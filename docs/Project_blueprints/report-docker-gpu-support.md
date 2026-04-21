# Docker GPU Passthrough: Full Technical Report

**Date**: 2026-03-23
**Purpose**: Document how Docker GPU support works across platforms and Docker variants, so the TUI installer can guide users to a working GPU setup.

---

## Executive Summary

Docker GPU passthrough to containers requires a chain of 4-5 components to be correctly installed and configured. The critical finding is:

- **Docker Engine on Linux**: Full NVIDIA GPU support. This is the recommended path.
- **Docker Desktop on Linux**: **NO GPU support.** Open issue since 2022, still unresolved (GitHub docker/roadmap#497). The VM architecture blocks GPU passthrough.
- **Docker Desktop on Windows (WSL2)**: NVIDIA GPU support works via GPU Paravirtualization (GPU-PV).
- **Docker Desktop on macOS**: No GPU passthrough. Metal GPU cannot be passed to containers.

**For The Embedinator's TUI**: On Linux, the installer MUST detect Docker Desktop and offer to migrate the user to Docker Engine. There is no workaround for Docker Desktop + GPU on Linux.

---

## 1. The GPU Passthrough Chain

For a container to use an NVIDIA GPU, every link in this chain must work:

```
┌─────────────────┐
│ 1. GPU Hardware  │  nvidia-smi must report a GPU
├─────────────────┤
│ 2. NVIDIA Driver │  Host kernel driver (e.g., 580.x)
├─────────────────┤
│ 3. Docker Type   │  MUST be Docker Engine on Linux (not Desktop)
├─────────────────┤
│ 4. NVIDIA        │  nvidia-container-toolkit package
│    Container     │  Provides: nvidia-container-runtime,
│    Toolkit       │  nvidia-ctk, nvidia-container-cli
├─────────────────┤
│ 5. Runtime       │  "nvidia" runtime registered in
│    Config        │  /etc/docker/daemon.json
├─────────────────┤
│ 6. CDI Spec      │  /etc/cdi/nvidia.yaml generated
│    (optional)    │  Required for Docker Engine 28.3+
├─────────────────┤
│ 7. Passthrough   │  docker run --gpus all nvidia-smi
│    Test          │  actually works
└─────────────────┘
```

If ANY link is broken, GPU access fails. The error messages are often cryptic (e.g., `could not select device driver "nvidia" with capabilities: [[gpu]]`), which is why the TUI must diagnose each step individually.

---

## 2. Docker Engine vs Docker Desktop

### 2.1 Docker Engine (docker-ce)

Docker Engine runs the daemon **natively on the host**. The container runtime has direct access to host devices including GPUs. This is the architecture that NVIDIA's container toolkit is designed for.

```
Host OS (Linux)
├── NVIDIA Kernel Driver
├── Docker Engine (dockerd) ← runs directly on host
│   ├── nvidia-container-runtime ← can find /usr/bin/nvidia-*
│   └── Container
│       └── nvidia-smi → talks to host GPU driver
```

**Supported**: Full GPU passthrough via `--gpus`, `deploy.resources.reservations.devices`, and CDI.

### 2.2 Docker Desktop on Linux

Docker Desktop runs the daemon **inside a lightweight VM** (using QEMU/KVM or VirtioFS). The nvidia-container-runtime binary exists on the host at `/usr/bin/nvidia-container-runtime`, but the Docker daemon inside the VM cannot see it.

```
Host OS (Linux)
├── NVIDIA Kernel Driver
├── Docker Desktop
│   └── Lightweight VM (LinuxKit)
│       ├── dockerd ← runs INSIDE the VM
│       ├── nvidia-container-runtime ← NOT FOUND (not in VM)
│       └── Container
│           └── nvidia-smi → FAILS
```

**Status**: NOT SUPPORTED. GitHub issue [docker/roadmap#497](https://github.com/docker/roadmap/issues/497) has been open since 2022 with 16+ upvotes. No official timeline or technical plan from Docker.

**Detection**: Check for `/var/run/desktop-containerd/` or `~/.docker/desktop/` directory, or "Desktop" in `docker info` output.

**Error**: `exec: "nvidia-container-runtime": executable file not found in $PATH` or `could not select device driver "nvidia" with capabilities: [[gpu]]`.

### 2.3 Docker Desktop on Windows (WSL2)

Docker Desktop on Windows uses WSL2 as its backend. NVIDIA provides GPU Paravirtualization (GPU-PV) for WSL2, which allows GPU passthrough through the Hyper-V GPU virtualization layer.

**Supported**: Yes, with prerequisites:
- Windows 10/11 with up-to-date NVIDIA drivers supporting WSL2 GPU-PV
- WSL2 kernel updated (`wsl --update`)
- Docker Desktop WSL2 backend enabled

**Test**: `docker run --rm -it --gpus=all nvcr.io/nvidia/k8s/cuda-sample:nbody nbody -gpu -benchmark`

### 2.4 Docker Desktop on macOS

macOS uses Apple Silicon (Metal) or Intel GPUs. Docker Desktop runs in a HyperKit/Apple Virtualization Framework VM. Neither Metal nor Intel GPU can be passed through to Docker containers.

**Status**: NOT SUPPORTED. No workaround exists.

**Recommendation**: Use local Ollama (installed natively) which has Metal GPU access.

---

## 3. NVIDIA Container Toolkit

### 3.1 What It Is

The NVIDIA Container Toolkit is the official package that enables GPU-accelerated containers. It provides:

- **nvidia-container-runtime**: An OCI-compliant runtime that wraps runc with GPU device injection
- **nvidia-ctk**: CLI tool for configuring Docker, generating CDI specs, and diagnostics
- **nvidia-container-cli**: Low-level CLI for device and driver management
- **libnvidia-container**: Library that handles the actual device injection

### 3.2 Installation by Distro

#### Fedora / RHEL / CentOS (dnf)

```bash
# Add NVIDIA repository
curl -s -L https://nvidia.github.io/libnvidia-container/stable/rpm/nvidia-container-toolkit.repo | \
  sudo tee /etc/yum.repos.d/nvidia-container-toolkit.repo

# Install
sudo dnf install nvidia-container-toolkit

# Configure Docker
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

#### Ubuntu / Debian (apt)

```bash
# Add GPG key and repository
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
  sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

# Install
sudo apt-get update
sudo apt-get install nvidia-container-toolkit

# Configure Docker
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

#### Arch Linux

```bash
# Install from AUR
yay -S nvidia-container-toolkit
# OR
sudo pacman -S nvidia-container-toolkit  # if in official repos

# Configure Docker
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

### 3.3 What `nvidia-ctk runtime configure` Does

This command modifies `/etc/docker/daemon.json` to register the nvidia runtime:

```json
{
    "runtimes": {
        "nvidia": {
            "args": [],
            "path": "nvidia-container-runtime"
        }
    }
}
```

It can also set nvidia as the default runtime:

```json
{
    "default-runtime": "nvidia",
    "runtimes": {
        "nvidia": {
            "args": [],
            "path": "nvidia-container-runtime"
        }
    }
}
```

### 3.4 Rootless Docker Mode

For rootless Docker installations, an additional configuration is needed:

```bash
nvidia-ctk config --set nvidia-container-cli.no-cgroups --in-place
```

This modifies `/etc/nvidia-container-runtime/config.toml`.

---

## 4. Container Device Interface (CDI)

### 4.1 What CDI Is

CDI is a CNCF standardized mechanism for container runtimes to expose host devices to containers. Since Docker Engine 28.3.0, CDI is enabled by default.

CDI specification files live in:
- `/etc/cdi/` — static specs
- `/var/run/cdi` — generated specs

### 4.2 Generating NVIDIA CDI Specs

```bash
sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml
```

This generates a YAML file that describes:
- Device nodes (`/dev/nvidia0`, `/dev/nvidiactl`, `/dev/nvidia-uvm`, etc.)
- Environment variables (`NVIDIA_VISIBLE_DEVICES`)
- Host-to-container library mounts (CUDA, nvml, OpenCL, etc.)
- Initialization hooks for symlink creation and ldcache updates

### 4.3 CDI vs Legacy `--gpus`

| Feature | `--gpus` flag | CDI |
|---------|:---:|:---:|
| Docker Engine support | 19.03+ | 28.3+ (default) |
| Standardized spec | No | Yes (CNCF) |
| Works with Compose `deploy` | Yes | Yes |
| Requires nvidia-container-toolkit | Yes | Yes |
| Declarative device config | No | Yes (YAML/JSON) |
| Build-time GPU access | No | Yes (`RUN --device`) |
| Multi-runtime support | Docker only | Docker, Containerd, CRI-O, Podman |

### 4.4 CDI in Docker Compose

Docker Compose uses the `deploy.resources.reservations.devices` syntax, which works with both the legacy runtime and CDI:

```yaml
services:
  ollama:
    image: ollama/ollama:latest
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

Properties:
- **driver** (required): `"nvidia"`
- **capabilities** (required): `[gpu]` — must be a list
- **count** (optional): integer or `"all"`. Default: all GPUs. Mutually exclusive with `device_ids`
- **device_ids** (optional): list of GPU indices like `['0', '3']`. Mutually exclusive with `count`
- **options** (optional): driver-specific key-value pairs

---

## 5. Docker Desktop to Docker Engine Migration (Linux)

This is the most critical path for the TUI installer. When a Linux user has Docker Desktop, the only way to get GPU passthrough is to switch to Docker Engine.

### 5.1 Migration Steps for Fedora

```bash
# 1. Stop and remove Docker Desktop
sudo dnf remove docker-desktop
rm -rf ~/.docker/desktop

# 2. Install Docker Engine
sudo dnf config-manager addrepo --from-repofile=https://download.docker.com/linux/fedora/docker-ce.repo
sudo dnf install docker-ce docker-ce-cli containerd.io docker-compose-plugin docker-buildx-plugin

# 3. Start Docker Engine
sudo systemctl enable --now docker

# 4. Add user to docker group (avoid sudo for every command)
sudo usermod -aG docker $USER
newgrp docker

# 5. Install NVIDIA Container Toolkit (if not already)
curl -s -L https://nvidia.github.io/libnvidia-container/stable/rpm/nvidia-container-toolkit.repo | \
  sudo tee /etc/yum.repos.d/nvidia-container-toolkit.repo
sudo dnf install nvidia-container-toolkit

# 6. Configure nvidia runtime for Docker
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# 7. Generate CDI spec (recommended for Docker 28.3+)
sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml

# 8. Verify
docker run --rm --gpus all nvidia/cuda:12.6.0-base-ubuntu24.04 nvidia-smi
```

### 5.2 Migration Steps for Ubuntu/Debian

```bash
# 1. Remove Docker Desktop
sudo apt-get remove docker-desktop
rm -rf ~/.docker/desktop

# 2. Install Docker Engine
sudo apt-get update
sudo apt-get install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install docker-ce docker-ce-cli containerd.io docker-compose-plugin docker-buildx-plugin

# 3. Start Docker Engine
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
newgrp docker

# 4. Install NVIDIA Container Toolkit
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
  sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt-get update
sudo apt-get install nvidia-container-toolkit

# 5. Configure + CDI + verify
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml
docker run --rm --gpus all nvidia/cuda:12.6.0-base-ubuntu24.04 nvidia-smi
```

---

## 6. NVIDIA Driver Capabilities

When running GPU containers, the toolkit allows fine-grained control over which driver components are exposed via `NVIDIA_DRIVER_CAPABILITIES`:

| Capability | Purpose |
|-----------|---------|
| `compute` | CUDA and OpenCL libraries |
| `graphics` | OpenGL and Vulkan |
| `utility` | nvidia-smi and NVML |
| `video` | Video Codec SDK |
| `display` | X11 display forwarding |
| `compat32` | 32-bit application support |

Default (when unset): `utility,compute` — sufficient for most AI/ML workloads including Ollama.

---

## 7. Common Errors and Fixes

| Error | Cause | Fix |
|-------|-------|-----|
| `could not select device driver "nvidia" with capabilities: [[gpu]]` | nvidia-container-toolkit not installed or runtime not configured | Install toolkit + `nvidia-ctk runtime configure --runtime=docker` + restart docker |
| `could not select device driver "" with capabilities: [[gpu]]` | CDI spec missing or Docker can't find the nvidia runtime | `sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml` |
| `exec: "nvidia-container-runtime": executable file not found in $PATH` | Docker Desktop on Linux (runtime binary not in VM) | Switch to Docker Engine |
| `Failed to initialize NVML: Unknown Error` | GPU access lost after system update or `systemctl daemon-reload` | Use CDI mode, or restart Docker, or add explicit `--device` flags |
| `Permission Denied` on Qdrant WAL | Container wrote files as root, permissions mismatch on bind mount | `sudo chown -R $(id -u):$(id -g) data/qdrant_db/` |
| SELinux blocking GPU access | SELinux denying device access | `--security-opt=label=disable` or configure SELinux policy |

---

## 8. Platform Decision Matrix for The Embedinator TUI

| Platform | Docker Type | GPU Passthrough | TUI Action |
|----------|------------|:-:|------------|
| Linux + NVIDIA + Docker Engine | Engine | **Yes** | Verify toolkit chain, offer to install/configure missing pieces |
| Linux + NVIDIA + Docker Desktop | Desktop | **No** | **BLOCKER** — offer Docker Desktop → Engine migration with distro-specific commands |
| Linux + AMD | Engine | Partial | AMD ROCm via `/dev/kfd` + `ollama:rocm` image. Less tested. |
| macOS + Apple Silicon | Desktop | **No** | Recommend local Ollama (Metal GPU). Docker Ollama = CPU only. |
| macOS + Intel | Desktop | **No** | CPU only. No workaround. |
| Windows + NVIDIA + WSL2 | Desktop | **Yes** | Verify WSL2 backend enabled, NVIDIA drivers updated, `wsl --update` |
| Windows + AMD/Intel | Desktop | **No** | CPU only in Docker. Recommend local Ollama. |

---

## 9. Recommendations for the TUI Installer

Based on this research, the TUI's GPU screen should:

1. **Always run the full diagnostic chain** — don't stop at "nvidia-smi found a GPU"
2. **Detect Docker Desktop on Linux as a hard blocker** — there is no workaround, no experimental flag, no hidden setting
3. **Provide distro-specific migration commands** — detect Fedora/Ubuntu/Debian/Arch and generate exact commands
4. **Offer to generate CDI specs** — needed for Docker Engine 28.3+
5. **Run an actual passthrough test** — `docker run --rm --gpus all nvidia/cuda:12.6.0-base-ubuntu24.04 nvidia-smi` is the only true verification
6. **On macOS, strongly recommend local Ollama** — Metal GPU is 3-10x faster than CPU-only Docker Ollama
7. **On Windows, verify WSL2 backend** — the only supported GPU path

---

## Sources

- [Docker Compose GPU Support](https://docs.docker.com/compose/how-tos/gpu-support/)
- [Docker Desktop GPU Support (Windows WSL2)](https://docs.docker.com/desktop/features/gpu/)
- [Docker CDI (Container Device Interface)](https://docs.docker.com/build/building/cdi/)
- [Docker Engine daemon.json CDI configuration](https://docs.docker.com/reference/cli/dockerd/)
- [NVIDIA Container Toolkit Installation Guide](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)
- [NVIDIA Container Toolkit Specialized Docker Configurations](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/docker-specialized.html)
- [NVIDIA Container Toolkit Troubleshooting](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/troubleshooting.html)
- [Docker Roadmap #497: Docker Desktop Linux GPU Support](https://github.com/docker/roadmap/issues/497) — Open since 2022, no resolution
