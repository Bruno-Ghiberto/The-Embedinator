package engine

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os/exec"
	"runtime"
	"strings"
	"time"
)

// OllamaDetection holds the result of local Ollama detection.
type OllamaDetection struct {
	Running      bool
	APIReachable bool
	Version      string
	Models       []string
}

// DetectLocalOllama checks if Ollama is running locally and probes its API.
func DetectLocalOllama() OllamaDetection {
	result := OllamaDetection{}

	// Step 1: Check if an Ollama process is running.
	if !isOllamaProcessRunning() {
		return result
	}
	result.Running = true

	// Step 2: Probe the API.
	client := &http.Client{Timeout: 2 * time.Second}
	resp, err := client.Get("http://localhost:11434/api/tags")
	if err != nil {
		return result
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return result
	}
	result.APIReachable = true

	// Extract version from header.
	result.Version = resp.Header.Get("x-ollama-version")

	// Parse model list.
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return result
	}

	var tagsResp struct {
		Models []struct {
			Name string `json:"name"`
		} `json:"models"`
	}
	if err := json.Unmarshal(body, &tagsResp); err == nil {
		for _, m := range tagsResp.Models {
			result.Models = append(result.Models, m.Name)
		}
	}

	return result
}

// isOllamaProcessRunning checks if an Ollama process is active.
func isOllamaProcessRunning() bool {
	switch runtime.GOOS {
	case "linux", "darwin":
		// Try pgrep first, then pidof.
		if err := exec.Command("pgrep", "-x", "ollama").Run(); err == nil {
			return true
		}
		if err := exec.Command("pidof", "ollama").Run(); err == nil {
			return true
		}
		return false
	case "windows":
		out, err := exec.Command("tasklist", "/FI", "IMAGENAME eq ollama.exe", "/FO", "CSV", "/NH").Output()
		if err != nil {
			return false
		}
		return strings.Contains(string(out), "ollama.exe")
	default:
		return false
	}
}

// PullModel pulls a model via docker compose exec or local ollama.
func PullModel(projectDir, model string, useLocal bool) error {
	if useLocal {
		return pullModelLocal(model)
	}
	return pullModelDocker(projectDir, model)
}

func pullModelLocal(model string) error {
	ollamaPath, err := exec.LookPath("ollama")
	if err != nil {
		return fmt.Errorf("ollama CLI not found in PATH: %w", err)
	}

	cmd := exec.Command(ollamaPath, "pull", model)
	cmd.Stdout = nil
	cmd.Stderr = nil
	return cmd.Run()
}

func pullModelDocker(projectDir, model string) error {
	cmd := DockerCommand("compose", "exec", "ollama", "ollama", "pull", model)
	cmd.Dir = projectDir
	return cmd.Run()
}

// ListLocalModels returns the models available in local Ollama.
func ListLocalModels() ([]string, error) {
	out, err := exec.Command("ollama", "list").Output()
	if err != nil {
		return nil, fmt.Errorf("ollama list: %w", err)
	}

	var models []string
	lines := strings.Split(string(out), "\n")
	for i, line := range lines {
		if i == 0 {
			continue // skip header
		}
		fields := strings.Fields(line)
		if len(fields) > 0 {
			models = append(models, fields[0])
		}
	}
	return models, nil
}

// ListDockerModels returns the models available in Docker Ollama.
func ListDockerModels(projectDir string) ([]string, error) {
	cmd := DockerCommand("compose", "exec", "ollama", "ollama", "list")
	cmd.Dir = projectDir
	out, err := cmd.Output()
	if err != nil {
		return nil, fmt.Errorf("docker ollama list: %w", err)
	}

	var models []string
	lines := strings.Split(string(out), "\n")
	for i, line := range lines {
		if i == 0 {
			continue
		}
		fields := strings.Fields(line)
		if len(fields) > 0 {
			models = append(models, fields[0])
		}
	}
	return models, nil
}

// OllamaConflictState describes the binding state of host port 11434.
type OllamaConflictState int

const (
	// OllamaPortFree indicates nothing is bound to :11434 — safe to start.
	OllamaPortFree OllamaConflictState = iota
	// OllamaPortOwnedByDockerStack indicates the embedinator-ollama container
	// holds :11434 — safe, this is the expected running state.
	OllamaPortOwnedByDockerStack
	// OllamaPortOwnedByHostDaemon indicates a host-native ollama daemon is
	// running (CONFLICT) — must be stopped before starting The Embedinator.
	OllamaPortOwnedByHostDaemon
	// OllamaPortOwnedByUnknown indicates an unknown process holds :11434
	// (CONFLICT) — user must investigate and stop it.
	OllamaPortOwnedByUnknown
)

// OllamaConflictResult reports the state of host port 11434 and how to
// remediate any conflict so Docker Ollama can bind successfully.
type OllamaConflictResult struct {
	State          OllamaConflictState
	HostBinaryPath string // Informational: path to host `ollama` CLI if installed.
	OwnerProcess   string // Describes the owning process when conflict present.
	Message        string // Short human-readable summary.
	Remediation    string // Multi-line remediation instructions.
}

// HasConflict returns true when the host state blocks Docker Ollama from
// binding port 11434.
func (r OllamaConflictResult) HasConflict() bool {
	return r.State == OllamaPortOwnedByHostDaemon || r.State == OllamaPortOwnedByUnknown
}

// CheckOllamaPortConflict inspects port 11434 and classifies who owns it.
// The Embedinator requires Docker Ollama exclusively, so any binding by a
// non-Docker process is reported as a conflict with remediation instructions.
//
// Detection order:
//  1. Port free               -> OllamaPortFree
//  2. Our embedinator-ollama  -> OllamaPortOwnedByDockerStack
//  3. Host `ollama serve` pid -> OllamaPortOwnedByHostDaemon (CONFLICT)
//  4. Anything else           -> OllamaPortOwnedByUnknown    (CONFLICT)
func CheckOllamaPortConflict() OllamaConflictResult {
	result := OllamaConflictResult{}

	// Informational: record the host `ollama` CLI path if installed.
	// Presence of the CLI binary is harmless on its own — only the daemon matters.
	if path, err := exec.LookPath("ollama"); err == nil {
		result.HostBinaryPath = path
	}

	// If we can listen on :11434, the port is free.
	if ScanPort(11434) {
		result.State = OllamaPortFree
		result.Message = "Port 11434 is free"
		return result
	}

	// Port is bound. Case 1: is it our Docker Ollama container?
	if dockerOllamaContainerRunning() {
		result.State = OllamaPortOwnedByDockerStack
		result.Message = "Port 11434 is bound by the embedinator-ollama container (OK)"
		return result
	}

	// Case 2: is a host-native `ollama serve` process running?
	if hostOllamaServeRunning() {
		result.State = OllamaPortOwnedByHostDaemon
		result.OwnerProcess = "ollama (host daemon)"
		result.Message = "Host-native Ollama daemon is running on port 11434"
		result.Remediation = hostOllamaRemediation()
		return result
	}

	// Case 3: something else owns the port.
	owner := identifyPortOwner(11434)
	result.State = OllamaPortOwnedByUnknown
	result.OwnerProcess = owner
	result.Message = fmt.Sprintf("Port 11434 is bound by an unknown process: %s", owner)
	result.Remediation = "Stop whatever is listening on port 11434 before starting The Embedinator."
	return result
}

// dockerOllamaContainerRunning returns true if a container named
// embedinator-ollama is running on the current Docker context.
func dockerOllamaContainerRunning() bool {
	cmd := DockerCommand("ps", "--filter", "name=embedinator-ollama",
		"--filter", "status=running", "--format", "{{.Names}}")
	out, err := cmd.Output()
	if err != nil {
		return false
	}
	return strings.TrimSpace(string(out)) != ""
}

// hostOllamaServeRunning checks specifically for a host-native `ollama serve`
// daemon process. This is stricter than isOllamaProcessRunning because
// momentary `ollama list`/`ollama pull` CLI invocations must not trigger a
// false positive conflict.
func hostOllamaServeRunning() bool {
	switch runtime.GOOS {
	case "linux", "darwin":
		// pgrep -f matches the full command line, catching both manual
		// `ollama serve` and systemd-managed daemons.
		if err := exec.Command("pgrep", "-f", "ollama serve").Run(); err == nil {
			return true
		}
		return false
	case "windows":
		// On Windows, ollama.exe is the daemon when started as a service.
		out, err := exec.Command("tasklist", "/FI", "IMAGENAME eq ollama.exe", "/FO", "CSV", "/NH").Output()
		if err != nil {
			return false
		}
		return strings.Contains(string(out), "ollama.exe")
	default:
		return false
	}
}

// hostOllamaRemediation returns user-facing instructions to stop and disable
// a conflicting host-native Ollama daemon.
func hostOllamaRemediation() string {
	return strings.Join([]string{
		"The Embedinator runs Ollama exclusively in Docker.",
		"A host-native Ollama daemon is currently holding port 11434.",
		"",
		"Stop and disable the host daemon:",
		"  sudo systemctl stop ollama 2>/dev/null || pkill -f 'ollama serve'",
		"  sudo systemctl disable ollama 2>/dev/null || true",
		"",
		"The host `ollama` CLI binary is fine to keep — only the daemon",
		"must be stopped. After stopping, re-run this command.",
	}, "\n")
}

// identifyPortOwner attempts to describe what is listening on a TCP port.
// Falls back through ss, lsof, and finally "unknown" when neither is present.
func identifyPortOwner(port int) string {
	// Try ss first — part of iproute2, preinstalled on most Linux distros.
	if out, err := exec.Command("ss", "-tlnH", fmt.Sprintf("sport = :%d", port)).Output(); err == nil {
		if s := strings.TrimSpace(string(out)); s != "" {
			return s
		}
	}
	// Fallback to lsof.
	if out, err := exec.Command("lsof", fmt.Sprintf("-iTCP:%d", port),
		"-sTCP:LISTEN", "-n", "-P").Output(); err == nil {
		if s := strings.TrimSpace(string(out)); s != "" {
			return s
		}
	}
	return "unknown"
}
