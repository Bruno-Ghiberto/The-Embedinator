package wizard

import (
	"fmt"
	"strings"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/huh"
)

// ModelChoice represents a selectable model with metadata.
type ModelChoice struct {
	Name        string
	Size        string
	Description string
}

// Available LLM models.
var LLMModels = []ModelChoice{
	{Name: "qwen2.5:7b", Size: "4.4 GB", Description: "Default, good balance of quality and speed"},
	{Name: "llama3.2:3b", Size: "2.0 GB", Description: "Smaller, faster, less accurate"},
	{Name: "mistral:7b", Size: "4.1 GB", Description: "Strong general-purpose model"},
	{Name: "gemma2:9b", Size: "5.4 GB", Description: "Google's model, good at reasoning"},
	{Name: "phi4:14b", Size: "8.4 GB", Description: "Microsoft's model, needs more RAM"},
}

// Available embedding models.
var EmbeddingModels = []ModelChoice{
	{Name: "nomic-embed-text", Size: "274 MB", Description: "Default, high quality embeddings"},
	{Name: "mxbai-embed-large", Size: "669 MB", Description: "Larger, slightly better quality"},
	{Name: "all-minilm", Size: "45 MB", Description: "Tiny, fast, lower quality"},
}

// ModelsModel is the bubbletea model for model selection (Screen 6).
type ModelsModel struct {
	state    *WizardState
	form     *huh.Form
	formDone bool
	width    int
}

// NewModelsModel creates the model selection screen.
func NewModelsModel(state *WizardState) ModelsModel {
	m := ModelsModel{state: state}
	m.form = m.buildForm()
	return m
}

func (m ModelsModel) buildForm() *huh.Form {
	llmOptions := make([]huh.Option[string], len(LLMModels))
	for i, model := range LLMModels {
		label := fmt.Sprintf("%-24s (%s) %s", model.Name, model.Size, model.Description)
		llmOptions[i] = huh.NewOption(label, model.Name)
	}

	embedOptions := make([]huh.Option[string], len(EmbeddingModels))
	for i, model := range EmbeddingModels {
		label := fmt.Sprintf("%-24s (%s) %s", model.Name, model.Size, model.Description)
		embedOptions[i] = huh.NewOption(label, model.Name)
	}

	llmSelect := huh.NewMultiSelect[string]().
		Title("LLM Model (for answering questions)").
		Options(llmOptions...).
		Value(&m.state.LLMModels)

	embedSelect := huh.NewMultiSelect[string]().
		Title("Embedding Model (for document search)").
		Options(embedOptions...).
		Value(&m.state.EmbeddingModels)

	return huh.NewForm(
		huh.NewGroup(llmSelect),
		huh.NewGroup(embedSelect),
	).WithShowHelp(true)
}

func (m ModelsModel) Init() tea.Cmd {
	return m.form.Init()
}

func (m ModelsModel) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
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

		// Validate at least one of each.
		if len(m.state.LLMModels) == 0 {
			m.state.LLMModels = []string{"qwen2.5:7b"}
		}
		if len(m.state.EmbeddingModels) == 0 {
			m.state.EmbeddingModels = []string{"nomic-embed-text"}
		}

		return m, func() tea.Msg { return NextScreenMsg{} }
	}

	return m, cmd
}

func (m ModelsModel) View() string {
	s := TitleStyle.Render("  AI Model Selection") + "\n\n"
	s += "  Choose which models to download. Models are downloaded after services start.\n\n"

	s += m.form.View()

	// Show total size estimate.
	if len(m.state.LLMModels) > 0 || len(m.state.EmbeddingModels) > 0 {
		s += "\n" + DimStyle.Render(fmt.Sprintf("  Selected: %s", strings.Join(append(m.state.LLMModels, m.state.EmbeddingModels...), ", ")))
	}

	return s
}
