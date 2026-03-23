package wizard

import (
	"fmt"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/huh"
)

// apiKeysPhase tracks the API keys screen progression.
type apiKeysPhase int

const (
	apiKeysPhaseSelect apiKeysPhase = iota // Choose providers
	apiKeysPhaseInput                      // Enter key for each selected provider
)

// providerDef describes a cloud LLM provider.
type providerDef struct {
	ID          string // "openai", "anthropic", "openrouter"
	Label       string // Display name
	Placeholder string // Input placeholder hint
}

var knownProviders = []providerDef{
	{ID: "openai", Label: "OpenAI", Placeholder: "sk-..."},
	{ID: "anthropic", Label: "Anthropic", Placeholder: "sk-ant-..."},
	{ID: "openrouter", Label: "OpenRouter", Placeholder: "sk-or-..."},
}

// APIKeysModel is the bubbletea model for API key configuration (Screen 7).
type APIKeysModel struct {
	state     *WizardState
	phase     apiKeysPhase
	form      *huh.Form
	formDone  bool
	selected  []string // provider IDs chosen in phase 1
	providers []providerDef
	inputIdx  int    // which provider key we are currently collecting
	inputVal  string // current input value (bound to huh.Input)
	width     int
}

// NewAPIKeysModel creates the API keys screen.
func NewAPIKeysModel(state *WizardState) APIKeysModel {
	m := APIKeysModel{state: state}
	m.form = m.buildSelectForm()
	return m
}

// buildSelectForm creates the provider multi-select form (phase 1).
func (m *APIKeysModel) buildSelectForm() *huh.Form {
	sel := huh.NewMultiSelect[string]().
		Title("Cloud Provider API Keys (Optional)").
		Description("Space to toggle, Enter to confirm. Press Enter with nothing selected to skip.").
		Options(
			huh.NewOption("OpenAI", "openai"),
			huh.NewOption("Anthropic", "anthropic"),
			huh.NewOption("OpenRouter", "openrouter"),
		).
		Filterable(false).
		Value(&m.selected)

	return huh.NewForm(huh.NewGroup(sel)).WithShowHelp(false)
}

// buildKeyInputForm creates a password input form for a single provider (phase 2).
func (m *APIKeysModel) buildKeyInputForm(prov providerDef) *huh.Form {
	m.inputVal = "" // Reset for each provider.

	input := huh.NewInput().
		Title(fmt.Sprintf("%s API Key", prov.Label)).
		Description(fmt.Sprintf("Paste your %s API key (hidden). Leave empty to skip.", prov.Label)).
		Placeholder(prov.Placeholder).
		EchoMode(huh.EchoModePassword).
		Value(&m.inputVal)

	return huh.NewForm(huh.NewGroup(input)).WithShowHelp(false)
}

func (m APIKeysModel) Init() tea.Cmd {
	return m.form.Init()
}

func (m APIKeysModel) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width = msg.Width
		return m, nil

	case tea.KeyMsg:
		if msg.String() == "ctrl+c" {
			return m, tea.Quit
		}
	}

	form, cmd := m.form.Update(msg)
	if f, ok := form.(*huh.Form); ok {
		m.form = f
	}

	if m.form.State == huh.StateCompleted && !m.formDone {
		m.formDone = true

		switch m.phase {
		case apiKeysPhaseSelect:
			return m.handleSelectionDone()
		case apiKeysPhaseInput:
			return m.handleKeyInputDone()
		}
	}

	return m, cmd
}

// handleSelectionDone processes the provider selection and transitions to key input.
func (m APIKeysModel) handleSelectionDone() (tea.Model, tea.Cmd) {
	// No providers selected -- skip to next screen.
	if len(m.selected) == 0 {
		return m, func() tea.Msg { return NextScreenMsg{} }
	}

	// Build the ordered list of providers to collect keys for.
	m.providers = nil
	for _, prov := range knownProviders {
		for _, sel := range m.selected {
			if sel == prov.ID {
				m.providers = append(m.providers, prov)
				break
			}
		}
	}

	// Transition to key input phase.
	m.phase = apiKeysPhaseInput
	m.inputIdx = 0
	m.formDone = false
	m.form = m.buildKeyInputForm(m.providers[0])
	return m, m.form.Init()
}

// handleKeyInputDone stores the entered key and advances to the next provider or screen.
func (m APIKeysModel) handleKeyInputDone() (tea.Model, tea.Cmd) {
	// Store the key in wizard state.
	prov := m.providers[m.inputIdx]
	m.storeKey(prov.ID, m.inputVal)

	// Advance to next provider.
	m.inputIdx++
	if m.inputIdx < len(m.providers) {
		m.formDone = false
		m.form = m.buildKeyInputForm(m.providers[m.inputIdx])
		return m, m.form.Init()
	}

	// All keys collected -- advance to next screen.
	return m, func() tea.Msg { return NextScreenMsg{} }
}

// storeKey saves an API key into the wizard state.
func (m *APIKeysModel) storeKey(providerID, key string) {
	switch providerID {
	case "openai":
		m.state.OpenAIKey = key
		m.state.UseOpenAI = key != ""
	case "anthropic":
		m.state.AnthropicKey = key
		m.state.UseAnthropic = key != ""
	case "openrouter":
		m.state.OpenRouterKey = key
		m.state.UseOpenRouter = key != ""
	}
}

func (m APIKeysModel) View() string {
	s := TitleStyle.Render("  Cloud Provider API Keys") + "\n\n"
	s += "  The Embedinator uses Ollama for local inference by default.\n"
	s += "  You can optionally configure cloud LLM providers.\n\n"

	if m.phase == apiKeysPhaseInput && m.inputIdx < len(m.providers) {
		// Show progress indicator for multi-key entry.
		s += DimStyle.Render(fmt.Sprintf("  Provider %d of %d", m.inputIdx+1, len(m.providers))) + "\n\n"
	}

	s += m.form.View()

	return s
}
