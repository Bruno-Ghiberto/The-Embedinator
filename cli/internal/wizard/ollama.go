package wizard

import (
	"fmt"
	"strings"

	tea "github.com/charmbracelet/bubbletea"

	"github.com/Bruno-Ghiberto/The-Embedinator/cli/internal/engine"
)

// OllamaModel is the bubbletea model for the Ollama configuration screen
// (Screen 3 of the setup wizard).
//
// The Embedinator runs Ollama exclusively in Docker — there is no local or
// remote mode. This screen probes the host for a conflicting Ollama daemon
// on port 11434 and refuses to advance until the conflict is resolved.
//
// On a clean host the screen is purely informational: it reports whether the
// port is free or already owned by the embedinator-ollama container, and
// advances on Enter.
type OllamaModel struct {
	state     *WizardState
	detection engine.OllamaDetection
	conflict  engine.OllamaConflictResult
	done      bool
	width     int
}

type ollamaDetectDoneMsg struct {
	detection engine.OllamaDetection
	conflict  engine.OllamaConflictResult
}

// NewOllamaModel creates the Ollama configuration screen. It forces Docker
// mode — no user choice is offered.
func NewOllamaModel(state *WizardState) OllamaModel {
	state.OllamaMode = "docker"
	state.OllamaRemoteURL = ""
	return OllamaModel{state: state}
}

func (m OllamaModel) Init() tea.Cmd {
	return func() tea.Msg {
		return ollamaDetectDoneMsg{
			detection: engine.DetectLocalOllama(),
			conflict:  engine.CheckOllamaPortConflict(),
		}
	}
}

func (m OllamaModel) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width = msg.Width
		return m, nil

	case ollamaDetectDoneMsg:
		m.detection = msg.detection
		m.conflict = msg.conflict
		m.state.OllamaDetection = msg.detection
		m.done = true
		return m, nil

	case tea.KeyMsg:
		switch msg.String() {
		case "ctrl+c", "q":
			return m, tea.Quit
		case "enter":
			if m.done && !m.conflict.HasConflict() {
				return m, func() tea.Msg { return NextScreenMsg{} }
			}
		case "r":
			if m.done && m.conflict.HasConflict() {
				// Re-probe after the user claims they've stopped the daemon.
				m.done = false
				return m, m.Init()
			}
		}
	}
	return m, nil
}

func (m OllamaModel) View() string {
	s := TitleStyle.Render("  Ollama Configuration") + "\n\n"

	if !m.done {
		s += "  Checking host Ollama state...\n"
		return s
	}

	s += "  The Embedinator runs Ollama exclusively in Docker for\n"
	s += "  reliability, reproducibility, and easy teardown.\n\n"

	if m.conflict.HasConflict() {
		s += ErrorBoxStyle.Render("  BLOCKED: "+m.conflict.Message) + "\n\n"
		if m.conflict.Remediation != "" {
			s += "  Remediation:\n"
			for _, line := range strings.Split(m.conflict.Remediation, "\n") {
				s += "    " + line + "\n"
			}
			s += "\n"
		}
		s += DimStyle.Render("  Press 'r' to retry detection, or q/Ctrl+C to quit.") + "\n"
		return s
	}

	// No conflict — port is either free or already owned by our Docker Ollama.
	switch m.conflict.State {
	case engine.OllamaPortFree:
		s += SuccessStyle.Render("  ✓ Port 11434 is free — ready to start Docker Ollama") + "\n"
	case engine.OllamaPortOwnedByDockerStack:
		s += SuccessStyle.Render("  ✓ Docker Ollama already running on port 11434") + "\n"
	}

	// Informational note when the host `ollama` CLI binary is present.
	if m.conflict.HostBinaryPath != "" {
		s += "\n" + DimStyle.Render(fmt.Sprintf(
			"  Note: host `ollama` CLI detected at %s.\n"+
				"  This is harmless — the CLI is just a client and will talk\n"+
				"  to the Docker Ollama via the exposed port.",
			m.conflict.HostBinaryPath)) + "\n"
	}

	s += "\n" + DimStyle.Render("  Press Enter to continue.") + "\n"
	return s
}
