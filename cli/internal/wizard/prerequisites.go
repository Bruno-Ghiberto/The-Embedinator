package wizard

import (
	"fmt"
	"time"

	"github.com/charmbracelet/bubbles/spinner"
	tea "github.com/charmbracelet/bubbletea"

	"github.com/Bruno-Ghiberto/The-Embedinator/cli/internal/engine"
)

// PrerequisitesModel is the bubbletea model for preflight checks (Screen 2).
type PrerequisitesModel struct {
	state      *WizardState
	results    []engine.PreflightResult
	running    bool
	done       bool
	allPassed  bool
	spinner    spinner.Model
	width      int
}

type preflightDoneMsg struct {
	results []engine.PreflightResult
}

// NewPrerequisitesModel creates the prerequisites screen model.
func NewPrerequisitesModel(state *WizardState) PrerequisitesModel {
	s := spinner.New()
	s.Spinner = spinner.Dot
	s.Style = TitleStyle
	return PrerequisitesModel{
		state:   state,
		spinner: s,
	}
}

func (m PrerequisitesModel) Init() tea.Cmd {
	return tea.Batch(m.spinner.Tick, m.runChecks())
}

func (m PrerequisitesModel) runChecks() tea.Cmd {
	return func() tea.Msg {
		// Small delay so the spinner is visible.
		time.Sleep(500 * time.Millisecond)
		results := engine.RunAllPreflights(m.state.ProjectDir)
		return preflightDoneMsg{results: results}
	}
}

func (m PrerequisitesModel) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width = msg.Width
		return m, nil

	case spinner.TickMsg:
		if !m.done {
			var cmd tea.Cmd
			m.spinner, cmd = m.spinner.Update(msg)
			return m, cmd
		}
		return m, nil

	case preflightDoneMsg:
		m.results = msg.results
		m.done = true
		m.allPassed = engine.AllPreflightsPassed(msg.results)
		m.state.PreflightResults = msg.results
		return m, nil

	case tea.KeyMsg:
		switch msg.String() {
		case "enter":
			if m.done && m.allPassed {
				return m, func() tea.Msg { return NextScreenMsg{} }
			}
			if m.done && !m.allPassed {
				// Retry checks.
				m.done = false
				m.results = nil
				return m, tea.Batch(m.spinner.Tick, m.runChecks())
			}
		case "q", "ctrl+c":
			return m, tea.Quit
		}
	}

	return m, nil
}

func (m PrerequisitesModel) View() string {
	s := TitleStyle.Render("  Checking prerequisites...") + "\n\n"

	if !m.done {
		s += fmt.Sprintf("    %s Running checks...\n", m.spinner.View())
		return s
	}

	for _, r := range m.results {
		if r.OK {
			s += fmt.Sprintf("    %s %-24s %s\n", CheckMark, r.Name, DimStyle.Render(r.Detail))
		} else {
			s += fmt.Sprintf("    %s %-24s %s\n", CrossMark, r.Name, ErrorStyle.Render(r.Error))
		}
	}

	s += "\n"

	if m.allPassed {
		s += SuccessStyle.Render("  All prerequisites met.") + "\n\n"
		s += DimStyle.Render("  Press Enter to continue.") + "\n"
	} else {
		s += "\n" + ErrorBoxStyle.Render("Some prerequisites failed. Fix the issues above and press Enter to retry.") + "\n\n"
		s += DimStyle.Render("  Press Enter to retry, or q to quit.") + "\n"
	}

	return s
}
