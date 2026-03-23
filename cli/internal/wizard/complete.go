package wizard

import (
	"fmt"
	"os/exec"
	"runtime"

	tea "github.com/charmbracelet/bubbletea"
)

// CompleteModel is the bubbletea model for the completion screen (Screen 10).
type CompleteModel struct {
	state *WizardState
	width int
}

// NewCompleteModel creates the completion screen.
func NewCompleteModel(state *WizardState) CompleteModel {
	return CompleteModel{state: state}
}

func (m CompleteModel) Init() tea.Cmd {
	return nil
}

func (m CompleteModel) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width = msg.Width
		return m, nil

	case tea.KeyMsg:
		switch msg.String() {
		case "enter", "q", "ctrl+c":
			return m, tea.Quit
		case "o":
			// Open browser.
			url := fmt.Sprintf("http://localhost:%d", m.state.Ports.Frontend)
			openBrowser(url)
			return m, nil
		}
	}

	return m, nil
}

func (m CompleteModel) View() string {
	successContent := fmt.Sprintf(`
   %s  The Embedinator is ready!

   Application    http://localhost:%d
   Backend API    http://localhost:%d
   API Docs       http://localhost:%d/docs
`,
		CheckMark,
		m.state.Ports.Frontend,
		m.state.Ports.Backend,
		m.state.Ports.Backend,
	)

	s := SuccessBoxStyle.Render(successContent) + "\n\n"

	s += "  Quick Start:\n"
	s += fmt.Sprintf("    1. Open http://localhost:%d in your browser\n", m.state.Ports.Frontend)
	s += "    2. Create a collection in the Collections tab\n"
	s += "    3. Upload a PDF, Markdown, or text file\n"
	s += "    4. Start asking questions in the Chat tab\n\n"

	s += "  Common Commands:\n"
	s += "    embedinator status    Show service health\n"
	s += "    embedinator stop      Stop all services\n"
	s += "    embedinator start     Start services again\n"
	s += "    embedinator logs      Stream all logs\n"
	s += "    embedinator config    Re-run configuration wizard\n"
	s += "    embedinator doctor    Diagnose common problems\n\n"

	s += DimStyle.Render("  Press Enter to exit, or o to open in browser.") + "\n"

	return s
}

// openBrowser opens a URL in the user's default browser.
func openBrowser(url string) {
	switch runtime.GOOS {
	case "darwin":
		exec.Command("open", url).Start()
	case "linux":
		exec.Command("xdg-open", url).Start()
	case "windows":
		exec.Command("rundll32", "url.dll,FileProtocolHandler", url).Start()
	}
}
