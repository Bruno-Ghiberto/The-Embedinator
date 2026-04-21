package wizard

import (
	"fmt"
	"runtime"
	"strings"
	"time"

	"github.com/charmbracelet/bubbles/spinner"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/huh"

	"github.com/Bruno-Ghiberto/The-Embedinator/cli/internal/engine"
)

// gpuPhase tracks where we are in the GPU screen flow.
type gpuPhase int

const (
	gpuPhaseDetecting    gpuPhase = iota // running DiagnoseGPU
	gpuPhaseResults                      // showing results + form
	gpuPhaseInfoOnly                     // macOS / no GPU / local ollama (press Enter)
)

// GPUModel is the bubbletea model for GPU detection (Screen 5).
type GPUModel struct {
	state      *WizardState
	result     engine.GPUResult
	diag       *engine.GPUDiagnostic
	phase      gpuPhase
	form       *huh.Form
	formDone   bool
	profileVal string
	spinner    spinner.Model
	width      int
}

type gpuDiagDoneMsg struct {
	diag   *engine.GPUDiagnostic
	result engine.GPUResult
}

// NewGPUModel creates the GPU detection screen.
func NewGPUModel(state *WizardState) GPUModel {
	s := spinner.New()
	s.Spinner = spinner.Dot
	s.Style = TitleStyle
	return GPUModel{
		state:   state,
		phase:   gpuPhaseDetecting,
		spinner: s,
	}
}

func (m GPUModel) Init() tea.Cmd {
	return tea.Batch(m.spinner.Tick, m.runDiagnostic())
}

func (m GPUModel) runDiagnostic() tea.Cmd {
	return func() tea.Msg {
		// Small delay so the spinner is visible.
		time.Sleep(500 * time.Millisecond)

		diag := engine.DiagnoseGPU()

		// Build a GPUResult from the diagnostic for backward compat.
		result := engine.GPUResult{
			Profile:       diag.RecommendedProfile,
			DeviceName:    diag.GPUName,
			DriverVersion: diag.DriverVersion,
			RuntimeOK:     diag.RecommendedProfile != "none",
			AutoDetected:  true,
		}

		return gpuDiagDoneMsg{diag: diag, result: result}
	}
}

func (m *GPUModel) buildForm() *huh.Form {
	m.profileVal = m.diag.RecommendedProfile

	options := []huh.Option[string]{}

	// Offer all detected GPUs in priority order (NVIDIA > AMD > Intel).
	if m.diag.HasNVIDIA && m.diag.RecommendedProfile == "nvidia" {
		label := "Use NVIDIA GPU (recommended)"
		if m.diag.GPUName != "" {
			label = fmt.Sprintf("Use NVIDIA GPU - %s (recommended)", m.diag.GPUName)
		}
		options = append(options, huh.NewOption(label, "nvidia"))
	} else if m.diag.HasNVIDIA {
		label := "Use NVIDIA GPU"
		if m.diag.GPUName != "" {
			label = fmt.Sprintf("Use NVIDIA GPU - %s", m.diag.GPUName)
		}
		options = append(options, huh.NewOption(label, "nvidia"))
	}

	if m.diag.HasAMD {
		label := "Use AMD GPU (ROCm)"
		if m.diag.RecommendedProfile == "amd" {
			label += " (recommended)"
		}
		options = append(options, huh.NewOption(label, "amd"))
	}

	if m.diag.HasIntel {
		label := "Use Intel GPU (experimental)"
		if m.diag.RecommendedProfile == "intel" {
			label += " (recommended)"
		}
		options = append(options, huh.NewOption(label, "intel"))
	}

	options = append(options, huh.NewOption("Use CPU only", "none"))

	sel := huh.NewSelect[string]().
		Title("GPU Configuration").
		Options(options...).
		Value(&m.profileVal)

	return huh.NewForm(huh.NewGroup(sel)).WithShowHelp(false)
}

func (m *GPUModel) buildIssueForm() *huh.Form {
	m.profileVal = "none"

	options := []huh.Option[string]{
		huh.NewOption("Skip GPU for now (use CPU mode)", "none"),
		huh.NewOption("I'll fix this myself (copy commands above)", "manual"),
	}

	sel := huh.NewSelect[string]().
		Title("").
		Options(options...).
		Value(&m.profileVal)

	return huh.NewForm(huh.NewGroup(sel)).WithShowHelp(false)
}

func (m GPUModel) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width = msg.Width
		return m, nil

	case spinner.TickMsg:
		if m.phase == gpuPhaseDetecting {
			var cmd tea.Cmd
			m.spinner, cmd = m.spinner.Update(msg)
			return m, cmd
		}
		return m, nil

	case gpuDiagDoneMsg:
		m.diag = msg.diag
		m.result = msg.result
		m.state.GPUResult = msg.result
		m.state.GPUDiag = msg.diag

		// macOS: always info-only.
		if runtime.GOOS == "darwin" {
			m.phase = gpuPhaseInfoOnly
			return m, nil
		}

		// No GPU found at all.
		if !m.diag.HasNVIDIA && !m.diag.HasAMD && !m.diag.HasIntel {
			m.phase = gpuPhaseInfoOnly
			return m, nil
		}

		// Using local Ollama: GPU config is informational.
		if m.state.OllamaMode == "local" {
			m.phase = gpuPhaseInfoOnly
			return m, nil
		}

		// If the recommended profile works (even if other GPU chains have issues),
		// show the full selection form so the user can pick the working GPU.
		// Only show the issue-only form if ALL detected GPUs have blockers.
		hasWorkingGPU := m.diag.RecommendedProfile != "none"
		if hasWorkingGPU {
			m.phase = gpuPhaseResults
			m.form = m.buildForm()
			return m, m.form.Init()
		}

		// No working GPU — show issues + fallback form.
		if m.diag.HasBlockers() {
			m.phase = gpuPhaseResults
			m.form = m.buildIssueForm()
			return m, m.form.Init()
		}

		// No GPU at all or all "none" — selection form.
		m.phase = gpuPhaseResults
		m.form = m.buildForm()
		return m, m.form.Init()

	case tea.KeyMsg:
		switch msg.String() {
		case "enter":
			if m.phase == gpuPhaseInfoOnly {
				return m, func() tea.Msg { return NextScreenMsg{} }
			}
		case "ctrl+c":
			return m, tea.Quit
		}
	}

	if m.form != nil {
		form, cmd := m.form.Update(msg)
		if f, ok := form.(*huh.Form); ok {
			m.form = f
		}

		if m.form.State == huh.StateCompleted && !m.formDone {
			m.formDone = true

			if m.profileVal == "manual" {
				// User chose "I'll fix this myself" -- use CPU mode.
				m.state.GPUResult.Profile = "none"
				m.state.GPUResult.AutoDetected = false
			} else if m.profileVal != "" {
				m.state.GPUResult.Profile = m.profileVal
				m.state.GPUResult.AutoDetected = false
			}

			return m, func() tea.Msg { return NextScreenMsg{} }
		}

		return m, cmd
	}

	return m, nil
}

func (m GPUModel) View() string {
	s := TitleStyle.Render("  GPU Setup") + "\n\n"

	if m.phase == gpuPhaseDetecting {
		s += fmt.Sprintf("    %s Diagnosing GPU and Docker GPU chain...\n", m.spinner.View())
		return s
	}

	// --- macOS ---
	if runtime.GOOS == "darwin" {
		s += "  macOS detected. Docker Desktop cannot pass through the Metal GPU.\n\n"
		if m.state.OllamaMode == "local" {
			s += SuccessStyle.Render("  Your local Ollama will use Metal GPU natively.") + "\n\n"
		} else {
			s += "  Docker Ollama will run in CPU mode.\n"
			s += DimStyle.Render("  For GPU-accelerated inference, use local Ollama (previous step).") + "\n\n"
		}
		s += DimStyle.Render(fmt.Sprintf("  GPU profile: %s", m.result.Profile)) + "\n\n"
		s += DimStyle.Render("  Press Enter to continue.") + "\n"
		return s
	}

	// --- No GPU ---
	if !m.diag.HasNVIDIA && !m.diag.HasAMD && !m.diag.HasIntel {
		s += fmt.Sprintf("    NVIDIA    %s not detected\n", SkipMark)
		s += fmt.Sprintf("    AMD       %s not detected\n", SkipMark)
		s += fmt.Sprintf("    Intel     %s not detected\n", SkipMark)
		s += "\n"
		s += "  No supported GPU detected. Using CPU mode.\n\n"
		s += DimStyle.Render("  This is fine -- Ollama works well on CPU.") + "\n\n"
		s += DimStyle.Render("  Press Enter to continue.") + "\n"
		return s
	}

	// --- Local Ollama ---
	if m.state.OllamaMode == "local" {
		s += m.renderHardwareSection()
		s += "\n"
		s += DimStyle.Render("  Using local Ollama (GPU passthrough managed by your local install).") + "\n\n"
		s += DimStyle.Render("  Press Enter to continue.") + "\n"
		return s
	}

	// --- Full diagnostic display ---
	s += m.renderHardwareSection()
	s += "\n"

	// Docker Engine coexistence status.
	if m.diag.DockerType == "desktop" && m.diag.EngineRunning {
		s += "  " + SuccessStyle.Render("Using Docker Engine for GPU access (Docker Desktop stays installed)") + "\n\n"
	} else if m.diag.DockerType == "desktop" && m.diag.EngineInstalled {
		s += "  " + WarningStyle.Render("Docker Engine installed but not running (Desktop detected)") + "\n\n"
	}

	// NVIDIA GPU chain.
	if m.diag.HasNVIDIA {
		s += "  " + BoldStyle.Render("NVIDIA GPU Chain:") + "\n"
		s += m.renderChainItem("Docker type", m.renderDockerTypeStatus())
		s += m.renderChainItem("nvidia-container-toolkit", m.renderToolkitStatus())
		s += m.renderChainItem("NVIDIA Docker runtime", m.renderRuntimeStatus())
		s += m.renderChainItem("CDI specification", m.renderCDIStatus())
		s += m.renderChainItem("GPU passthrough test", m.renderNVIDIAPassthroughStatus())
		s += "\n"
	}

	// AMD GPU chain.
	if m.diag.HasAMD {
		s += "  " + BoldStyle.Render("AMD GPU Chain:") + "\n"
		s += m.renderChainItem("ROCm kernel driver (/dev/kfd)", m.renderBoolStatus(m.diag.AMDKernelDriver, "loaded", "not found"))
		s += m.renderChainItem("User groups (video, render)", m.renderBoolStatus(m.diag.AMDUserGroups, "OK", "missing"))
		s += m.renderChainItem("rocminfo", m.renderBoolStatus(m.diag.AMDRocmInfo, "works", "not available"))
		s += "\n"
	}

	// Intel GPU chain.
	if m.diag.HasIntel {
		s += "  " + BoldStyle.Render("Intel GPU Chain (experimental):") + "\n"
		s += m.renderChainItem("/dev/dri render devices", m.renderBoolStatus(m.diag.IntelDRI, "found", "not found"))
		s += m.renderChainItem("User group (render)", m.renderBoolStatus(m.diag.IntelUserGroup, "OK", "missing"))
		s += "\n"
	}

	// Issues.
	if len(m.diag.Issues) > 0 {
		for _, issue := range m.diag.Issues {
			if issue.Severity == "info" {
				continue // Don't show info-level in the issues box.
			}
			s += m.renderIssueBox(issue)
			s += "\n"
		}
	}

	// Success message when everything works.
	if !m.diag.HasBlockers() && m.diag.RecommendedProfile != "none" {
		gpuType := strings.ToUpper(m.diag.RecommendedProfile)
		s += SuccessStyle.Render(fmt.Sprintf("  %s GPU will be used for Ollama inference inside Docker.", gpuType)) + "\n\n"
	}

	// Form.
	if m.form != nil {
		s += m.form.View()
	}

	return s
}

// --- View helpers ---

func (m GPUModel) renderHardwareSection() string {
	s := "  " + BoldStyle.Render("Hardware:") + "\n"

	if m.diag.HasNVIDIA {
		detail := ""
		if m.diag.DriverVersion != "" {
			detail = fmt.Sprintf(" (driver %s)", m.diag.DriverVersion)
		}
		s += fmt.Sprintf("    %-34s %s detected%s\n", m.diag.GPUName, CheckMark, detail)
	} else {
		s += fmt.Sprintf("    %-34s %s not detected\n", "NVIDIA", SkipMark)
	}

	if m.diag.HasAMD {
		s += fmt.Sprintf("    %-34s %s detected\n", "AMD (ROCm)", CheckMark)
	} else {
		s += fmt.Sprintf("    %-34s %s not detected\n", "AMD", SkipMark)
	}

	if m.diag.HasIntel {
		s += fmt.Sprintf("    %-34s %s detected\n", "Intel", CheckMark)
	} else {
		s += fmt.Sprintf("    %-34s %s not detected\n", "Intel", SkipMark)
	}

	return s
}

func (m GPUModel) renderChainItem(label, status string) string {
	return fmt.Sprintf("    %-34s %s\n", label, status)
}

func (m GPUModel) renderBoolStatus(ok bool, passLabel, failLabel string) string {
	if ok {
		return fmt.Sprintf("%s %s", CheckMark, passLabel)
	}
	return fmt.Sprintf("%s %s", CrossMark, failLabel)
}

func (m GPUModel) renderDockerTypeStatus() string {
	switch m.diag.DockerType {
	case "engine":
		ver := ""
		if m.diag.DockerVersion != "" {
			ver = fmt.Sprintf(" v%s", m.diag.DockerVersion)
		}
		return fmt.Sprintf("%s Docker Engine%s", CheckMark, ver)
	case "desktop":
		if m.diag.EngineRunning {
			return fmt.Sprintf("%s Docker Engine (via Engine socket, Desktop also installed)", CheckMark)
		}
		return fmt.Sprintf("%s Docker Desktop %s", CrossMark, ErrorStyle.Render("(needs Docker Engine for GPU)"))
	default:
		return fmt.Sprintf("%s unknown", WarningMark)
	}
}

func (m GPUModel) renderToolkitStatus() string {
	if m.diag.ToolkitInstalled {
		ver := ""
		if m.diag.ToolkitVersion != "" {
			ver = fmt.Sprintf(" v%s", m.diag.ToolkitVersion)
		}
		return fmt.Sprintf("%s installed%s", CheckMark, ver)
	}
	// If Docker Desktop blocker exists and Engine not running, toolkit check was skipped.
	if m.diag.DockerType == "desktop" && !m.diag.EngineRunning {
		return fmt.Sprintf("%s skipped (Docker Engine not running)", SkipMark)
	}
	return fmt.Sprintf("%s not installed", CrossMark)
}

func (m GPUModel) renderRuntimeStatus() string {
	if m.diag.RuntimeConfigured {
		return fmt.Sprintf("%s configured", CheckMark)
	}
	if m.diag.DockerType == "desktop" && !m.diag.EngineRunning {
		return fmt.Sprintf("%s skipped (Docker Engine not running)", SkipMark)
	}
	return fmt.Sprintf("%s not configured", CrossMark)
}

func (m GPUModel) renderCDIStatus() string {
	if m.diag.CDISpecExists {
		return fmt.Sprintf("%s generated", CheckMark)
	}
	if m.diag.DockerType == "desktop" && !m.diag.EngineRunning {
		return fmt.Sprintf("%s skipped (Docker Engine not running)", SkipMark)
	}
	return fmt.Sprintf("%s not found", WarningMark)
}

func (m GPUModel) renderNVIDIAPassthroughStatus() string {
	if m.diag.PassthroughWorks {
		return fmt.Sprintf("%s passed", CheckMark)
	}
	if m.diag.HasBlockers() {
		return fmt.Sprintf("%s skipped (fix blockers first)", SkipMark)
	}
	if m.diag.PassthroughError != "" {
		return fmt.Sprintf("%s failed", CrossMark)
	}
	return fmt.Sprintf("%s not tested", SkipMark)
}

func (m GPUModel) renderIssueBox(issue engine.GPUIssue) string {
	var borderStyle = ErrorBoxStyle
	severityLabel := "Issue"
	if issue.Severity == "warning" {
		borderStyle = WarningBoxStyle
		severityLabel = "Warning"
	}

	var content strings.Builder
	content.WriteString(issue.Description)

	if len(issue.FixCommands) > 0 {
		content.WriteString("\n\nFix:")
		for _, cmd := range issue.FixCommands {
			content.WriteString("\n  " + DimStyle.Render(cmd))
		}
	}

	if issue.FixNote != "" {
		content.WriteString("\n\n" + DimStyle.Render(issue.FixNote))
	}

	label := fmt.Sprintf(" %s: %s ", severityLabel, issue.Title)
	box := borderStyle.Render(content.String())

	return "  " + BoldStyle.Render(label) + "\n" + box + "\n"
}
