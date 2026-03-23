package engine

import (
	"runtime"
	"testing"
)

func TestDetectOS(t *testing.T) {
	info := DetectOS()

	t.Run("OS matches runtime.GOOS", func(t *testing.T) {
		if info.OS != runtime.GOOS {
			t.Errorf("OS = %q, want %q (runtime.GOOS)", info.OS, runtime.GOOS)
		}
	})

	t.Run("Arch matches runtime.GOARCH", func(t *testing.T) {
		if info.Arch != runtime.GOARCH {
			t.Errorf("Arch = %q, want %q (runtime.GOARCH)", info.Arch, runtime.GOARCH)
		}
	})

	t.Run("OS is a known value", func(t *testing.T) {
		known := map[string]bool{
			"linux": true, "darwin": true, "windows": true,
			"freebsd": true, "openbsd": true, "netbsd": true,
		}
		if !known[info.OS] {
			t.Logf("OS = %q is not in common set (may be valid for exotic platform)", info.OS)
		}
	})

	t.Run("Arch is a known value", func(t *testing.T) {
		known := map[string]bool{
			"amd64": true, "arm64": true, "386": true, "arm": true,
			"riscv64": true, "ppc64le": true, "s390x": true,
		}
		if !known[info.Arch] {
			t.Logf("Arch = %q is not in common set (may be valid for exotic platform)", info.Arch)
		}
	})
}

func TestDetectArch(t *testing.T) {
	arch := DetectArch()
	if arch != runtime.GOARCH {
		t.Errorf("DetectArch() = %q, want %q", arch, runtime.GOARCH)
	}
	if arch == "" {
		t.Error("DetectArch() returned empty string")
	}
}

func TestIsWSL2(t *testing.T) {
	// This test verifies the function does not panic and returns a bool.
	// On non-Linux, it must return false.
	result := IsWSL2()
	if runtime.GOOS != "linux" {
		if result {
			t.Error("IsWSL2() = true on non-Linux platform")
		}
	}
	// On Linux, result depends on /proc/version content.
	// We just verify no panic.
	_ = result
}

func TestGetLANIP(t *testing.T) {
	ip := GetLANIP()

	// GetLANIP may return empty on CI or restricted environments.
	if ip == "" {
		t.Skip("GetLANIP returned empty (no network interface available)")
	}

	t.Run("not loopback", func(t *testing.T) {
		if ip == "127.0.0.1" || ip == "::1" {
			t.Errorf("GetLANIP() = %q, expected non-loopback address", ip)
		}
	})

	t.Run("looks like IP address", func(t *testing.T) {
		// Basic check: contains dots (IPv4) or colons (IPv6).
		hasDots := false
		hasColons := false
		for _, c := range ip {
			if c == '.' {
				hasDots = true
			}
			if c == ':' {
				hasColons = true
			}
		}
		if !hasDots && !hasColons {
			t.Errorf("GetLANIP() = %q, does not look like an IP address", ip)
		}
	})
}

func TestOSInfo_Struct(t *testing.T) {
	info := OSInfo{
		OS:   "linux",
		Arch: "amd64",
		WSL2: true,
	}

	if info.OS != "linux" {
		t.Errorf("OS = %q, want %q", info.OS, "linux")
	}
	if info.Arch != "amd64" {
		t.Errorf("Arch = %q, want %q", info.Arch, "amd64")
	}
	if !info.WSL2 {
		t.Error("WSL2 = false, want true")
	}
}

func TestDetectOS_ConsistentWithDetectArch(t *testing.T) {
	info := DetectOS()
	arch := DetectArch()

	if info.Arch != arch {
		t.Errorf("DetectOS().Arch = %q, DetectArch() = %q -- should be consistent", info.Arch, arch)
	}
}

func TestDetectOS_WSL2OnLinux(t *testing.T) {
	if runtime.GOOS != "linux" {
		t.Skip("WSL2 detection only relevant on Linux")
	}

	info := DetectOS()
	wsl2Direct := IsWSL2()

	// Both methods should agree on WSL2 status.
	if info.WSL2 != wsl2Direct {
		t.Errorf("DetectOS().WSL2 = %v, IsWSL2() = %v -- should agree", info.WSL2, wsl2Direct)
	}
}
