package engine

import (
	"net"
	"os"
	"os/exec"
	"runtime"
	"strings"
)

// OSInfo holds detected operating system information.
type OSInfo struct {
	OS   string // linux, darwin, windows
	Arch string // amd64, arm64
	WSL2 bool
}

// DetectOS returns the current operating system and architecture.
func DetectOS() OSInfo {
	info := OSInfo{
		OS:   runtime.GOOS,
		Arch: runtime.GOARCH,
	}

	if info.OS == "linux" {
		data, err := os.ReadFile("/proc/version")
		if err == nil && strings.Contains(strings.ToLower(string(data)), "microsoft") {
			info.WSL2 = true
		}
	}

	return info
}

// DetectArch returns the CPU architecture string.
func DetectArch() string {
	return runtime.GOARCH
}

// IsWSL2 checks whether the current environment is WSL2.
func IsWSL2() bool {
	if runtime.GOOS != "linux" {
		return false
	}
	data, err := os.ReadFile("/proc/version")
	if err != nil {
		return false
	}
	return strings.Contains(strings.ToLower(string(data)), "microsoft")
}

// GetLANIP returns the first non-loopback IPv4 address.
func GetLANIP() string {
	// Try hostname -I on Linux.
	if runtime.GOOS == "linux" {
		out, err := exec.Command("hostname", "-I").Output()
		if err == nil {
			fields := strings.Fields(string(out))
			if len(fields) > 0 {
				return fields[0]
			}
		}
	}

	// macOS: ipconfig getifaddr en0.
	if runtime.GOOS == "darwin" {
		for _, iface := range []string{"en0", "en1"} {
			out, err := exec.Command("ipconfig", "getifaddr", iface).Output()
			if err == nil {
				ip := strings.TrimSpace(string(out))
				if ip != "" {
					return ip
				}
			}
		}
	}

	// Fallback: iterate network interfaces.
	addrs, err := net.InterfaceAddrs()
	if err != nil {
		return ""
	}
	for _, addr := range addrs {
		if ipnet, ok := addr.(*net.IPNet); ok && !ipnet.IP.IsLoopback() && ipnet.IP.To4() != nil {
			return ipnet.IP.String()
		}
	}

	return ""
}
