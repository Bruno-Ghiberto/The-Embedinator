package engine

import (
	"fmt"
	"os"
	"os/exec"
	"runtime"
	"strconv"
	"strings"
	"syscall"
)

// IsDockerEngineInstalled checks if Docker Engine (not Desktop) is available on Linux.
func IsDockerEngineInstalled() bool {
	if runtime.GOOS != "linux" {
		return false
	}
	// Check if the Engine socket exists.
	if _, err := os.Stat("/var/run/docker.sock"); err == nil {
		return true
	}
	// Check if dockerd binary exists.
	if _, err := exec.LookPath("dockerd"); err == nil {
		return true
	}
	return false
}

// IsDockerEngineRunning checks if Docker Engine service is active.
func IsDockerEngineRunning() bool {
	if runtime.GOOS != "linux" {
		return false
	}
	out, err := exec.Command("systemctl", "is-active", "docker").Output()
	if err != nil {
		return false
	}
	return strings.TrimSpace(string(out)) == "active"
}

// DockerEngineInstallCommands returns distro-specific commands to install Docker Engine
// ALONGSIDE Docker Desktop (no removal commands).
func DockerEngineInstallCommands(distro string) []string {
	return dockerEngineInstallCommands(distro)
}

// PreflightResult holds the result of a single preflight check.
type PreflightResult struct {
	Name    string
	OK      bool
	Detail  string
	Error   string
}

// CheckDocker checks if the Docker daemon is running and returns the version.
// Uses DockerCommand to target Engine socket on Linux.
func CheckDocker() PreflightResult {
	result := PreflightResult{Name: "Docker daemon"}

	cmd := DockerCommand("version", "--format", "{{.Server.Version}}")
	out, err := cmd.CombinedOutput()
	if err != nil {
		result.OK = false
		result.Error = "Docker daemon is not running or not installed"

		// Check if user is not in docker group (Linux).
		if runtime.GOOS == "linux" {
			groupOut, _ := exec.Command("groups").Output()
			if !strings.Contains(string(groupOut), "docker") {
				result.Error += ". Your user is not in the 'docker' group. Fix: sudo usermod -aG docker $USER && newgrp docker"
			}
		}
		return result
	}

	version := strings.TrimSpace(string(out))
	result.OK = true
	result.Detail = fmt.Sprintf("v%s", version)
	return result
}

// CheckDockerCompose checks if Docker Compose v2 is available.
// Uses DockerCommand to target Engine socket on Linux.
func CheckDockerCompose() PreflightResult {
	result := PreflightResult{Name: "Docker Compose v2"}

	cmd := DockerCommand("compose", "version", "--short")
	out, err := cmd.CombinedOutput()
	if err != nil {
		result.OK = false
		result.Error = "Docker Compose v2 is not available. Install the 'docker compose' plugin."
		return result
	}

	version := strings.TrimSpace(string(out))
	result.OK = true
	result.Detail = fmt.Sprintf("v%s", version)
	return result
}

// CheckDiskSpace checks available disk space at the given path.
// Returns the result with available GB and whether it meets the minimum.
func CheckDiskSpace(path string, minGB uint64) PreflightResult {
	result := PreflightResult{Name: "Disk space"}

	var stat syscall.Statfs_t
	if err := syscall.Statfs(path, &stat); err != nil {
		result.OK = false
		result.Error = fmt.Sprintf("unable to check disk space: %v", err)
		return result
	}

	availableBytes := stat.Bavail * uint64(stat.Bsize)
	availableGB := availableBytes / (1024 * 1024 * 1024)

	if availableGB < minGB {
		result.OK = false
		result.Error = fmt.Sprintf("%d GB available, %d GB required", availableGB, minGB)
		return result
	}

	result.OK = true
	result.Detail = fmt.Sprintf("%d GB available (%d GB required)", availableGB, minGB)
	return result
}

// CheckRAM checks available system RAM.
func CheckRAM(minGB uint64) PreflightResult {
	result := PreflightResult{Name: "RAM"}

	totalGB := getSystemRAMGB()
	if totalGB == 0 {
		result.OK = false
		result.Error = "unable to detect system RAM"
		return result
	}

	if totalGB < minGB {
		result.OK = false
		result.Error = fmt.Sprintf("%d GB available, %d GB minimum", totalGB, minGB)
		return result
	}

	result.OK = true
	result.Detail = fmt.Sprintf("%d GB available (%d GB minimum)", totalGB, minGB)
	return result
}

// getSystemRAMGB returns total system RAM in GB.
func getSystemRAMGB() uint64 {
	switch runtime.GOOS {
	case "linux":
		return getLinuxRAMGB()
	case "darwin":
		return getDarwinRAMGB()
	default:
		return 0
	}
}

// getLinuxRAMGB reads total RAM from /proc/meminfo.
func getLinuxRAMGB() uint64 {
	out, err := exec.Command("grep", "MemTotal", "/proc/meminfo").Output()
	if err != nil {
		return 0
	}
	// Format: "MemTotal:       16384000 kB"
	fields := strings.Fields(string(out))
	if len(fields) < 2 {
		return 0
	}
	kb, err := strconv.ParseUint(fields[1], 10, 64)
	if err != nil {
		return 0
	}
	return kb / (1024 * 1024)
}

// getDarwinRAMGB reads total RAM via sysctl.
func getDarwinRAMGB() uint64 {
	out, err := exec.Command("sysctl", "-n", "hw.memsize").Output()
	if err != nil {
		return 0
	}
	bytes, err := strconv.ParseUint(strings.TrimSpace(string(out)), 10, 64)
	if err != nil {
		return 0
	}
	return bytes / (1024 * 1024 * 1024)
}

// RunAllPreflights runs all preflight checks and returns the results.
func RunAllPreflights(projectDir string) []PreflightResult {
	osInfo := DetectOS()

	results := []PreflightResult{
		CheckDocker(),
		CheckDockerCompose(),
		CheckDiskSpace(projectDir, 15),
		CheckRAM(4),
		{
			Name:   "Operating system",
			OK:     true,
			Detail: fmt.Sprintf("%s/%s", osInfo.OS, osInfo.Arch),
		},
	}

	// Linux: add Docker Engine awareness when Desktop is detected.
	if runtime.GOOS == "linux" {
		dockerType := DetectDockerType()
		if dockerType == "desktop" {
			if IsDockerEngineRunning() {
				results = append(results, PreflightResult{
					Name:   "Docker Engine",
					OK:     true,
					Detail: "running (GPU capable)",
				})
			} else if IsDockerEngineInstalled() {
				results = append(results, PreflightResult{
					Name:  "Docker Engine",
					OK:    false,
					Error: "installed but not running. Start with: sudo systemctl start docker",
				})
			} else {
				results = append(results, PreflightResult{
					Name:  "Docker Engine",
					OK:    false,
					Error: "not installed (required for GPU passthrough alongside Docker Desktop)",
				})
			}
		}
	}

	// WSL2 path warning.
	if osInfo.WSL2 {
		cwd := projectDir
		if strings.HasPrefix(cwd, "/mnt/") {
			results = append(results, PreflightResult{
				Name:  "WSL2 path",
				OK:    false,
				Error: "Running from Windows filesystem path. Clone to ~/projects/ for better I/O performance.",
			})
		}
	}

	return results
}

// AllPreflightsPassed checks if all preflight results are OK.
func AllPreflightsPassed(results []PreflightResult) bool {
	for _, r := range results {
		if !r.OK {
			return false
		}
	}
	return true
}

// DetectDockerType returns "engine", "desktop", or "unknown" based on the Docker installation.
// Note: This checks the DEFAULT docker context. Even if Desktop is detected,
// Docker Engine may be running alongside it (check IsDockerEngineRunning).
func DetectDockerType() string {
	if runtime.GOOS == "darwin" || runtime.GOOS == "windows" {
		return "desktop"
	}

	// Linux: check for Docker Desktop indicators.

	// Indicator 1: Docker Desktop's containerd socket.
	if _, err := os.Stat("/var/run/desktop-containerd/containerd.sock"); err == nil {
		return "desktop"
	}

	// Indicator 2: Docker Desktop's data directory.
	home, _ := os.UserHomeDir()
	if home != "" {
		if _, err := os.Stat(home + "/.docker/desktop"); err == nil {
			return "desktop"
		}
	}

	// Indicator 3: "docker info" contains "Desktop" in the server name or context.
	// Use bare exec.Command here (not DockerCommand) to check the DEFAULT context.
	out, err := exec.Command("docker", "info", "--format", "{{.Name}} {{.ServerVersion}} {{.OperatingSystem}}").CombinedOutput()
	if err == nil {
		info := strings.ToLower(string(out))
		if strings.Contains(info, "desktop") {
			return "desktop"
		}
	}

	// Indicator 4: Docker context is "desktop-linux".
	ctxOut, err := exec.Command("docker", "context", "show").CombinedOutput()
	if err == nil {
		ctx := strings.TrimSpace(string(ctxOut))
		if strings.Contains(strings.ToLower(ctx), "desktop") {
			return "desktop"
		}
	}

	// If Docker daemon responds, it's Docker Engine.
	_, err = exec.Command("docker", "info").CombinedOutput()
	if err == nil {
		return "engine"
	}

	return "unknown"
}

// DetectLinuxDistro returns the Linux distribution ID from /etc/os-release.
// Returns "fedora", "ubuntu", "debian", "arch", "rhel", "centos", or "unknown".
func DetectLinuxDistro() string {
	if runtime.GOOS != "linux" {
		return "unknown"
	}

	data, err := os.ReadFile("/etc/os-release")
	if err != nil {
		return "unknown"
	}

	for _, line := range strings.Split(string(data), "\n") {
		if strings.HasPrefix(line, "ID=") {
			id := strings.TrimPrefix(line, "ID=")
			id = strings.Trim(id, `"'`)
			id = strings.ToLower(id)
			switch id {
			case "fedora", "ubuntu", "debian", "arch", "rhel", "centos":
				return id
			}
			// ID_LIKE fallback handled below.
		}
	}

	// Try ID_LIKE for derivatives (e.g., Linux Mint -> ubuntu, Manjaro -> arch).
	for _, line := range strings.Split(string(data), "\n") {
		if strings.HasPrefix(line, "ID_LIKE=") {
			like := strings.TrimPrefix(line, "ID_LIKE=")
			like = strings.Trim(like, `"'`)
			for _, part := range strings.Fields(strings.ToLower(like)) {
				switch part {
				case "fedora", "ubuntu", "debian", "arch", "rhel":
					return part
				}
			}
		}
	}

	return "unknown"
}
