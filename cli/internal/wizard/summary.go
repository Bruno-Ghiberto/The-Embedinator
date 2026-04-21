package wizard

import (
	"fmt"
	"strings"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/huh"
)

// SummaryModel is the bubbletea model for the summary screen (Screen 8).
type SummaryModel struct {
	state    *WizardState
	form     *huh.Form
	formDone bool
	choice   string
	width    int
}

// NewSummaryModel creates the summary and confirmation screen.
func NewSummaryModel(state *WizardState) SummaryModel {
	m := SummaryModel{state: state, choice: "confirm"}
	m.form = m.buildForm()
	return m
}

func (m SummaryModel) buildForm() *huh.Form {
	sel := huh.NewSelect[string]().
		Title("").
		Options(
			huh.NewOption("Confirm and install", "confirm"),
			huh.NewOption("Edit configuration (go back)", "edit"),
			huh.NewOption("Abort", "abort"),
		).
		Value(&m.choice)

	return huh.NewForm(huh.NewGroup(sel)).WithShowHelp(false)
}

func (m SummaryModel) Init() tea.Cmd {
	return m.form.Init()
}

func (m SummaryModel) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
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

		switch m.choice {
		case "confirm":
			return m, func() tea.Msg { return NextScreenMsg{} }
		case "edit":
			return m, func() tea.Msg { return GoBackMsg{Target: ScreenOllama} }
		case "abort":
			return m, tea.Quit
		}
	}

	return m, cmd
}

func (m SummaryModel) View() string {
	s := TitleStyle.Render("  Configuration Summary") + "\n\n"

	// Build summary table.
	ollamaDesc := m.state.OllamaMode
	if m.state.OllamaMode == "docker" && m.state.GPUResult.Profile != "none" {
		ollamaDesc = fmt.Sprintf("Docker (GPU: %s)", strings.ToUpper(m.state.GPUResult.Profile))
	}
	if m.state.OllamaMode == "local" {
		ollamaDesc = "Local (native)"
	}
	if m.state.OllamaMode == "remote" {
		ollamaDesc = fmt.Sprintf("Remote (%s)", m.state.OllamaRemoteURL)
	}

	lines := []string{
		fmt.Sprintf("  %-16s %s", "Ollama", ollamaDesc),
		fmt.Sprintf("  %-16s http://localhost:%d", "Frontend", m.state.Ports.Frontend),
		fmt.Sprintf("  %-16s http://localhost:%d", "Backend API", m.state.Ports.Backend),
		fmt.Sprintf("  %-16s http://localhost:%d", "Qdrant", m.state.Ports.Qdrant),
		fmt.Sprintf("  %-16s http://localhost:%d", "Ollama API", m.state.Ports.Ollama),
		fmt.Sprintf("  %-16s %s", "LLM Models", strings.Join(m.state.LLMModels, ", ")),
		fmt.Sprintf("  %-16s %s", "Embed Models", strings.Join(m.state.EmbeddingModels, ", ")),
		fmt.Sprintf("  %-16s %s", "GPU Profile", m.state.GPUResult.Profile),
		fmt.Sprintf("  %-16s %s", "Fernet Key", "auto-generated ✓"),
	}

	// Show cloud provider status.
	var providers []string
	if m.state.UseOpenAI {
		providers = append(providers, "OpenAI")
	}
	if m.state.UseAnthropic {
		providers = append(providers, "Anthropic")
	}
	if m.state.UseOpenRouter {
		providers = append(providers, "OpenRouter")
	}
	if len(providers) > 0 {
		lines = append(lines, fmt.Sprintf("  %-16s %s", "Cloud LLMs", strings.Join(providers, ", ")))
	} else {
		lines = append(lines, fmt.Sprintf("  %-16s %s", "Cloud LLMs", "none (local only)"))
	}

	table := SummaryBoxStyle.Render(strings.Join(lines, "\n"))
	s += table + "\n\n"

	s += "  The following files will be created/updated:\n"
	s += DimStyle.Render("    .env                          Environment configuration") + "\n"
	s += DimStyle.Render("    config.yaml                   TUI settings (re-runnable)") + "\n\n"

	s += "  The following Docker operations will run:\n"
	s += DimStyle.Render("    docker compose up --build -d  Build and start all services") + "\n"
	for _, model := range m.state.LLMModels {
		s += DimStyle.Render(fmt.Sprintf("    ollama pull %-18s Download LLM model", model)) + "\n"
	}
	for _, model := range m.state.EmbeddingModels {
		s += DimStyle.Render(fmt.Sprintf("    ollama pull %-18s Download embedding model", model)) + "\n"
	}

	s += "\n" + m.form.View()

	return s
}
