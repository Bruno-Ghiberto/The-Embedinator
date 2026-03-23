package engine

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestDefaultConfig(t *testing.T) {
	cfg := DefaultConfig()

	t.Run("version is set", func(t *testing.T) {
		if cfg.Version != "1" {
			t.Errorf("Version = %q, want %q", cfg.Version, "1")
		}
	})

	t.Run("timestamps are populated", func(t *testing.T) {
		if cfg.CreatedAt == "" {
			t.Error("CreatedAt is empty")
		}
		if cfg.UpdatedAt == "" {
			t.Error("UpdatedAt is empty")
		}
	})

	t.Run("ollama defaults", func(t *testing.T) {
		if cfg.Ollama.Mode != "docker" {
			t.Errorf("Ollama.Mode = %q, want %q", cfg.Ollama.Mode, "docker")
		}
		if len(cfg.Ollama.Models.LLM) == 0 {
			t.Error("Ollama.Models.LLM is empty, want at least one model")
		}
		if cfg.Ollama.Models.LLM[0] != "qwen2.5:7b" {
			t.Errorf("Ollama.Models.LLM[0] = %q, want %q", cfg.Ollama.Models.LLM[0], "qwen2.5:7b")
		}
		if len(cfg.Ollama.Models.Embedding) == 0 {
			t.Error("Ollama.Models.Embedding is empty, want at least one model")
		}
		if cfg.Ollama.Models.Embedding[0] != "nomic-embed-text" {
			t.Errorf("Ollama.Models.Embedding[0] = %q, want %q", cfg.Ollama.Models.Embedding[0], "nomic-embed-text")
		}
	})

	t.Run("GPU defaults to none", func(t *testing.T) {
		if cfg.GPU.Profile != "none" {
			t.Errorf("GPU.Profile = %q, want %q", cfg.GPU.Profile, "none")
		}
		if !cfg.GPU.AutoDetected {
			t.Error("GPU.AutoDetected = false, want true")
		}
	})

	t.Run("port defaults", func(t *testing.T) {
		if cfg.Ports.Frontend != 3000 {
			t.Errorf("Ports.Frontend = %d, want 3000", cfg.Ports.Frontend)
		}
		if cfg.Ports.Backend != 8000 {
			t.Errorf("Ports.Backend = %d, want 8000", cfg.Ports.Backend)
		}
		if cfg.Ports.Qdrant != 6333 {
			t.Errorf("Ports.Qdrant = %d, want 6333", cfg.Ports.Qdrant)
		}
		if cfg.Ports.QdrantGRPC != 6334 {
			t.Errorf("Ports.QdrantGRPC = %d, want 6334", cfg.Ports.QdrantGRPC)
		}
		if cfg.Ports.Ollama != 11434 {
			t.Errorf("Ports.Ollama = %d, want 11434", cfg.Ports.Ollama)
		}
	})

	t.Run("dev mode off by default", func(t *testing.T) {
		if cfg.DevMode {
			t.Error("DevMode = true, want false")
		}
	})

	t.Run("providers all false by default", func(t *testing.T) {
		if cfg.Providers.OpenAI {
			t.Error("Providers.OpenAI = true, want false")
		}
		if cfg.Providers.Anthropic {
			t.Error("Providers.Anthropic = true, want false")
		}
		if cfg.Providers.OpenRouter {
			t.Error("Providers.OpenRouter = true, want false")
		}
	})
}

func TestWriteAndReadConfig(t *testing.T) {
	tmpDir := t.TempDir()
	configPath := filepath.Join(tmpDir, "config.yaml")
	cfg := DefaultConfig()
	cfg.GPU.Profile = "nvidia"
	cfg.Ports.Frontend = 4000
	cfg.Providers.OpenAI = true

	t.Run("write config", func(t *testing.T) {
		err := WriteConfig(configPath, cfg)
		if err != nil {
			t.Fatalf("WriteConfig: %v", err)
		}

		// Verify the file exists.
		if _, err := os.Stat(configPath); err != nil {
			t.Fatalf("config file not created: %v", err)
		}
	})

	t.Run("file has header comment", func(t *testing.T) {
		data, err := os.ReadFile(configPath)
		if err != nil {
			t.Fatalf("ReadFile: %v", err)
		}
		if !strings.HasPrefix(string(data), "# config.yaml") {
			t.Error("config file does not start with header comment")
		}
	})

	t.Run("read config roundtrip", func(t *testing.T) {
		got, err := ReadConfig(configPath)
		if err != nil {
			t.Fatalf("ReadConfig: %v", err)
		}

		if got.GPU.Profile != "nvidia" {
			t.Errorf("GPU.Profile = %q, want %q", got.GPU.Profile, "nvidia")
		}
		if got.Ports.Frontend != 4000 {
			t.Errorf("Ports.Frontend = %d, want 4000", got.Ports.Frontend)
		}
		if !got.Providers.OpenAI {
			t.Error("Providers.OpenAI = false, want true")
		}
		if got.Ollama.Mode != "docker" {
			t.Errorf("Ollama.Mode = %q, want %q", got.Ollama.Mode, "docker")
		}
	})

	t.Run("write updates UpdatedAt", func(t *testing.T) {
		got, _ := ReadConfig(configPath)
		// UpdatedAt should differ from the original since WriteConfig stamps it.
		// We cannot guarantee a time difference in fast tests, but it should be non-empty.
		if got.UpdatedAt == "" {
			t.Error("UpdatedAt is empty after write")
		}
	})

	t.Run("temp file is cleaned up on success", func(t *testing.T) {
		tmpPath := configPath + ".tmp"
		if _, err := os.Stat(tmpPath); err == nil {
			t.Error("temp file still exists after successful write")
		}
	})
}

func TestReadConfig_Errors(t *testing.T) {
	t.Run("file does not exist", func(t *testing.T) {
		_, err := ReadConfig("/nonexistent/path/config.yaml")
		if err == nil {
			t.Error("ReadConfig with nonexistent path returned nil error")
		}
	})

	t.Run("invalid YAML", func(t *testing.T) {
		tmpDir := t.TempDir()
		badPath := filepath.Join(tmpDir, "bad.yaml")
		if err := os.WriteFile(badPath, []byte("{{invalid yaml content"), 0644); err != nil {
			t.Fatalf("failed to write bad yaml: %v", err)
		}

		_, err := ReadConfig(badPath)
		if err == nil {
			t.Error("ReadConfig with invalid YAML returned nil error")
		}
		if !strings.Contains(err.Error(), "parse config") {
			t.Errorf("error = %q, want substring %q", err.Error(), "parse config")
		}
	})
}

func TestWriteConfig_ErrorOnBadPath(t *testing.T) {
	cfg := DefaultConfig()
	err := WriteConfig("/nonexistent/directory/config.yaml", cfg)
	if err == nil {
		t.Error("WriteConfig with nonexistent directory returned nil error")
	}
}

func TestValidateConfig(t *testing.T) {
	validConfig := func() Config {
		cfg := DefaultConfig()
		return cfg
	}

	tests := []struct {
		name      string
		modify    func(*Config)
		wantErr   bool
		errSubstr string
	}{
		{
			name:    "valid default config",
			modify:  func(c *Config) {},
			wantErr: false,
		},
		{
			name:    "ollama mode docker is valid",
			modify:  func(c *Config) { c.Ollama.Mode = "docker" },
			wantErr: false,
		},
		{
			name:    "ollama mode local is valid",
			modify:  func(c *Config) { c.Ollama.Mode = "local" },
			wantErr: false,
		},
		{
			name:   "ollama mode remote with URL is valid",
			modify: func(c *Config) { c.Ollama.Mode = "remote"; c.Ollama.RemoteURL = "http://10.0.0.5:11434" },
			wantErr: false,
		},
		{
			name:      "invalid ollama mode",
			modify:    func(c *Config) { c.Ollama.Mode = "invalid" },
			wantErr:   true,
			errSubstr: "invalid ollama.mode",
		},
		{
			name:      "remote mode without URL",
			modify:    func(c *Config) { c.Ollama.Mode = "remote"; c.Ollama.RemoteURL = "" },
			wantErr:   true,
			errSubstr: "remote_url is required",
		},
		{
			name:      "empty LLM models",
			modify:    func(c *Config) { c.Ollama.Models.LLM = nil },
			wantErr:   true,
			errSubstr: "at least one LLM model",
		},
		{
			name:      "empty embedding models",
			modify:    func(c *Config) { c.Ollama.Models.Embedding = nil },
			wantErr:   true,
			errSubstr: "at least one embedding model",
		},
		{
			name:      "invalid GPU profile",
			modify:    func(c *Config) { c.GPU.Profile = "apu" },
			wantErr:   true,
			errSubstr: "invalid gpu.profile",
		},
		{
			name:    "GPU profile nvidia is valid",
			modify:  func(c *Config) { c.GPU.Profile = "nvidia" },
			wantErr: false,
		},
		{
			name:    "GPU profile amd is valid",
			modify:  func(c *Config) { c.GPU.Profile = "amd" },
			wantErr: false,
		},
		{
			name:    "GPU profile intel is valid",
			modify:  func(c *Config) { c.GPU.Profile = "intel" },
			wantErr: false,
		},
		{
			name:    "GPU profile none is valid",
			modify:  func(c *Config) { c.GPU.Profile = "none" },
			wantErr: false,
		},
		{
			name:      "frontend port below range",
			modify:    func(c *Config) { c.Ports.Frontend = 80 },
			wantErr:   true,
			errSubstr: "ports.frontend",
		},
		{
			name:      "frontend port above range",
			modify:    func(c *Config) { c.Ports.Frontend = 70000 },
			wantErr:   true,
			errSubstr: "ports.frontend",
		},
		{
			name:      "backend port below range",
			modify:    func(c *Config) { c.Ports.Backend = 0 },
			wantErr:   true,
			errSubstr: "ports.backend",
		},
		{
			name:      "qdrant port above range",
			modify:    func(c *Config) { c.Ports.Qdrant = 100000 },
			wantErr:   true,
			errSubstr: "ports.qdrant",
		},
		{
			name:      "qdrant grpc port below range",
			modify:    func(c *Config) { c.Ports.QdrantGRPC = 500 },
			wantErr:   true,
			errSubstr: "ports.qdrant_grpc",
		},
		{
			name:      "ollama port below range",
			modify:    func(c *Config) { c.Ports.Ollama = 1023 },
			wantErr:   true,
			errSubstr: "ports.ollama",
		},
		{
			name:    "all ports at boundary minimum",
			modify: func(c *Config) {
				c.Ports.Frontend = 1024
				c.Ports.Backend = 1024
				c.Ports.Qdrant = 1024
				c.Ports.QdrantGRPC = 1024
				c.Ports.Ollama = 1024
			},
			wantErr: false,
		},
		{
			name:    "all ports at boundary maximum",
			modify: func(c *Config) {
				c.Ports.Frontend = 65535
				c.Ports.Backend = 65535
				c.Ports.Qdrant = 65535
				c.Ports.QdrantGRPC = 65535
				c.Ports.Ollama = 65535
			},
			wantErr: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			cfg := validConfig()
			tt.modify(&cfg)
			err := ValidateConfig(cfg)

			if tt.wantErr && err == nil {
				t.Error("ValidateConfig returned nil, want error")
			}
			if !tt.wantErr && err != nil {
				t.Errorf("ValidateConfig returned error: %v", err)
			}
			if tt.wantErr && err != nil && tt.errSubstr != "" {
				if !strings.Contains(err.Error(), tt.errSubstr) {
					t.Errorf("error = %q, want substring %q", err.Error(), tt.errSubstr)
				}
			}
		})
	}
}

func TestConfigExists(t *testing.T) {
	t.Run("existing file returns true", func(t *testing.T) {
		tmpDir := t.TempDir()
		path := filepath.Join(tmpDir, "config.yaml")
		if err := os.WriteFile(path, []byte("version: 1"), 0644); err != nil {
			t.Fatalf("write temp: %v", err)
		}
		if !ConfigExists(path) {
			t.Error("ConfigExists returned false for existing file")
		}
	})

	t.Run("nonexistent file returns false", func(t *testing.T) {
		if ConfigExists("/nonexistent/config.yaml") {
			t.Error("ConfigExists returned true for nonexistent file")
		}
	})
}

func TestWriteConfig_AtomicWrite(t *testing.T) {
	tmpDir := t.TempDir()
	configPath := filepath.Join(tmpDir, "config.yaml")
	cfg := DefaultConfig()

	// Write once.
	if err := WriteConfig(configPath, cfg); err != nil {
		t.Fatalf("first WriteConfig: %v", err)
	}

	// Write again (overwrite). Should succeed without leaving temp files.
	cfg.GPU.Profile = "amd"
	if err := WriteConfig(configPath, cfg); err != nil {
		t.Fatalf("second WriteConfig: %v", err)
	}

	got, err := ReadConfig(configPath)
	if err != nil {
		t.Fatalf("ReadConfig after overwrite: %v", err)
	}
	if got.GPU.Profile != "amd" {
		t.Errorf("GPU.Profile = %q after overwrite, want %q", got.GPU.Profile, "amd")
	}
}
