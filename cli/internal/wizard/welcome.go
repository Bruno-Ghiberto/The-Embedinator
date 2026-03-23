package wizard

import (
	"fmt"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"

	"github.com/Bruno-Ghiberto/The-Embedinator/cli/internal/version"
)

// WelcomeModel is the bubbletea model for the welcome screen (Screen 1).
type WelcomeModel struct {
	width  int
	height int
}

// NewWelcomeModel creates a new welcome screen model.
func NewWelcomeModel() WelcomeModel {
	return WelcomeModel{}
}

func (m WelcomeModel) Init() tea.Cmd {
	return nil
}

func (m WelcomeModel) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height
		return m, nil

	case tea.KeyMsg:
		switch msg.String() {
		case "enter":
			return m, func() tea.Msg { return NextScreenMsg{} }
		case "q", "ctrl+c":
			return m, tea.Quit
		}
	}

	return m, nil
}

func (m WelcomeModel) View() string {
	var s string

	if m.width >= 60 {
		// Large layout: full gorilla + full banner.
		gorilla := lipgloss.NewStyle().
			Foreground(ColorCyan).
			Render(GorillaASCII)

		banner := lipgloss.NewStyle().
			Foreground(ColorPurple).
			Bold(true).
			Render(EmbeddinatorBanner)

		s = gorilla + "\n" + banner
	} else {
		// Narrow layout: small gorilla + small banner.
		gorilla := lipgloss.NewStyle().
			Foreground(ColorCyan).
			Render(GorillaASCIISmall)

		banner := AccentStyle.Render(EmbeddinatorBannerSmall)
		s = gorilla + "\n" + banner
	}

	tagline := SubtitleStyle.Render("Self-hosted agentic RAG for private documents")
	ver := DimStyle.Render(fmt.Sprintf("v%s", version.Version))

	info := `
  Welcome! This wizard will configure and install The Embedinator.

  It will:
    1. Check prerequisites (Docker, disk space, RAM)
    2. Configure Ollama (local AI inference)
    3. Set up ports and GPU detection
    4. Choose AI models to download
    5. Optionally configure cloud AI providers
    6. Start all services via Docker Compose

  Estimated time: 5-15 minutes (depending on internet speed)
`

	prompt := DimStyle.Render("  Press Enter to begin, or q to quit.")

	return s + "\n  " + tagline + "\n  " + ver + "\n" + info + "\n" + prompt + "\n"
}
