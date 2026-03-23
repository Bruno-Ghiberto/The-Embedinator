package engine

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestBuildManagedMap(t *testing.T) {
	cfg := DefaultConfig()

	t.Run("ports are formatted as strings", func(t *testing.T) {
		m := buildManagedMap(cfg, "")
		if m["EMBEDINATOR_PORT_FRONTEND"] != "3000" {
			t.Errorf("FRONTEND = %q, want %q", m["EMBEDINATOR_PORT_FRONTEND"], "3000")
		}
		if m["EMBEDINATOR_PORT_BACKEND"] != "8000" {
			t.Errorf("BACKEND = %q, want %q", m["EMBEDINATOR_PORT_BACKEND"], "8000")
		}
		if m["EMBEDINATOR_PORT_QDRANT"] != "6333" {
			t.Errorf("QDRANT = %q, want %q", m["EMBEDINATOR_PORT_QDRANT"], "6333")
		}
		if m["EMBEDINATOR_PORT_QDRANT_GRPC"] != "6334" {
			t.Errorf("QDRANT_GRPC = %q, want %q", m["EMBEDINATOR_PORT_QDRANT_GRPC"], "6334")
		}
		if m["EMBEDINATOR_PORT_OLLAMA"] != "11434" {
			t.Errorf("OLLAMA = %q, want %q", m["EMBEDINATOR_PORT_OLLAMA"], "11434")
		}
	})

	t.Run("GPU profile is passed through", func(t *testing.T) {
		m := buildManagedMap(cfg, "")
		if m["EMBEDINATOR_GPU"] != "none" {
			t.Errorf("GPU = %q, want %q", m["EMBEDINATOR_GPU"], "none")
		}
	})

	t.Run("OLLAMA_MODELS joins LLM and embedding", func(t *testing.T) {
		m := buildManagedMap(cfg, "")
		got := m["OLLAMA_MODELS"]
		// Default: qwen2.5:7b + nomic-embed-text
		if !strings.Contains(got, "qwen2.5:7b") {
			t.Errorf("OLLAMA_MODELS = %q, missing %q", got, "qwen2.5:7b")
		}
		if !strings.Contains(got, "nomic-embed-text") {
			t.Errorf("OLLAMA_MODELS = %q, missing %q", got, "nomic-embed-text")
		}
	})

	t.Run("fernet key included when provided", func(t *testing.T) {
		m := buildManagedMap(cfg, "my-secret-key")
		if m["EMBEDINATOR_FERNET_KEY"] != "my-secret-key" {
			t.Errorf("FERNET_KEY = %q, want %q", m["EMBEDINATOR_FERNET_KEY"], "my-secret-key")
		}
	})

	t.Run("fernet key omitted when empty", func(t *testing.T) {
		m := buildManagedMap(cfg, "")
		if _, ok := m["EMBEDINATOR_FERNET_KEY"]; ok {
			t.Error("FERNET_KEY should not be in map when empty")
		}
	})

	t.Run("local ollama sets USE_LOCAL_OLLAMA", func(t *testing.T) {
		localCfg := cfg
		localCfg.Ollama.Mode = "local"
		m := buildManagedMap(localCfg, "")
		if m["EMBEDINATOR_USE_LOCAL_OLLAMA"] != "1" {
			t.Errorf("USE_LOCAL_OLLAMA = %q, want %q", m["EMBEDINATOR_USE_LOCAL_OLLAMA"], "1")
		}
	})

	t.Run("docker mode does not set USE_LOCAL_OLLAMA", func(t *testing.T) {
		m := buildManagedMap(cfg, "")
		if _, ok := m["EMBEDINATOR_USE_LOCAL_OLLAMA"]; ok {
			t.Error("USE_LOCAL_OLLAMA should not be set for docker mode")
		}
	})
}

func TestGenerateDotEnv_FromScratch(t *testing.T) {
	tmpDir := t.TempDir()
	envPath := filepath.Join(tmpDir, ".env")
	cfg := DefaultConfig()

	err := GenerateDotEnv(envPath, "", cfg, "test-fernet-key")
	if err != nil {
		t.Fatalf("GenerateDotEnv: %v", err)
	}

	data, err := os.ReadFile(envPath)
	if err != nil {
		t.Fatalf("ReadFile: %v", err)
	}
	content := string(data)

	// All managed vars should be present.
	for _, key := range []string{
		"EMBEDINATOR_PORT_FRONTEND=3000",
		"EMBEDINATOR_PORT_BACKEND=8000",
		"EMBEDINATOR_PORT_QDRANT=6333",
		"EMBEDINATOR_PORT_QDRANT_GRPC=6334",
		"EMBEDINATOR_PORT_OLLAMA=11434",
		"EMBEDINATOR_GPU=none",
		"EMBEDINATOR_FERNET_KEY=test-fernet-key",
	} {
		if !strings.Contains(content, key) {
			t.Errorf(".env missing %q", key)
		}
	}
}

func TestGenerateDotEnv_PreservesUnmanagedVars(t *testing.T) {
	tmpDir := t.TempDir()
	envPath := filepath.Join(tmpDir, ".env")

	// Write an existing .env with a custom variable.
	initial := "# My custom header\nMY_CUSTOM_VAR=hello\nEMBEDINATOR_PORT_FRONTEND=9999\n"
	if err := os.WriteFile(envPath, []byte(initial), 0644); err != nil {
		t.Fatalf("write initial .env: %v", err)
	}

	cfg := DefaultConfig()
	err := GenerateDotEnv(envPath, "", cfg, "")
	if err != nil {
		t.Fatalf("GenerateDotEnv: %v", err)
	}

	data, err := os.ReadFile(envPath)
	if err != nil {
		t.Fatalf("ReadFile: %v", err)
	}
	content := string(data)

	// Custom var should be preserved.
	if !strings.Contains(content, "MY_CUSTOM_VAR=hello") {
		t.Error("unmanaged variable MY_CUSTOM_VAR was not preserved")
	}

	// Comment should be preserved.
	if !strings.Contains(content, "# My custom header") {
		t.Error("comment header was not preserved")
	}

	// Frontend port should be updated to default (3000), not 9999.
	if !strings.Contains(content, "EMBEDINATOR_PORT_FRONTEND=3000") {
		t.Error("EMBEDINATOR_PORT_FRONTEND was not updated to 3000")
	}
	if strings.Contains(content, "EMBEDINATOR_PORT_FRONTEND=9999") {
		t.Error("old EMBEDINATOR_PORT_FRONTEND=9999 was not replaced")
	}
}

func TestGenerateDotEnv_FromExample(t *testing.T) {
	tmpDir := t.TempDir()
	envPath := filepath.Join(tmpDir, ".env")
	examplePath := filepath.Join(tmpDir, ".env.example")

	// Create an example file with structure.
	example := `# The Embedinator Configuration
# Ports
EMBEDINATOR_PORT_FRONTEND=3000
EMBEDINATOR_PORT_BACKEND=8000

# API Keys
OPENAI_API_KEY=
EMBEDINATOR_FERNET_KEY=changeme
`
	if err := os.WriteFile(examplePath, []byte(example), 0644); err != nil {
		t.Fatalf("write example: %v", err)
	}

	cfg := DefaultConfig()
	err := GenerateDotEnv(envPath, examplePath, cfg, "real-key")
	if err != nil {
		t.Fatalf("GenerateDotEnv: %v", err)
	}

	data, err := os.ReadFile(envPath)
	if err != nil {
		t.Fatalf("ReadFile: %v", err)
	}
	content := string(data)

	// Comments from example should be preserved.
	if !strings.Contains(content, "# The Embedinator Configuration") {
		t.Error("example header comment not preserved")
	}

	// Managed var from example should be updated.
	if !strings.Contains(content, "EMBEDINATOR_FERNET_KEY=real-key") {
		t.Error("EMBEDINATOR_FERNET_KEY not updated from example")
	}

	// Unmanaged var from example should pass through.
	if !strings.Contains(content, "OPENAI_API_KEY=") {
		t.Error("unmanaged OPENAI_API_KEY from example not preserved")
	}
}

func TestGenerateDotEnv_AppendsMissingManagedKeys(t *testing.T) {
	tmpDir := t.TempDir()
	envPath := filepath.Join(tmpDir, ".env")

	// Start with a .env that only has one managed key.
	initial := "EMBEDINATOR_PORT_FRONTEND=3000\n"
	if err := os.WriteFile(envPath, []byte(initial), 0644); err != nil {
		t.Fatalf("write initial: %v", err)
	}

	cfg := DefaultConfig()
	err := GenerateDotEnv(envPath, "", cfg, "key123")
	if err != nil {
		t.Fatalf("GenerateDotEnv: %v", err)
	}

	data, _ := os.ReadFile(envPath)
	content := string(data)

	// Missing managed keys should be appended.
	if !strings.Contains(content, "EMBEDINATOR_PORT_BACKEND=8000") {
		t.Error("missing EMBEDINATOR_PORT_BACKEND not appended")
	}
	if !strings.Contains(content, "EMBEDINATOR_FERNET_KEY=key123") {
		t.Error("missing EMBEDINATOR_FERNET_KEY not appended")
	}
}

func TestGenerateDotEnv_ErrorOnBadPath(t *testing.T) {
	cfg := DefaultConfig()
	err := GenerateDotEnv("/nonexistent/dir/.env", "", cfg, "")
	if err == nil {
		t.Error("GenerateDotEnv with bad path returned nil error")
	}
}

func TestGenerateDotEnv_HandlesBlankAndCommentLines(t *testing.T) {
	tmpDir := t.TempDir()
	envPath := filepath.Join(tmpDir, ".env")

	initial := `# Comment line

# Another comment
EMBEDINATOR_PORT_FRONTEND=3000
NOEQUALS_LINE
`
	if err := os.WriteFile(envPath, []byte(initial), 0644); err != nil {
		t.Fatalf("write: %v", err)
	}

	cfg := DefaultConfig()
	err := GenerateDotEnv(envPath, "", cfg, "")
	if err != nil {
		t.Fatalf("GenerateDotEnv: %v", err)
	}

	data, _ := os.ReadFile(envPath)
	content := string(data)

	// Comment lines preserved.
	if !strings.Contains(content, "# Comment line") {
		t.Error("comment line not preserved")
	}
	// Line without '=' should pass through.
	if !strings.Contains(content, "NOEQUALS_LINE") {
		t.Error("line without '=' not preserved")
	}
}

func TestReadDotEnvValue(t *testing.T) {
	tmpDir := t.TempDir()
	envPath := filepath.Join(tmpDir, ".env")

	envContent := `# Header comment
EMBEDINATOR_PORT_FRONTEND=3000
EMBEDINATOR_GPU=nvidia
EMPTY_VAR=
MY_KEY=value with spaces
# Inline comment not supported
`
	if err := os.WriteFile(envPath, []byte(envContent), 0644); err != nil {
		t.Fatalf("write .env: %v", err)
	}

	tests := []struct {
		name    string
		key     string
		want    string
		wantErr bool
	}{
		{
			name: "reads existing key",
			key:  "EMBEDINATOR_PORT_FRONTEND",
			want: "3000",
		},
		{
			name: "reads GPU profile",
			key:  "EMBEDINATOR_GPU",
			want: "nvidia",
		},
		{
			name: "reads empty value",
			key:  "EMPTY_VAR",
			want: "",
		},
		{
			name: "reads value with spaces",
			key:  "MY_KEY",
			want: "value with spaces",
		},
		{
			name:    "missing key returns error",
			key:     "NONEXISTENT_KEY",
			wantErr: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, err := ReadDotEnvValue(envPath, tt.key)
			if tt.wantErr {
				if err == nil {
					t.Errorf("ReadDotEnvValue(%q) = %q, want error", tt.key, got)
				}
				return
			}
			if err != nil {
				t.Fatalf("ReadDotEnvValue(%q) error: %v", tt.key, err)
			}
			if got != tt.want {
				t.Errorf("ReadDotEnvValue(%q) = %q, want %q", tt.key, got, tt.want)
			}
		})
	}
}

func TestReadDotEnvValue_FileNotFound(t *testing.T) {
	_, err := ReadDotEnvValue("/nonexistent/.env", "KEY")
	if err == nil {
		t.Error("ReadDotEnvValue with nonexistent file returned nil error")
	}
}

func TestReadDotEnvValue_SkipsComments(t *testing.T) {
	tmpDir := t.TempDir()
	envPath := filepath.Join(tmpDir, ".env")

	envContent := "# EMBEDINATOR_PORT_FRONTEND=9999\nEMBEDINATOR_PORT_FRONTEND=3000\n"
	if err := os.WriteFile(envPath, []byte(envContent), 0644); err != nil {
		t.Fatalf("write: %v", err)
	}

	got, err := ReadDotEnvValue(envPath, "EMBEDINATOR_PORT_FRONTEND")
	if err != nil {
		t.Fatalf("ReadDotEnvValue: %v", err)
	}
	if got != "3000" {
		t.Errorf("got %q, want %q (should skip commented line)", got, "3000")
	}
}

func TestManagedEnvVars_ContainsExpectedKeys(t *testing.T) {
	expected := []string{
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

	if len(ManagedEnvVars) != len(expected) {
		t.Fatalf("ManagedEnvVars has %d entries, want %d", len(ManagedEnvVars), len(expected))
	}

	for i, want := range expected {
		if ManagedEnvVars[i] != want {
			t.Errorf("ManagedEnvVars[%d] = %q, want %q", i, ManagedEnvVars[i], want)
		}
	}
}
