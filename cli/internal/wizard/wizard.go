package wizard

import (
	tea "github.com/charmbracelet/bubbletea"
)

// NextScreenMsg signals the wizard to advance to the next screen.
type NextScreenMsg struct{}

// GoBackMsg signals the wizard to return to a specific screen.
type GoBackMsg struct {
	Target Screen
}

// WizardModel is the top-level bubbletea model that manages screen flow.
type WizardModel struct {
	state         *WizardState
	currentScreen Screen
	screenModel   tea.Model
	width         int
	height        int
}

// NewWizardModel creates the top-level wizard model.
func NewWizardModel(state *WizardState) WizardModel {
	w := WizardModel{
		state:         state,
		currentScreen: ScreenWelcome,
	}
	w.screenModel = NewWelcomeModel()
	return w
}

// NewConfigWizardModel creates a wizard that starts at the Ollama screen (for `embedinator config`).
func NewConfigWizardModel(state *WizardState) WizardModel {
	w := WizardModel{
		state:         state,
		currentScreen: ScreenOllama,
	}
	w.screenModel = NewOllamaModel(state)
	return w
}

func (m WizardModel) Init() tea.Cmd {
	return m.screenModel.Init()
}

func (m WizardModel) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height
		// Forward to current screen.
		updated, cmd := m.screenModel.Update(msg)
		m.screenModel = updated
		return m, cmd

	case NextScreenMsg:
		return m.advanceScreen()

	case GoBackMsg:
		return m.goToScreen(msg.Target)
	}

	// Forward all other messages to the current screen.
	updated, cmd := m.screenModel.Update(msg)
	m.screenModel = updated
	return m, cmd
}

func (m WizardModel) View() string {
	return m.screenModel.View()
}

// advanceScreen moves to the next screen in sequence.
func (m WizardModel) advanceScreen() (tea.Model, tea.Cmd) {
	next := m.currentScreen + 1

	// Skip GPU screen if using local ollama on macOS (already handled in GPU screen itself).
	// Skip based on sequential flow.

	return m.goToScreen(next)
}

// goToScreen switches to the specified screen.
func (m WizardModel) goToScreen(screen Screen) (tea.Model, tea.Cmd) {
	m.currentScreen = screen

	switch screen {
	case ScreenWelcome:
		m.screenModel = NewWelcomeModel()
	case ScreenPrerequisites:
		m.screenModel = NewPrerequisitesModel(m.state)
	case ScreenOllama:
		m.screenModel = NewOllamaModel(m.state)
	case ScreenPorts:
		m.screenModel = NewPortsModel(m.state)
	case ScreenGPU:
		m.screenModel = NewGPUModel(m.state)
	case ScreenModels:
		m.screenModel = NewModelsModel(m.state)
	case ScreenAPIKeys:
		m.screenModel = NewAPIKeysModel(m.state)
	case ScreenSummary:
		m.screenModel = NewSummaryModel(m.state)
	case ScreenProgress:
		m.screenModel = NewProgressModel(m.state)
	case ScreenComplete:
		m.screenModel = NewCompleteModel(m.state)
	default:
		return m, tea.Quit
	}

	return m, m.screenModel.Init()
}

// Run starts the wizard TUI.
func Run(state *WizardState) error {
	model := NewWizardModel(state)
	p := tea.NewProgram(model, tea.WithAltScreen())
	_, err := p.Run()
	return err
}

// RunConfig starts the config-only wizard (screens 3-8).
func RunConfig(state *WizardState) error {
	model := NewConfigWizardModel(state)
	p := tea.NewProgram(model, tea.WithAltScreen())
	_, err := p.Run()
	return err
}
