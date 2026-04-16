package engine

import (
	"strings"
	"testing"
)

func TestGPUDiagnostic_HasBlockers(t *testing.T) {
	tests := []struct {
		name   string
		issues []GPUIssue
		want   bool
	}{
		{
			name:   "no issues",
			issues: nil,
			want:   false,
		},
		{
			name: "only info issues",
			issues: []GPUIssue{
				{Severity: "info", Title: "macOS"},
				{Severity: "info", Title: "no GPU"},
			},
			want: false,
		},
		{
			name: "only warning issues",
			issues: []GPUIssue{
				{Severity: "warning", Title: "CDI not generated"},
			},
			want: false,
		},
		{
			name: "one blocker among others",
			issues: []GPUIssue{
				{Severity: "info", Title: "info issue"},
				{Severity: "blocker", Title: "toolkit missing"},
				{Severity: "warning", Title: "warning issue"},
			},
			want: true,
		},
		{
			name: "only blockers",
			issues: []GPUIssue{
				{Severity: "blocker", Title: "blocker 1"},
				{Severity: "blocker", Title: "blocker 2"},
			},
			want: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			diag := &GPUDiagnostic{Issues: tt.issues}
			if got := diag.HasBlockers(); got != tt.want {
				t.Errorf("HasBlockers() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestChainHasBlockers(t *testing.T) {
	tests := []struct {
		name   string
		vendor string
		issues []GPUIssue
		want   bool
	}{
		{
			name:   "no issues",
			vendor: "nvidia",
			issues: nil,
			want:   false,
		},
		{
			name:   "blocker matches vendor prefix",
			vendor: "nvidia",
			issues: []GPUIssue{
				{Severity: "blocker", Title: "Nvidia: toolkit not installed"},
			},
			want: true,
		},
		{
			name:   "blocker for different vendor",
			vendor: "nvidia",
			issues: []GPUIssue{
				{Severity: "blocker", Title: "AMD: ROCm not found"},
			},
			want: false,
		},
		{
			name:   "warning not treated as blocker",
			vendor: "nvidia",
			issues: []GPUIssue{
				{Severity: "warning", Title: "Nvidia: CDI not generated"},
			},
			want: false,
		},
		{
			name:   "amd vendor capitalization check",
			vendor: "amd",
			issues: []GPUIssue{
				{Severity: "blocker", Title: "Amd: kernel driver missing"},
			},
			want: true,
		},
		{
			name:   "intel vendor capitalization check",
			vendor: "intel",
			issues: []GPUIssue{
				{Severity: "blocker", Title: "Intel: render devices not found"},
			},
			want: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			diag := &GPUDiagnostic{Issues: tt.issues}
			if got := chainHasBlockers(diag, tt.vendor); got != tt.want {
				t.Errorf("chainHasBlockers(diag, %q) = %v, want %v", tt.vendor, got, tt.want)
			}
		})
	}
}

func TestGPUResult_Struct(t *testing.T) {
	// Verify GPUResult fields are correctly populated.
	r := GPUResult{
		Profile:       "nvidia",
		DeviceName:    "RTX 4090",
		DriverVersion: "565.77",
		RuntimeOK:     true,
		AutoDetected:  true,
	}

	if r.Profile != "nvidia" {
		t.Errorf("Profile = %q, want %q", r.Profile, "nvidia")
	}
	if r.DeviceName != "RTX 4090" {
		t.Errorf("DeviceName = %q, want %q", r.DeviceName, "RTX 4090")
	}
	if r.DriverVersion != "565.77" {
		t.Errorf("DriverVersion = %q, want %q", r.DriverVersion, "565.77")
	}
	if !r.RuntimeOK {
		t.Error("RuntimeOK = false, want true")
	}
	if !r.AutoDetected {
		t.Error("AutoDetected = false, want true")
	}
}

func TestGPUIssue_Struct(t *testing.T) {
	issue := GPUIssue{
		Severity:    "blocker",
		Title:       "NVIDIA: toolkit not installed",
		Description: "The NVIDIA Container Toolkit is required.",
		FixCommands: []string{"sudo dnf install nvidia-container-toolkit"},
		FixNote:     "Install the toolkit.",
	}

	if issue.Severity != "blocker" {
		t.Errorf("Severity = %q, want %q", issue.Severity, "blocker")
	}
	if len(issue.FixCommands) != 1 {
		t.Errorf("FixCommands has %d entries, want 1", len(issue.FixCommands))
	}
}

func TestDockerEngineInstallCommands_Distros(t *testing.T) {
	tests := []struct {
		distro       string
		wantContains string
	}{
		{"fedora", "dnf"},
		{"ubuntu", "apt-get"},
		{"debian", "apt-get"},
		{"arch", "pacman"},
		{"unknown", "docs.docker.com"},
	}

	for _, tt := range tests {
		t.Run(tt.distro, func(t *testing.T) {
			cmds := dockerEngineInstallCommands(tt.distro)
			if len(cmds) == 0 {
				t.Fatal("got empty command list")
			}
			joined := strings.Join(cmds, "\n")
			if !strings.Contains(joined, tt.wantContains) {
				t.Errorf("commands for %q missing %q:\n%s", tt.distro, tt.wantContains, joined)
			}
		})
	}
}

func TestToolkitInstallCommands_Distros(t *testing.T) {
	tests := []struct {
		distro       string
		wantContains string
	}{
		{"fedora", "dnf"},
		{"rhel", "dnf"},
		{"centos", "dnf"},
		{"ubuntu", "apt-get"},
		{"debian", "apt-get"},
		{"arch", "nvidia-container-toolkit"},
		{"unknown", "nvidia-ctk"},
	}

	for _, tt := range tests {
		t.Run(tt.distro, func(t *testing.T) {
			cmds := toolkitInstallCommands(tt.distro)
			if len(cmds) == 0 {
				t.Fatal("got empty command list")
			}
			joined := strings.Join(cmds, "\n")
			if !strings.Contains(joined, tt.wantContains) {
				t.Errorf("commands for %q missing %q:\n%s", tt.distro, tt.wantContains, joined)
			}
		})
	}
}

func TestAmdDriverInstallCommands_Distros(t *testing.T) {
	tests := []struct {
		distro       string
		wantContains string
	}{
		{"ubuntu", "amdgpu-install"},
		{"debian", "amdgpu-install"},
		{"fedora", "amdgpu-install"},
		{"arch", "rocm-hip-sdk"},
		{"unknown", "rocm.docs.amd.com"},
	}

	for _, tt := range tests {
		t.Run(tt.distro, func(t *testing.T) {
			cmds := amdDriverInstallCommands(tt.distro)
			if len(cmds) == 0 {
				t.Fatal("got empty command list")
			}
			joined := strings.Join(cmds, "\n")
			if !strings.Contains(joined, tt.wantContains) {
				t.Errorf("commands for %q missing %q:\n%s", tt.distro, tt.wantContains, joined)
			}
		})
	}
}

func TestAmdRocmInfoInstallCommands_Distros(t *testing.T) {
	tests := []struct {
		distro       string
		wantContains string
	}{
		{"ubuntu", "apt-get"},
		{"debian", "apt-get"},
		{"fedora", "dnf"},
		{"arch", "rocminfo"},
		{"unknown", "package manager"},
	}

	for _, tt := range tests {
		t.Run(tt.distro, func(t *testing.T) {
			cmds := amdRocmInfoInstallCommands(tt.distro)
			if len(cmds) == 0 {
				t.Fatal("got empty command list")
			}
			joined := strings.Join(cmds, "\n")
			if !strings.Contains(joined, tt.wantContains) {
				t.Errorf("commands for %q missing %q:\n%s", tt.distro, tt.wantContains, joined)
			}
		})
	}
}

func TestGPUDiagnostic_DefaultProfile(t *testing.T) {
	diag := &GPUDiagnostic{}
	// Zero-value string is "". DiagnoseGPU sets it to "none" at creation.
	// But if constructed manually without DiagnoseGPU, default is "".
	// Verify that DiagnoseGPU would set a default.
	if diag.RecommendedProfile != "" {
		t.Errorf("zero-value RecommendedProfile = %q, want empty string", diag.RecommendedProfile)
	}
}

func TestGPUDiagnostic_IssuesAppend(t *testing.T) {
	diag := &GPUDiagnostic{}

	diag.Issues = append(diag.Issues, GPUIssue{
		Severity: "info",
		Title:    "test issue",
	})

	if len(diag.Issues) != 1 {
		t.Fatalf("Issues has %d entries, want 1", len(diag.Issues))
	}
	if diag.Issues[0].Severity != "info" {
		t.Errorf("Issues[0].Severity = %q, want %q", diag.Issues[0].Severity, "info")
	}

	// Add a blocker.
	diag.Issues = append(diag.Issues, GPUIssue{
		Severity: "blocker",
		Title:    "critical issue",
	})

	if !diag.HasBlockers() {
		t.Error("HasBlockers() = false after adding blocker")
	}
}

func TestHandleDockerDesktopCoexistence_EngineRunning(t *testing.T) {
	// Simulate: Engine installed + running -- should return true with info issue.
	diag := &GPUDiagnostic{
		EngineInstalled: true,
		EngineRunning:   true,
	}

	resolved := handleDockerDesktopCoexistence(diag)
	if !resolved {
		t.Error("handleDockerDesktopCoexistence returned false, want true (Engine running)")
	}

	// Should have an info issue about using Engine.
	foundInfo := false
	for _, issue := range diag.Issues {
		if issue.Severity == "info" && strings.Contains(issue.Title, "Docker Engine") {
			foundInfo = true
		}
	}
	if !foundInfo {
		t.Error("expected info issue about Docker Engine, not found")
	}
}

func TestHandleDockerDesktopCoexistence_EngineInstalledNotRunning(t *testing.T) {
	// Simulate: Engine installed but NOT running -- should return false with warning.
	diag := &GPUDiagnostic{
		EngineInstalled: true,
		EngineRunning:   false,
	}

	resolved := handleDockerDesktopCoexistence(diag)
	if resolved {
		t.Error("handleDockerDesktopCoexistence returned true, want false (Engine not running)")
	}

	foundWarning := false
	for _, issue := range diag.Issues {
		if issue.Severity == "warning" && strings.Contains(issue.Title, "not running") {
			foundWarning = true
		}
	}
	if !foundWarning {
		t.Error("expected warning issue about Engine not running, not found")
	}
}

func TestHandleDockerDesktopCoexistence_EngineNotInstalled(t *testing.T) {
	// Simulate: Engine NOT installed -- should return false with blocker.
	diag := &GPUDiagnostic{
		EngineInstalled: false,
		EngineRunning:   false,
	}

	resolved := handleDockerDesktopCoexistence(diag)
	if resolved {
		t.Error("handleDockerDesktopCoexistence returned true, want false (Engine not installed)")
	}

	foundBlocker := false
	for _, issue := range diag.Issues {
		if issue.Severity == "blocker" && strings.Contains(issue.Title, "Docker Engine needed") {
			foundBlocker = true
		}
	}
	if !foundBlocker {
		t.Error("expected blocker issue about Engine needed, not found")
	}
}
