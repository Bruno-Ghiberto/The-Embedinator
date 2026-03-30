package engine

import (
	"bufio"
	"crypto/rand"
	"encoding/base64"
	"fmt"
	"os"
	"strings"

	"github.com/Bruno-Ghiberto/The-Embedinator/cli/internal/version"
)

// GenerateFernetKey produces a valid Fernet key: 32 random bytes, URL-safe
// base64-encoded (44 characters). This matches Python's cryptography.fernet
// Fernet.generate_key() output.
func GenerateFernetKey() string {
	key := make([]byte, 32)
	if _, err := rand.Read(key); err != nil {
		// crypto/rand should never fail; panic is appropriate here.
		panic(fmt.Sprintf("crypto/rand failed: %v", err))
	}
	return base64.URLEncoding.EncodeToString(key)
}

// ManagedEnvVars are the .env keys managed by the TUI.
var ManagedEnvVars = []string{
	"EMBEDINATOR_VERSION",
	"EMBEDINATOR_PORT_FRONTEND",
	"EMBEDINATOR_PORT_BACKEND",
	"EMBEDINATOR_PORT_QDRANT",
	"EMBEDINATOR_PORT_QDRANT_GRPC",
	"EMBEDINATOR_PORT_OLLAMA",
	"EMBEDINATOR_GPU",
	"OLLAMA_MODELS",
	"EMBEDINATOR_FERNET_KEY",
	"CORS_ORIGINS",
	"EMBEDINATOR_USE_LOCAL_OLLAMA",
}

// GenerateDotEnv creates or updates a .env file from Config.
// It preserves unmanaged variables.
func GenerateDotEnv(envPath, examplePath string, cfg Config, fernetKey string) error {
	managed := buildManagedMap(cfg, fernetKey)

	existing := make(map[string]bool)
	var lines []string

	// If .env exists, read and update managed vars in place.
	if data, err := os.ReadFile(envPath); err == nil {
		scanner := bufio.NewScanner(strings.NewReader(string(data)))
		for scanner.Scan() {
			line := scanner.Text()
			trimmed := strings.TrimSpace(line)

			// Comments and blank lines pass through.
			if trimmed == "" || strings.HasPrefix(trimmed, "#") {
				lines = append(lines, line)
				continue
			}

			parts := strings.SplitN(trimmed, "=", 2)
			if len(parts) < 2 {
				lines = append(lines, line)
				continue
			}
			key := strings.TrimSpace(parts[0])

			if val, ok := managed[key]; ok {
				lines = append(lines, fmt.Sprintf("%s=%s", key, val))
				existing[key] = true
			} else {
				lines = append(lines, line)
			}
		}
	} else if examplePath != "" {
		// Copy from .env.example as the base.
		if data, err := os.ReadFile(examplePath); err == nil {
			scanner := bufio.NewScanner(strings.NewReader(string(data)))
			for scanner.Scan() {
				line := scanner.Text()
				trimmed := strings.TrimSpace(line)

				if trimmed == "" || strings.HasPrefix(trimmed, "#") {
					lines = append(lines, line)
					continue
				}

				parts := strings.SplitN(trimmed, "=", 2)
				if len(parts) < 2 {
					lines = append(lines, line)
					continue
				}
				key := strings.TrimSpace(parts[0])

				if val, ok := managed[key]; ok {
					lines = append(lines, fmt.Sprintf("%s=%s", key, val))
					existing[key] = true
				} else {
					lines = append(lines, line)
				}
			}
		}
	}

	// Append any managed keys not yet in the file.
	for _, key := range ManagedEnvVars {
		if !existing[key] {
			if val, ok := managed[key]; ok && val != "" {
				lines = append(lines, fmt.Sprintf("%s=%s", key, val))
			}
		}
	}

	// Atomic write.
	content := strings.Join(lines, "\n") + "\n"
	tmpPath := envPath + ".tmp"
	if err := os.WriteFile(tmpPath, []byte(content), 0644); err != nil {
		return fmt.Errorf("write .env temp: %w", err)
	}
	if err := os.Rename(tmpPath, envPath); err != nil {
		os.Remove(tmpPath)
		return fmt.Errorf("rename .env: %w", err)
	}

	return nil
}

// buildManagedMap creates a key-value map from Config for .env generation.
func buildManagedMap(cfg Config, fernetKey string) map[string]string {
	m := map[string]string{
		"EMBEDINATOR_VERSION":         version.Version,
		"EMBEDINATOR_PORT_FRONTEND":   fmt.Sprintf("%d", cfg.Ports.Frontend),
		"EMBEDINATOR_PORT_BACKEND":    fmt.Sprintf("%d", cfg.Ports.Backend),
		"EMBEDINATOR_PORT_QDRANT":     fmt.Sprintf("%d", cfg.Ports.Qdrant),
		"EMBEDINATOR_PORT_QDRANT_GRPC": fmt.Sprintf("%d", cfg.Ports.QdrantGRPC),
		"EMBEDINATOR_PORT_OLLAMA":     fmt.Sprintf("%d", cfg.Ports.Ollama),
		"EMBEDINATOR_GPU":             cfg.GPU.Profile,
	}

	// Build OLLAMA_MODELS from both lists.
	var models []string
	models = append(models, cfg.Ollama.Models.LLM...)
	models = append(models, cfg.Ollama.Models.Embedding...)
	m["OLLAMA_MODELS"] = strings.Join(models, ",")

	if fernetKey != "" {
		m["EMBEDINATOR_FERNET_KEY"] = fernetKey
	}

	if cfg.Ollama.Mode == "local" {
		m["EMBEDINATOR_USE_LOCAL_OLLAMA"] = "1"
	}

	return m
}

// ReadDotEnvValue reads a single value from a .env file.
func ReadDotEnvValue(envPath, key string) (string, error) {
	data, err := os.ReadFile(envPath)
	if err != nil {
		return "", err
	}

	scanner := bufio.NewScanner(strings.NewReader(string(data)))
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if strings.HasPrefix(line, "#") || line == "" {
			continue
		}
		parts := strings.SplitN(line, "=", 2)
		if len(parts) == 2 && strings.TrimSpace(parts[0]) == key {
			return strings.TrimSpace(parts[1]), nil
		}
	}

	return "", fmt.Errorf("key %q not found in %s", key, envPath)
}
