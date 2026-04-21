//go:build !windows

package engine

import (
	"os/exec"
	"runtime"
	"strconv"
	"strings"
)

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
