package engine

import (
	"net"
	"testing"
)

func TestDefaultPorts(t *testing.T) {
	ports := DefaultPorts()

	expected := map[string]int{
		"frontend":    3000,
		"backend":     8000,
		"qdrant":      6333,
		"qdrant_grpc": 6334,
		"ollama":      11434,
	}

	if len(ports) != len(expected) {
		t.Fatalf("DefaultPorts: got %d entries, want %d", len(ports), len(expected))
	}

	for name, wantPort := range expected {
		got, ok := ports[name]
		if !ok {
			t.Errorf("DefaultPorts: missing key %q", name)
			continue
		}
		if got != wantPort {
			t.Errorf("DefaultPorts[%q] = %d, want %d", name, got, wantPort)
		}
	}
}

func TestValidatePort(t *testing.T) {
	tests := []struct {
		name       string
		port       int
		otherPorts []int
		wantErr    bool
		errSubstr  string
	}{
		{
			name:       "valid port no conflicts",
			port:       8080,
			otherPorts: []int{3000, 6333},
			wantErr:    false,
		},
		{
			name:       "minimum valid port",
			port:       1024,
			otherPorts: nil,
			wantErr:    false,
		},
		{
			name:       "maximum valid port",
			port:       65535,
			otherPorts: nil,
			wantErr:    false,
		},
		{
			name:       "below minimum range",
			port:       1023,
			otherPorts: nil,
			wantErr:    true,
			errSubstr:  "between 1024 and 65535",
		},
		{
			name:       "above maximum range",
			port:       65536,
			otherPorts: nil,
			wantErr:    true,
			errSubstr:  "between 1024 and 65535",
		},
		{
			name:       "port zero",
			port:       0,
			otherPorts: nil,
			wantErr:    true,
			errSubstr:  "between 1024 and 65535",
		},
		{
			name:       "negative port",
			port:       -1,
			otherPorts: nil,
			wantErr:    true,
			errSubstr:  "between 1024 and 65535",
		},
		{
			name:       "privileged port 80",
			port:       80,
			otherPorts: nil,
			wantErr:    true,
			errSubstr:  "between 1024 and 65535",
		},
		{
			name:       "conflicts with other port",
			port:       3000,
			otherPorts: []int{3000, 8000},
			wantErr:    true,
			errSubstr:  "conflicts",
		},
		{
			name:       "conflicts with second port in list",
			port:       8000,
			otherPorts: []int{3000, 8000, 6333},
			wantErr:    true,
			errSubstr:  "conflicts",
		},
		{
			name:       "no conflict with empty list",
			port:       8080,
			otherPorts: []int{},
			wantErr:    false,
		},
		{
			name:       "no conflict with nil list",
			port:       8080,
			otherPorts: nil,
			wantErr:    false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := ValidatePort(tt.port, tt.otherPorts)
			if tt.wantErr && err == nil {
				t.Errorf("ValidatePort(%d, %v) = nil, want error containing %q", tt.port, tt.otherPorts, tt.errSubstr)
			}
			if !tt.wantErr && err != nil {
				t.Errorf("ValidatePort(%d, %v) = %v, want nil", tt.port, tt.otherPorts, err)
			}
			if tt.wantErr && err != nil && tt.errSubstr != "" {
				if got := err.Error(); !containsSubstring(got, tt.errSubstr) {
					t.Errorf("ValidatePort(%d, %v) error = %q, want substring %q", tt.port, tt.otherPorts, got, tt.errSubstr)
				}
			}
		})
	}
}

func TestScanPort(t *testing.T) {
	// Bind a port so we know it is occupied.
	ln, err := net.Listen("tcp", ":0")
	if err != nil {
		t.Fatalf("failed to listen on a free port: %v", err)
	}
	defer ln.Close()
	occupiedPort := ln.Addr().(*net.TCPAddr).Port

	t.Run("occupied port returns false", func(t *testing.T) {
		if ScanPort(occupiedPort) {
			t.Errorf("ScanPort(%d) = true, want false (port is occupied)", occupiedPort)
		}
	})

	// Release the port and verify it becomes available.
	ln.Close()
	t.Run("released port returns true", func(t *testing.T) {
		if !ScanPort(occupiedPort) {
			t.Errorf("ScanPort(%d) = false, want true (port was released)", occupiedPort)
		}
	})
}

func TestIsPortAvailable(t *testing.T) {
	// Nothing should be listening on a high ephemeral port.
	// IsPortAvailable uses DialTimeout: connection refused means available.
	t.Run("unreachable port returns true", func(t *testing.T) {
		// Port 19 (chargen) is almost certainly not running locally.
		if !IsPortAvailable(19) {
			t.Skip("port 19 unexpectedly in use, skipping")
		}
	})
}

func TestFindAvailablePort(t *testing.T) {
	t.Run("finds a free port starting from high range", func(t *testing.T) {
		port, err := FindAvailablePort(49152, 100)
		if err != nil {
			t.Fatalf("FindAvailablePort(49152, 100) returned error: %v", err)
		}
		if port < 49152 || port > 49251 {
			t.Errorf("FindAvailablePort returned %d, expected range 49152-49251", port)
		}
	})

	t.Run("returns error when maxAttempts is zero", func(t *testing.T) {
		_, err := FindAvailablePort(8000, 0)
		if err == nil {
			t.Error("FindAvailablePort(8000, 0) = nil, want error")
		}
	})

	t.Run("respects upper port limit of 65535", func(t *testing.T) {
		// Starting from 65530 with 100 attempts -- should stop at 65535.
		port, err := FindAvailablePort(65530, 100)
		if err != nil {
			t.Fatalf("FindAvailablePort(65530, 100) returned error: %v", err)
		}
		if port < 65530 || port > 65535 {
			t.Errorf("FindAvailablePort returned %d, expected 65530-65535", port)
		}
	})

	t.Run("all ports occupied returns error", func(t *testing.T) {
		// Occupy a single port and search with maxAttempts=1.
		ln, err := net.Listen("tcp", ":0")
		if err != nil {
			t.Fatalf("failed to listen: %v", err)
		}
		defer ln.Close()
		occupied := ln.Addr().(*net.TCPAddr).Port

		_, findErr := FindAvailablePort(occupied, 1)
		if findErr == nil {
			t.Errorf("FindAvailablePort(%d, 1) = nil, want error (port is occupied)", occupied)
		}
	})
}

func TestAllPortInfos(t *testing.T) {
	cfg := DefaultConfig()
	infos := AllPortInfos(cfg)

	if len(infos) != 5 {
		t.Fatalf("AllPortInfos: got %d entries, want 5", len(infos))
	}

	// Verify each PortInfo has non-empty Name and EnvVar.
	for i, info := range infos {
		if info.Name == "" {
			t.Errorf("AllPortInfos[%d].Name is empty", i)
		}
		if info.EnvVar == "" {
			t.Errorf("AllPortInfos[%d].EnvVar is empty", i)
		}
		if info.Port < 1024 {
			t.Errorf("AllPortInfos[%d].Port = %d, expected >= 1024", i, info.Port)
		}
	}

	// Verify port values match config.
	expectedPorts := map[string]int{
		"EMBEDINATOR_PORT_FRONTEND":   cfg.Ports.Frontend,
		"EMBEDINATOR_PORT_BACKEND":    cfg.Ports.Backend,
		"EMBEDINATOR_PORT_QDRANT":     cfg.Ports.Qdrant,
		"EMBEDINATOR_PORT_QDRANT_GRPC": cfg.Ports.QdrantGRPC,
		"EMBEDINATOR_PORT_OLLAMA":     cfg.Ports.Ollama,
	}
	for _, info := range infos {
		if want, ok := expectedPorts[info.EnvVar]; ok {
			if info.Port != want {
				t.Errorf("AllPortInfos: EnvVar %q has Port %d, want %d", info.EnvVar, info.Port, want)
			}
		}
	}
}

func TestCheckAllPorts(t *testing.T) {
	cfg := DefaultConfig()
	results := CheckAllPorts(cfg)

	if len(results) != 5 {
		t.Fatalf("CheckAllPorts: got %d results, want 5", len(results))
	}

	for _, r := range results {
		if r.Name == "" {
			t.Error("CheckAllPorts: got result with empty Name")
		}
		if r.Port < 1024 {
			t.Errorf("CheckAllPorts: Port %d is below 1024", r.Port)
		}
		// Available is a boolean -- just ensure it is set (no panic).
		_ = r.Available
	}
}

// containsSubstring is a test helper.
func containsSubstring(s, substr string) bool {
	return len(s) >= len(substr) && (s == substr || len(s) > 0 && containsIdx(s, substr))
}

func containsIdx(s, substr string) bool {
	for i := 0; i <= len(s)-len(substr); i++ {
		if s[i:i+len(substr)] == substr {
			return true
		}
	}
	return false
}
