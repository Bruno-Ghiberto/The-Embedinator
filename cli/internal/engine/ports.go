package engine

import (
	"fmt"
	"net"
	"time"
)

// PortStatus holds the scan result for a single port.
type PortStatus struct {
	Port      int
	Name      string // human-readable service name
	Available bool
	Process   string // process name if in use (best effort)
}

// ScanPort checks if a TCP port is available by attempting to listen on it.
func ScanPort(port int) bool {
	ln, err := net.Listen("tcp", fmt.Sprintf(":%d", port))
	if err != nil {
		return false // port is in use
	}
	ln.Close()
	return true // port is available
}

// FindAvailablePort finds the next available port starting from startPort.
// It checks up to maxAttempts consecutive ports.
func FindAvailablePort(startPort, maxAttempts int) (int, error) {
	return FindAvailablePortExcluding(startPort, maxAttempts, nil)
}

// FindAvailablePortExcluding finds the next available port starting from startPort,
// skipping any port that is already assigned within the wizard session (excludePorts)
// in addition to OS-level in-use ports.
func FindAvailablePortExcluding(startPort, maxAttempts int, excludePorts []int) (int, error) {
	excluded := make(map[int]struct{}, len(excludePorts))
	for _, p := range excludePorts {
		excluded[p] = struct{}{}
	}
	for p := startPort; p < startPort+maxAttempts; p++ {
		if p > 65535 {
			break
		}
		if _, skip := excluded[p]; skip {
			continue
		}
		if ScanPort(p) {
			return p, nil
		}
	}
	return 0, fmt.Errorf("no available port found in range %d-%d", startPort, startPort+maxAttempts-1)
}

// DefaultPorts returns the default port assignments for all services.
func DefaultPorts() map[string]int {
	return map[string]int{
		"frontend":   3000,
		"backend":    8000,
		"qdrant":     6333,
		"qdrant_grpc": 6334,
		"ollama":     11434,
	}
}

// PortInfo describes a service port for display and scanning.
type PortInfo struct {
	Name    string
	Port    int
	EnvVar  string
}

// AllPortInfos returns the full list of service ports.
func AllPortInfos(cfg Config) []PortInfo {
	return []PortInfo{
		{Name: "Frontend (Next.js)", Port: cfg.Ports.Frontend, EnvVar: "EMBEDINATOR_PORT_FRONTEND"},
		{Name: "Backend (FastAPI)", Port: cfg.Ports.Backend, EnvVar: "EMBEDINATOR_PORT_BACKEND"},
		{Name: "Qdrant (vector DB)", Port: cfg.Ports.Qdrant, EnvVar: "EMBEDINATOR_PORT_QDRANT"},
		{Name: "Qdrant gRPC", Port: cfg.Ports.QdrantGRPC, EnvVar: "EMBEDINATOR_PORT_QDRANT_GRPC"},
		{Name: "Ollama", Port: cfg.Ports.Ollama, EnvVar: "EMBEDINATOR_PORT_OLLAMA"},
	}
}

// CheckAllPorts scans all configured ports and returns their status.
func CheckAllPorts(cfg Config) []PortStatus {
	ports := AllPortInfos(cfg)
	results := make([]PortStatus, len(ports))

	for i, p := range ports {
		results[i] = PortStatus{
			Port:      p.Port,
			Name:      p.Name,
			Available: ScanPort(p.Port),
		}
	}

	return results
}

// IsPortAvailable checks a port with a short dial timeout instead of listen.
// Useful as a secondary check method.
func IsPortAvailable(port int) bool {
	conn, err := net.DialTimeout("tcp", fmt.Sprintf("localhost:%d", port), 500*time.Millisecond)
	if err != nil {
		return true // connection refused means nothing is listening
	}
	conn.Close()
	return false // something responded
}

// ValidatePort checks that a port number is within valid range and not conflicting.
func ValidatePort(port int, otherPorts []int) error {
	if port < 1024 || port > 65535 {
		return fmt.Errorf("port must be between 1024 and 65535, got %d", port)
	}
	for _, other := range otherPorts {
		if port == other {
			return fmt.Errorf("port %d conflicts with another Embedinator service", port)
		}
	}
	return nil
}

// ValidateCustomPort performs full validation for a user-entered custom port:
// range check, not conflicting with other Embedinator services, and optionally
// checks if the port is currently in use on the host.
func ValidateCustomPort(port int, otherPorts []int) (inUse bool, err error) {
	if err := ValidatePort(port, otherPorts); err != nil {
		return false, err
	}
	if !ScanPort(port) {
		return true, nil // valid range, no conflict, but currently in use
	}
	return false, nil
}

// CollectAssignedPorts returns all currently assigned port numbers from PortStatus
// entries, excluding the entry at skipIdx. Used for cross-conflict validation
// when a user enters a custom port.
func CollectAssignedPorts(statuses []PortStatus, skipIdx int) []int {
	ports := make([]int, 0, len(statuses)-1)
	for i, ps := range statuses {
		if i == skipIdx {
			continue
		}
		ports = append(ports, ps.Port)
	}
	return ports
}
