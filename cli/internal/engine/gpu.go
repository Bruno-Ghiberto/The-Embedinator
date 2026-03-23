package engine

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"time"
)

// GPUResult holds the result of GPU detection.
type GPUResult struct {
	Profile       string // nvidia | amd | intel | none
	DeviceName    string // e.g., "RTX 4090"
	DriverVersion string // e.g., "565.77"
	RuntimeOK     bool   // whether Docker runtime supports the GPU
	AutoDetected  bool   // true if detection ran, false if user override
}

// GPUDiagnostic holds the full chain diagnostic for GPU passthrough.
type GPUDiagnostic struct {
	// Hardware
	HasNVIDIA     bool
	HasAMD        bool
	HasIntel      bool
	GPUName       string // e.g. "NVIDIA GeForce RTX 4070 Ti"
	DriverVersion string // e.g. "580.126.18"

	// Docker environment
	DockerType    string // "engine" | "desktop" | "unknown"
	DockerVersion string

	// Docker Engine coexistence (Linux only)
	EngineInstalled bool // Docker Engine is installed alongside Desktop
	EngineRunning   bool // Docker Engine service is active

	// NVIDIA toolkit chain (only relevant if HasNVIDIA)
	ToolkitInstalled  bool   // nvidia-container-toolkit package found
	ToolkitVersion    string
	RuntimeConfigured bool // "nvidia" in docker info runtimes
	CDISpecExists     bool // /etc/cdi/nvidia.yaml exists

	// AMD ROCm chain (only relevant if HasAMD)
	AMDKernelDriver bool // /dev/kfd exists
	AMDUserGroups   bool // user in video+render groups
	AMDRocmInfo     bool // rocminfo works

	// Intel ARC chain (only relevant if HasIntel)
	IntelDRI       bool // /dev/dri/renderD* exists
	IntelUserGroup bool // user in render group

	// Actual passthrough test
	PassthroughWorks bool   // docker run --gpus all actually works
	PassthroughError string // error message if it doesn't work

	// Issues found (ordered by severity)
	Issues []GPUIssue

	// Recommended profile
	RecommendedProfile string // "nvidia" | "amd" | "intel" | "none"
}

// GPUIssue describes a single problem found during GPU diagnostics.
type GPUIssue struct {
	Severity    string   // "blocker" | "warning" | "info"
	Title       string
	Description string
	FixCommands []string // shell commands to fix
	FixNote     string   // human-readable explanation
}

// HasBlockers returns true if any issue has "blocker" severity.
func (d *GPUDiagnostic) HasBlockers() bool {
	for _, issue := range d.Issues {
		if issue.Severity == "blocker" {
			return true
		}
	}
	return false
}

// DiagnoseGPU runs the full GPU passthrough diagnostic chain.
func DiagnoseGPU() *GPUDiagnostic {
	diag := &GPUDiagnostic{
		RecommendedProfile: "none",
	}

	// macOS: always Docker Desktop, no GPU passthrough.
	if runtime.GOOS == "darwin" {
		diag.DockerType = "desktop"
		diag.DockerVersion = getDockerVersion()
		diag.Issues = append(diag.Issues, GPUIssue{
			Severity:    "info",
			Title:       "macOS uses Docker Desktop",
			Description: "Docker Desktop on macOS cannot pass through GPU hardware. Ollama inside Docker will run in CPU mode.",
			FixNote:     "For GPU-accelerated inference, use a local Ollama install (it uses Metal natively).",
		})
		return diag
	}

	// Windows: always Docker Desktop (unless WSL2 with Docker Engine inside).
	if runtime.GOOS == "windows" {
		diag.DockerType = "desktop"
		diag.DockerVersion = getDockerVersion()
		// Check for NVIDIA on Windows (WSL2 GPU passthrough).
		if name, driver, ok := detectNVIDIAHardware(); ok {
			diag.HasNVIDIA = true
			diag.GPUName = name
			diag.DriverVersion = driver
			diag.Issues = append(diag.Issues, GPUIssue{
				Severity:    "info",
				Title:       "NVIDIA GPU detected on Windows",
				Description: "Docker Desktop on Windows supports NVIDIA GPU via WSL2. Ensure WSL2 backend is enabled in Docker Desktop settings.",
				FixNote:     "Enable WSL2 backend in Docker Desktop > Settings > General.",
			})
			diag.RecommendedProfile = "nvidia"
		}
		return diag
	}

	// Linux: full diagnostic chain.
	diag.DockerVersion = getDockerVersion()
	diag.DockerType = DetectDockerType()

	// Check Docker Engine coexistence state.
	diag.EngineInstalled = IsDockerEngineInstalled()
	diag.EngineRunning = IsDockerEngineRunning()

	// Detect GPU hardware.
	if name, driver, ok := detectNVIDIAHardware(); ok {
		diag.HasNVIDIA = true
		diag.GPUName = name
		diag.DriverVersion = driver
	}
	if detectAMDHardware() {
		diag.HasAMD = true
	}
	if detectIntelHardware() {
		diag.HasIntel = true
	}

	// No GPU at all.
	if !diag.HasNVIDIA && !diag.HasAMD && !diag.HasIntel {
		diag.Issues = append(diag.Issues, GPUIssue{
			Severity:    "info",
			Title:       "No supported GPU detected",
			Description: "No NVIDIA, AMD, or Intel GPU was found. Ollama will run in CPU mode.",
			FixNote:     "This is fine -- Ollama works well on CPU for smaller models.",
		})
		return diag
	}

	// Handle Docker Desktop on Linux: try to use Engine alongside it.
	if diag.DockerType == "desktop" {
		resolved := handleDockerDesktopCoexistence(diag)
		if !resolved {
			// Engine not available and couldn't be started -- blocker already added.
			return diag
		}
		// Engine is running. Continue diagnostic using Engine socket.
	}

	// Priority: NVIDIA > AMD > Intel.
	if diag.HasNVIDIA {
		diagnoseNVIDIAChain(diag)
	}
	if diag.HasAMD {
		diagnoseAMDChain(diag)
	}
	if diag.HasIntel {
		diagnoseIntelChain(diag)
	}

	// Set recommended profile by priority if not already set by a chain.
	if diag.RecommendedProfile == "none" {
		if diag.HasNVIDIA && !chainHasBlockers(diag, "nvidia") {
			diag.RecommendedProfile = "nvidia"
		} else if diag.HasAMD && !chainHasBlockers(diag, "amd") {
			diag.RecommendedProfile = "amd"
		} else if diag.HasIntel && !chainHasBlockers(diag, "intel") {
			diag.RecommendedProfile = "intel"
		}
	}

	return diag
}

// chainHasBlockers checks if any blocker issue relates to the given GPU vendor.
func chainHasBlockers(diag *GPUDiagnostic, vendor string) bool {
	prefix := strings.ToUpper(vendor[:1]) + vendor[1:]
	for _, issue := range diag.Issues {
		if issue.Severity == "blocker" && strings.Contains(issue.Title, prefix) {
			return true
		}
	}
	return false
}

// handleDockerDesktopCoexistence checks if Docker Engine can be used alongside Desktop.
// Returns true if Engine is available and running, false if it's a blocker.
func handleDockerDesktopCoexistence(diag *GPUDiagnostic) bool {
	distro := DetectLinuxDistro()

	// Case 1: Engine is installed and running -- just use it.
	if diag.EngineInstalled && diag.EngineRunning {
		diag.Issues = append(diag.Issues, GPUIssue{
			Severity:    "info",
			Title:       "Using Docker Engine for GPU access",
			Description: "Docker Desktop is installed but The Embedinator will use Docker Engine (via /var/run/docker.sock) for GPU-capable containers. Docker Desktop stays installed.",
			FixNote:     "No action needed. Docker Engine is already running alongside Docker Desktop.",
		})
		return true
	}

	// Case 2: Engine is installed but not running -- try to start it.
	if diag.EngineInstalled && !diag.EngineRunning {
		diag.Issues = append(diag.Issues, GPUIssue{
			Severity:    "warning",
			Title:       "Docker Engine installed but not running",
			Description: "Docker Engine is installed alongside Docker Desktop but the service is stopped. Starting it will enable GPU passthrough.",
			FixCommands: []string{
				"sudo systemctl start docker",
				"sudo systemctl enable docker",
			},
			FixNote: "Start the Docker Engine service. Docker Desktop stays installed and unaffected.",
		})
		return false
	}

	// Case 3: Engine is NOT installed -- provide install commands (no removal).
	installCmds := dockerEngineInstallCommands(distro)
	diag.Issues = append(diag.Issues, GPUIssue{
		Severity: "blocker",
		Title:    "Docker Engine needed for GPU passthrough",
		Description: "Docker Desktop doesn't support GPU passthrough on Linux, but Docker Engine does. " +
			"We'll install Docker Engine alongside Docker Desktop -- they coexist fine. " +
			"The Embedinator will use Docker Engine for GPU-accelerated containers.",
		FixCommands: installCmds,
		FixNote:     "Install Docker Engine alongside Docker Desktop. No need to remove Desktop.",
	})

	return false
}

// diagnoseNVIDIAChain runs the full NVIDIA-specific diagnostic chain on Linux.
func diagnoseNVIDIAChain(diag *GPUDiagnostic) {
	distro := DetectLinuxDistro()

	// Step 1: nvidia-container-toolkit.
	diag.ToolkitInstalled, diag.ToolkitVersion = detectNVIDIAToolkit()
	if !diag.ToolkitInstalled {
		installCmds := toolkitInstallCommands(distro)
		diag.Issues = append(diag.Issues, GPUIssue{
			Severity:    "blocker",
			Title:       "NVIDIA: nvidia-container-toolkit not installed",
			Description: "The NVIDIA Container Toolkit is required for Docker GPU passthrough. Without it, Docker cannot access the GPU.",
			FixCommands: installCmds,
			FixNote:     "Install the toolkit, then configure the Docker runtime.",
		})
	}

	// Step 2: NVIDIA runtime in Docker (query via Engine socket).
	diag.RuntimeConfigured = detectNVIDIARuntime()
	if !diag.RuntimeConfigured {
		diag.Issues = append(diag.Issues, GPUIssue{
			Severity:    "blocker",
			Title:       "NVIDIA: runtime not configured in Docker",
			Description: "The 'nvidia' runtime is not registered with the Docker daemon. Docker needs this to allocate GPU devices to containers.",
			FixCommands: []string{
				"sudo nvidia-ctk runtime configure --runtime=docker",
				"sudo systemctl restart docker",
			},
			FixNote: "This registers the nvidia runtime in /etc/docker/daemon.json and restarts Docker.",
		})
	}

	// Step 3: CDI spec.
	diag.CDISpecExists = detectCDISpec()
	if !diag.CDISpecExists {
		diag.Issues = append(diag.Issues, GPUIssue{
			Severity:    "warning",
			Title:       "NVIDIA: CDI specification not generated",
			Description: "The Container Device Interface spec helps Docker discover GPU devices. Some setups work without it, but generating it is recommended.",
			FixCommands: []string{
				"sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml",
			},
			FixNote: "This creates a device spec file that makes GPU discovery more reliable.",
		})
	}

	// Step 4: Actual passthrough test (only if no NVIDIA blockers so far).
	if !diag.HasBlockers() {
		diag.PassthroughWorks, diag.PassthroughError = testGPUPassthrough()
		if diag.PassthroughWorks {
			diag.RecommendedProfile = "nvidia"
		} else {
			diag.Issues = append(diag.Issues, GPUIssue{
				Severity:    "blocker",
				Title:       "NVIDIA: GPU passthrough test failed",
				Description: fmt.Sprintf("Running 'docker run --gpus all nvidia-smi' failed: %s", diag.PassthroughError),
				FixCommands: []string{
					"sudo nvidia-ctk runtime configure --runtime=docker",
					"sudo systemctl restart docker",
					"docker run --rm --gpus all nvidia/cuda:12.6.0-base-ubuntu24.04 nvidia-smi",
				},
				FixNote: "Try reconfiguring the runtime and restarting Docker, then test again.",
			})
		}
	}
}

// diagnoseAMDChain runs the full AMD ROCm diagnostic chain on Linux.
func diagnoseAMDChain(diag *GPUDiagnostic) {
	// Step 1: /dev/kfd (ROCm kernel driver).
	diag.AMDKernelDriver = detectAMDHardware()
	if !diag.AMDKernelDriver {
		diag.Issues = append(diag.Issues, GPUIssue{
			Severity:    "blocker",
			Title:       "AMD: ROCm kernel driver not loaded",
			Description: "/dev/kfd not found. The AMD ROCm kernel driver (amdgpu) must be loaded for GPU compute.",
			FixCommands: amdDriverInstallCommands(DetectLinuxDistro()),
			FixNote:     "Install the AMD ROCm kernel driver for your GPU, then reboot.",
		})
	}

	// Step 2: User in video + render groups.
	diag.AMDUserGroups = userInGroups("video", "render")
	if !diag.AMDUserGroups {
		diag.Issues = append(diag.Issues, GPUIssue{
			Severity:    "blocker",
			Title:       "AMD: user not in required groups",
			Description: "Your user must be in the 'video' and 'render' groups to access AMD GPU devices.",
			FixCommands: []string{
				"sudo usermod -aG video,render $USER",
				"# Log out and back in for group changes to take effect",
			},
			FixNote: "Add your user to the video and render groups, then log out and back in.",
		})
	}

	// Step 3: rocminfo works.
	diag.AMDRocmInfo = checkRocmInfo()
	if !diag.AMDRocmInfo {
		diag.Issues = append(diag.Issues, GPUIssue{
			Severity:    "warning",
			Title:       "AMD: rocminfo not available",
			Description: "The rocminfo utility is not installed or not working. This is used to verify ROCm driver setup.",
			FixCommands: amdRocmInfoInstallCommands(DetectLinuxDistro()),
			FixNote:     "Install ROCm runtime to verify GPU access. Containers may still work without this on the host.",
		})
	}

	// Step 4: Docker device passthrough test (only if no AMD blockers).
	if !chainHasBlockers(diag, "AMD") {
		ok, errMsg := testAMDPassthrough()
		if ok {
			if diag.RecommendedProfile == "none" {
				diag.RecommendedProfile = "amd"
			}
		} else {
			diag.Issues = append(diag.Issues, GPUIssue{
				Severity:    "blocker",
				Title:       "AMD: Docker GPU passthrough test failed",
				Description: fmt.Sprintf("Running ROCm container test failed: %s", errMsg),
				FixCommands: []string{
					"sudo usermod -aG video,render $USER",
					"# Log out and back in, then test:",
					"docker run --rm --device /dev/kfd --device /dev/dri rocm/dev-almalinux-8:latest rocminfo",
				},
				FixNote: "Ensure groups are set and devices are accessible, then test again.",
			})
		}
	}
}

// diagnoseIntelChain runs the full Intel ARC diagnostic chain on Linux.
func diagnoseIntelChain(diag *GPUDiagnostic) {
	// Always mark Intel as experimental.
	diag.Issues = append(diag.Issues, GPUIssue{
		Severity:    "info",
		Title:       "Intel GPU support is experimental",
		Description: "Intel ARC GPU support in Docker is experimental. Performance and compatibility may vary.",
		FixNote:     "Intel GPU passthrough uses /dev/dri. NVIDIA and AMD have more mature Docker GPU support.",
	})

	// Step 1: /dev/dri/renderD* exists.
	diag.IntelDRI = detectIntelHardware()
	if !diag.IntelDRI {
		diag.Issues = append(diag.Issues, GPUIssue{
			Severity:    "blocker",
			Title:       "Intel: /dev/dri render devices not found",
			Description: "No /dev/dri/renderD* devices were found. The Intel i915 or xe kernel driver must be loaded.",
			FixCommands: []string{
				"# Ensure Intel GPU kernel driver is loaded:",
				"sudo modprobe i915",
				"# For newer ARC GPUs, the xe driver may be needed:",
				"sudo modprobe xe",
			},
			FixNote: "Load the appropriate Intel kernel driver and check that /dev/dri/renderD* appears.",
		})
	}

	// Step 2: User in render group.
	diag.IntelUserGroup = userInGroups("render")
	if !diag.IntelUserGroup {
		diag.Issues = append(diag.Issues, GPUIssue{
			Severity:    "blocker",
			Title:       "Intel: user not in render group",
			Description: "Your user must be in the 'render' group to access Intel GPU devices.",
			FixCommands: []string{
				"sudo usermod -aG render $USER",
				"# Log out and back in for group changes to take effect",
			},
			FixNote: "Add your user to the render group, then log out and back in.",
		})
	}

	// Step 3: Check intel_gpu_top or /dev/dri accessibility.
	if !checkIntelGPUAccess() {
		diag.Issues = append(diag.Issues, GPUIssue{
			Severity:    "warning",
			Title:       "Intel: cannot verify GPU accessibility",
			Description: "Neither intel_gpu_top nor direct /dev/dri access could be confirmed. The GPU may still work in Docker.",
			FixCommands: []string{
				"# Install Intel GPU tools (optional, for verification):",
				"sudo apt-get install intel-gpu-tools  # Debian/Ubuntu",
				"sudo dnf install intel-gpu-tools      # Fedora",
			},
			FixNote: "Intel GPU tools help verify access but are not required for Docker passthrough.",
		})
	}

	// Step 4: Docker device passthrough test (only if no Intel blockers).
	if !chainHasBlockers(diag, "Intel") {
		ok, errMsg := testIntelPassthrough()
		if ok {
			if diag.RecommendedProfile == "none" {
				diag.RecommendedProfile = "intel"
			}
		} else {
			diag.Issues = append(diag.Issues, GPUIssue{
				Severity:    "warning",
				Title:       "Intel: Docker GPU passthrough test inconclusive",
				Description: fmt.Sprintf("Running Intel compute container test failed: %s. This is experimental and may still work with Ollama.", errMsg),
				FixCommands: []string{
					"sudo usermod -aG render $USER",
					"# Log out and back in, then test:",
					"docker run --rm --device /dev/dri intel/compute-runtime:latest clinfo",
				},
				FixNote: "Intel GPU Docker support is experimental. You can still try the intel GPU profile.",
			})
		}
	}
}

// DetectGPU runs the full GPU detection logic.
// Preserved for backward compatibility -- delegates to DiagnoseGPU internally.
func DetectGPU() GPUResult {
	// macOS: always CPU (no GPU passthrough in Docker Desktop).
	if runtime.GOOS == "darwin" {
		return GPUResult{Profile: "none", AutoDetected: true}
	}

	// Check env var override.
	if override := os.Getenv("EMBEDINATOR_GPU"); override != "" {
		switch override {
		case "nvidia", "amd", "intel", "none":
			return GPUResult{Profile: override, AutoDetected: false}
		}
	}

	diag := DiagnoseGPU()

	result := GPUResult{
		Profile:       diag.RecommendedProfile,
		DeviceName:    diag.GPUName,
		DriverVersion: diag.DriverVersion,
		RuntimeOK:     diag.RecommendedProfile != "none",
		AutoDetected:  true,
	}

	return result
}

// --- Hardware detection helpers ---

// detectNVIDIAHardware checks if nvidia-smi is available and returns GPU info.
func detectNVIDIAHardware() (name, driver string, ok bool) {
	out, err := exec.Command("nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader,nounits").Output()
	if err != nil {
		return "", "", false
	}

	fields := strings.SplitN(strings.TrimSpace(string(out)), ",", 2)
	if len(fields) >= 1 {
		name = strings.TrimSpace(fields[0])
	}
	if len(fields) >= 2 {
		driver = strings.TrimSpace(fields[1])
	}

	return name, driver, true
}

// detectAMDHardware checks if /dev/kfd exists (AMD ROCm kernel driver).
func detectAMDHardware() bool {
	_, err := os.Stat("/dev/kfd")
	return err == nil
}

// detectIntelHardware checks if /dev/dri/renderD* exists.
func detectIntelHardware() bool {
	matches, _ := filepath.Glob("/dev/dri/renderD*")
	return len(matches) > 0
}

// --- NVIDIA toolkit chain helpers ---

// detectNVIDIAToolkit checks if nvidia-container-toolkit is installed.
func detectNVIDIAToolkit() (installed bool, version string) {
	// Try the direct command first.
	out, err := exec.Command("nvidia-ctk", "--version").CombinedOutput()
	if err == nil {
		ver := strings.TrimSpace(string(out))
		// Output is like "NVIDIA Container Toolkit CLI version 1.19.0"
		parts := strings.Fields(ver)
		if len(parts) > 0 {
			version = parts[len(parts)-1]
		}
		return true, version
	}

	// Fallback: check package manager.
	distro := DetectLinuxDistro()
	switch distro {
	case "fedora", "rhel", "centos":
		out, err = exec.Command("rpm", "-q", "nvidia-container-toolkit").CombinedOutput()
		if err == nil && !strings.Contains(string(out), "not installed") {
			ver := strings.TrimSpace(string(out))
			// rpm -q returns "nvidia-container-toolkit-1.19.0-1.x86_64"
			parts := strings.Split(ver, "-")
			if len(parts) >= 4 {
				version = parts[3]
			}
			return true, version
		}
	case "ubuntu", "debian":
		out, err = exec.Command("dpkg", "-s", "nvidia-container-toolkit").CombinedOutput()
		if err == nil && strings.Contains(string(out), "Status: install ok installed") {
			for _, line := range strings.Split(string(out), "\n") {
				if strings.HasPrefix(line, "Version:") {
					version = strings.TrimSpace(strings.TrimPrefix(line, "Version:"))
					break
				}
			}
			return true, version
		}
	case "arch":
		out, err = exec.Command("pacman", "-Q", "nvidia-container-toolkit").CombinedOutput()
		if err == nil {
			parts := strings.Fields(strings.TrimSpace(string(out)))
			if len(parts) >= 2 {
				version = parts[1]
			}
			return true, version
		}
	}

	return false, ""
}

// detectNVIDIARuntime checks if "nvidia" is among Docker's configured runtimes.
// Uses DockerCommand to target Engine socket on Linux.
func detectNVIDIARuntime() bool {
	cmd := DockerCommand("info", "--format", "{{.Runtimes}}")
	out, err := cmd.CombinedOutput()
	if err != nil {
		// Fallback: parse full docker info.
		cmd = DockerCommand("info")
		out, err = cmd.CombinedOutput()
		if err != nil {
			return false
		}
	}
	return strings.Contains(strings.ToLower(string(out)), "nvidia")
}

// detectCDISpec checks if the NVIDIA CDI spec exists.
func detectCDISpec() bool {
	paths := []string{
		"/etc/cdi/nvidia.yaml",
		"/var/run/cdi/nvidia.yaml",
	}
	for _, p := range paths {
		if _, err := os.Stat(p); err == nil {
			return true
		}
	}
	return false
}

// testGPUPassthrough runs an actual Docker container with --gpus all.
// Uses DockerCommand to target Engine socket on Linux.
func testGPUPassthrough() (ok bool, errMsg string) {
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	cmd := DockerCommand("run", "--rm", "--gpus", "all",
		"nvidia/cuda:12.6.0-base-ubuntu24.04", "nvidia-smi", "--query-gpu=name", "--format=csv,noheader")
	cmd = exec.CommandContext(ctx, cmd.Path, cmd.Args[1:]...)
	cmd.Env = DockerCommand().Env // Re-apply Engine env for the context command.
	out, err := cmd.CombinedOutput()
	if err != nil {
		output := strings.TrimSpace(string(out))
		if output != "" {
			return false, output
		}
		return false, err.Error()
	}

	return true, ""
}

// --- AMD diagnostic helpers ---

// userInGroups checks if the current user belongs to all specified groups.
func userInGroups(groups ...string) bool {
	out, err := exec.Command("groups").Output()
	if err != nil {
		return false
	}
	userGroups := strings.ToLower(string(out))
	for _, g := range groups {
		if !strings.Contains(userGroups, strings.ToLower(g)) {
			return false
		}
	}
	return true
}

// checkRocmInfo runs rocminfo and checks if it succeeds.
func checkRocmInfo() bool {
	err := exec.Command("rocminfo").Run()
	return err == nil
}

// testAMDPassthrough tests AMD GPU passthrough in Docker.
func testAMDPassthrough() (ok bool, errMsg string) {
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	cmd := DockerCommand("run", "--rm", "--device", "/dev/kfd", "--device", "/dev/dri",
		"rocm/dev-almalinux-8:latest", "rocminfo")
	cmd = exec.CommandContext(ctx, cmd.Path, cmd.Args[1:]...)
	cmd.Env = DockerCommand().Env
	out, err := cmd.CombinedOutput()
	if err != nil {
		output := strings.TrimSpace(string(out))
		if output != "" {
			return false, output
		}
		return false, err.Error()
	}
	return true, ""
}

// amdDriverInstallCommands returns distro-specific commands to install AMD ROCm kernel driver.
func amdDriverInstallCommands(distro string) []string {
	switch distro {
	case "ubuntu", "debian":
		return []string{
			"# Install AMD ROCm kernel driver:",
			"wget https://repo.radeon.com/amdgpu-install/latest/ubuntu/jammy/amdgpu-install_6.4.60400-1_all.deb",
			"sudo apt-get install ./amdgpu-install_6.4.60400-1_all.deb",
			"sudo amdgpu-install --usecase=rocm",
			"sudo usermod -aG video,render $USER",
			"# Reboot required after installation",
		}
	case "fedora", "rhel", "centos":
		return []string{
			"# Install AMD ROCm kernel driver:",
			"sudo dnf install https://repo.radeon.com/amdgpu-install/latest/rhel/9.4/amdgpu-install-6.4.60400-1.el9.noarch.rpm",
			"sudo amdgpu-install --usecase=rocm",
			"sudo usermod -aG video,render $USER",
			"# Reboot required after installation",
		}
	case "arch":
		return []string{
			"# Install AMD ROCm from AUR:",
			"yay -S rocm-hip-sdk",
			"sudo usermod -aG video,render $USER",
			"# Reboot required after installation",
		}
	default:
		return []string{
			"# See https://rocm.docs.amd.com/projects/install-on-linux/en/latest/",
			"sudo usermod -aG video,render $USER",
		}
	}
}

// amdRocmInfoInstallCommands returns commands to install rocminfo utility.
func amdRocmInfoInstallCommands(distro string) []string {
	switch distro {
	case "ubuntu", "debian":
		return []string{"sudo apt-get install rocminfo"}
	case "fedora", "rhel", "centos":
		return []string{"sudo dnf install rocminfo"}
	case "arch":
		return []string{"yay -S rocminfo"}
	default:
		return []string{"# Install rocminfo from your package manager"}
	}
}

// --- Intel diagnostic helpers ---

// checkIntelGPUAccess checks if Intel GPU tools or /dev/dri are accessible.
func checkIntelGPUAccess() bool {
	// Try intel_gpu_top.
	if _, err := exec.LookPath("intel_gpu_top"); err == nil {
		return true
	}
	// Check /dev/dri is readable.
	entries, err := os.ReadDir("/dev/dri")
	if err != nil {
		return false
	}
	for _, e := range entries {
		if strings.HasPrefix(e.Name(), "renderD") {
			return true
		}
	}
	return false
}

// testIntelPassthrough tests Intel GPU passthrough in Docker.
func testIntelPassthrough() (ok bool, errMsg string) {
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	cmd := DockerCommand("run", "--rm", "--device", "/dev/dri",
		"intel/compute-runtime:latest", "clinfo")
	cmd = exec.CommandContext(ctx, cmd.Path, cmd.Args[1:]...)
	cmd.Env = DockerCommand().Env
	out, err := cmd.CombinedOutput()
	if err != nil {
		output := strings.TrimSpace(string(out))
		if output != "" {
			return false, output
		}
		return false, err.Error()
	}
	return true, ""
}

// --- Docker Engine install commands (coexistence with Desktop) ---

// dockerEngineInstallCommands returns distro-specific commands to install Docker Engine
// ALONGSIDE Docker Desktop (no removal commands).
func dockerEngineInstallCommands(distro string) []string {
	switch distro {
	case "fedora":
		return []string{
			"# Install Docker Engine alongside Docker Desktop:",
			"sudo dnf config-manager addrepo --from-repofile=https://download.docker.com/linux/fedora/docker-ce.repo",
			"sudo dnf install docker-ce docker-ce-cli containerd.io docker-compose-plugin",
			"sudo systemctl enable --now docker",
			"sudo usermod -aG docker $USER",
			"# Log out and back in for group changes to take effect",
		}
	case "ubuntu":
		return []string{
			"# Install Docker Engine alongside Docker Desktop:",
			"sudo apt-get update",
			"sudo apt-get install ca-certificates curl",
			"sudo install -m 0755 -d /etc/apt/keyrings",
			"sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc",
			"sudo chmod a+r /etc/apt/keyrings/docker.asc",
			`echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null`,
			"sudo apt-get update",
			"sudo apt-get install docker-ce docker-ce-cli containerd.io docker-compose-plugin",
			"sudo systemctl enable --now docker",
			"sudo usermod -aG docker $USER",
			"# Log out and back in for group changes to take effect",
		}
	case "debian":
		return []string{
			"# Install Docker Engine alongside Docker Desktop:",
			"sudo apt-get update",
			"sudo apt-get install ca-certificates curl",
			"sudo install -m 0755 -d /etc/apt/keyrings",
			"sudo curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc",
			"sudo chmod a+r /etc/apt/keyrings/docker.asc",
			`echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(. /etc/os-release && echo $VERSION_CODENAME) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null`,
			"sudo apt-get update",
			"sudo apt-get install docker-ce docker-ce-cli containerd.io docker-compose-plugin",
			"sudo systemctl enable --now docker",
			"sudo usermod -aG docker $USER",
			"# Log out and back in for group changes to take effect",
		}
	case "arch":
		return []string{
			"# Install Docker Engine alongside Docker Desktop:",
			"sudo pacman -S docker docker-compose",
			"sudo systemctl enable --now docker",
			"sudo usermod -aG docker $USER",
			"# Log out and back in for group changes to take effect",
		}
	default:
		return []string{
			"# Install Docker Engine (see https://docs.docker.com/engine/install/):",
			"# Docker Engine and Docker Desktop coexist fine on Linux.",
			"sudo systemctl enable --now docker",
			"sudo usermod -aG docker $USER",
		}
	}
}

// toolkitInstallCommands returns distro-specific commands to install nvidia-container-toolkit.
func toolkitInstallCommands(distro string) []string {
	switch distro {
	case "fedora", "rhel", "centos":
		return []string{
			"curl -s -L https://nvidia.github.io/libnvidia-container/stable/rpm/nvidia-container-toolkit.repo | sudo tee /etc/yum.repos.d/nvidia-container-toolkit.repo",
			"sudo dnf install nvidia-container-toolkit",
			"sudo nvidia-ctk runtime configure --runtime=docker",
			"sudo systemctl restart docker",
		}
	case "ubuntu", "debian":
		return []string{
			"curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg",
			`curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list`,
			"sudo apt-get update",
			"sudo apt-get install nvidia-container-toolkit",
			"sudo nvidia-ctk runtime configure --runtime=docker",
			"sudo systemctl restart docker",
		}
	case "arch":
		return []string{
			"yay -S nvidia-container-toolkit",
			"# Or: sudo pacman -S nvidia-container-toolkit (if in official repos)",
			"sudo nvidia-ctk runtime configure --runtime=docker",
			"sudo systemctl restart docker",
		}
	default:
		return []string{
			"# See https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html",
			"sudo nvidia-ctk runtime configure --runtime=docker",
			"sudo systemctl restart docker",
		}
	}
}

// getDockerVersion returns the Docker server version string.
// Uses DockerCommand to target Engine socket on Linux.
func getDockerVersion() string {
	cmd := DockerCommand("version", "--format", "{{.Server.Version}}")
	out, err := cmd.CombinedOutput()
	if err != nil {
		return ""
	}
	return strings.TrimSpace(string(out))
}
