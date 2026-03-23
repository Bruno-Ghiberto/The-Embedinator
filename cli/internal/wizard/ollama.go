package wizard

import (
	"fmt"
	"net/http"
	"net/url"
	"runtime"
	"time"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/huh"

	"github.com/Bruno-Ghiberto/The-Embedinator/cli/internal/engine"
)

// ollamaPhase tracks the Ollama screen progression.
type ollamaPhase int

const (
	ollamaPhaseDetect ollamaPhase = iota // Detecting local Ollama
	ollamaPhaseSelect                    // Mode selection form
	ollamaPhaseURL                       // Remote URL input
)

// OllamaModel is the bubbletea model for Ollama configuration (Screen 3).
type OllamaModel struct {
	state     *WizardState
	detection engine.OllamaDetection
	phase     ollamaPhase
	form      *huh.Form
	formDone  bool
	urlValue  string // bound to the URL input field
	urlError  string // connectivity test result
	width     int
}

type ollamaDetectDoneMsg struct {
	detection engine.OllamaDetection
}

type ollamaURLTestMsg struct {
	ok  bool
	err string
}

// NewOllamaModel creates the Ollama configuration screen.
func NewOllamaModel(state *WizardState) OllamaModel {
	return OllamaModel{
		state:    state,
		urlValue: "http://host.docker.internal:11434",
	}
}

func (m OllamaModel) Init() tea.Cmd {
	return func() tea.Msg {
		detection := engine.DetectLocalOllama()
		return ollamaDetectDoneMsg{detection: detection}
	}
}

func (m OllamaModel) buildModeForm() *huh.Form {
	options := []huh.Option[string]{
		huh.NewOption("Use Docker Ollama (recommended)", "docker"),
	}

	if m.detection.Running && m.detection.APIReachable {
		label := fmt.Sprintf("Use my local Ollama (v%s, %d models)", m.detection.Version, len(m.detection.Models))
		if runtime.GOOS == "darwin" {
			label += " - recommended for macOS Metal GPU"
		}
		options = append(options, huh.NewOption(label, "local"))
	}

	options = append(options, huh.NewOption("Use a remote Ollama (enter URL manually)", "remote"))

	modeSelect := huh.NewSelect[string]().
		Title("Ollama Configuration").
		Description("Choose how The Embedinator connects to Ollama for AI inference.").
		Options(options...).
		Value(&m.state.OllamaMode)

	group := huh.NewGroup(modeSelect)

	return huh.NewForm(group).WithShowHelp(false)
}

func (m OllamaModel) buildURLForm() *huh.Form {
	input := huh.NewInput().
		Title("Remote Ollama URL").
		Description("Enter the full URL of your remote Ollama instance (including port).").
		Placeholder("http://host.docker.internal:11434").
		Value(&m.urlValue).
		Validate(validateOllamaURL)

	return huh.NewForm(huh.NewGroup(input)).WithShowHelp(false)
}

// validateOllamaURL checks that the URL is well-formed http(s) with a port.
func validateOllamaURL(s string) error {
	if s == "" {
		return fmt.Errorf("URL cannot be empty")
	}
	u, err := url.Parse(s)
	if err != nil {
		return fmt.Errorf("invalid URL: %w", err)
	}
	if u.Scheme != "http" && u.Scheme != "https" {
		return fmt.Errorf("URL must start with http:// or https://")
	}
	if u.Host == "" {
		return fmt.Errorf("URL must include a host")
	}
	if u.Port() == "" {
		return fmt.Errorf("URL must include a port (e.g. :11434)")
	}
	return nil
}

// testOllamaURL checks connectivity to the Ollama URL.
func testOllamaURL(rawURL string) tea.Cmd {
	return func() tea.Msg {
		client := &http.Client{Timeout: 5 * time.Second}
		testURL := rawURL + "/api/tags"
		resp, err := client.Get(testURL)
		if err != nil {
			return ollamaURLTestMsg{ok: false, err: fmt.Sprintf("Connection failed: %v", err)}
		}
		resp.Body.Close()
		if resp.StatusCode >= 500 {
			return ollamaURLTestMsg{ok: false, err: fmt.Sprintf("Server error: HTTP %d", resp.StatusCode)}
		}
		return ollamaURLTestMsg{ok: true}
	}
}

func (m OllamaModel) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width = msg.Width
		return m, nil

	case ollamaDetectDoneMsg:
		m.detection = msg.detection
		m.state.OllamaDetection = msg.detection
		m.phase = ollamaPhaseSelect
		m.form = m.buildModeForm()
		return m, m.form.Init()

	case ollamaURLTestMsg:
		if msg.ok {
			m.urlError = ""
			// URL verified -- advance to next screen.
			return m, func() tea.Msg { return NextScreenMsg{} }
		}
		// Show error but still allow proceeding -- the URL might work inside Docker.
		m.urlError = msg.err
		m.state.OllamaRemoteURL = m.urlValue
		return m, func() tea.Msg { return NextScreenMsg{} }

	case tea.KeyMsg:
		if msg.String() == "ctrl+c" {
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

			switch m.phase {
			case ollamaPhaseSelect:
				if m.state.OllamaMode == "remote" {
					// Transition to URL input phase.
					m.phase = ollamaPhaseURL
					m.formDone = false
					m.form = m.buildURLForm()
					return m, m.form.Init()
				}
				// Docker or local -- proceed to next screen.
				return m, func() tea.Msg { return NextScreenMsg{} }

			case ollamaPhaseURL:
				// URL input completed (validation passed). Store and test connectivity.
				m.state.OllamaRemoteURL = m.urlValue
				return m, testOllamaURL(m.urlValue)
			}
		}

		return m, cmd
	}

	return m, nil
}

func (m OllamaModel) View() string {
	s := ""

	if m.phase == ollamaPhaseDetect {
		s += TitleStyle.Render("  Ollama Configuration") + "\n\n"
		s += "  Detecting local Ollama...\n"
		return s
	}

	// Show detection info.
	if m.detection.Running && m.detection.APIReachable {
		s += SuccessStyle.Render(fmt.Sprintf("  Local Ollama detected (v%s)", m.detection.Version)) + "\n"
		if runtime.GOOS == "darwin" {
			s += WarningStyle.Render("  On macOS, local Ollama is STRONGLY recommended (Metal GPU).") + "\n"
		}
		s += "\n"
	} else {
		s += DimStyle.Render("  No local Ollama installation detected.") + "\n\n"
	}

	if m.phase == ollamaPhaseURL {
		s += TitleStyle.Render("  Remote Ollama URL") + "\n\n"
		if m.urlError != "" {
			s += WarningStyle.Render(fmt.Sprintf("  Warning: %s", m.urlError)) + "\n"
			s += DimStyle.Render("  (Proceeding anyway -- the URL may work from inside Docker containers.)") + "\n\n"
		}
	}

	if m.form != nil {
		s += m.form.View()
	}

	return s
}
