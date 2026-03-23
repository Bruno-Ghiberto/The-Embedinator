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
