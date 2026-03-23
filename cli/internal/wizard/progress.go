package wizard

import (
	"context"
	"fmt"
	"path/filepath"
	"time"

	"github.com/charmbracelet/bubbles/spinner"
	tea "github.com/charmbracelet/bubbletea"

	"github.com/Bruno-Ghiberto/The-Embedinator/cli/internal/engine"
)

// ProgressModel is the bubbletea model for installation progress (Screen 9).
type ProgressModel struct {
	state       *WizardState
	spinner     spinner.Model
	phase       installPhase
	elapsed     time.Duration
	startTime   time.Time
	healthState map[string]serviceStatus // per-service health status
	healthOrder []string                 // ordered service names for display
	modelState  []modelPullState
	err         error
	logPath     string // path to compose log file on error
	done        bool
	width       int
}

type installPhase int

const (
	phaseComposeUp installPhase = iota
	phaseHealthCheck
	phaseModelPull
	phaseDone
)

type serviceStatus int

const (
	statusPending serviceStatus = iota
	statusActive
	statusDone
	statusFailed
)

type modelPullState struct {
	Name   string
	Status string // queued | pulling | done | error
}

// Progress messages.
type composeUpDoneMsg struct{ err error }
type healthDoneMsg struct{ err error }
type modelPullDoneMsg struct {
	index int
	err   error
}
type installTickMsg struct{}

// NewProgressModel creates the installation progress screen.
func NewProgressModel(state *WizardState) ProgressModel {
	s := spinner.New()
	s.Spinner = spinner.Dot
	s.Style = TitleStyle

	models := make([]modelPullState, 0, len(state.LLMModels)+len(state.EmbeddingModels))
	for _, m := range state.LLMModels {
		models = append(models, modelPullState{Name: m, Status: "queued"})
	}
	for _, m := range state.EmbeddingModels {
		models = append(models, modelPullState{Name: m, Status: "queued"})
	}

	healthOrder := []string{"qdrant", "ollama", "backend", "frontend"}
	healthState := make(map[string]serviceStatus, len(healthOrder))
	for _, name := range healthOrder {
		healthState[name] = statusPending
	}

	return ProgressModel{
		state:       state,
		spinner:     s,
		modelState:  models,
		healthState: healthState,
		healthOrder: healthOrder,
		startTime:   time.Now(),
	}
}

func (m ProgressModel) Init() tea.Cmd {
	return tea.Batch(
		m.spinner.Tick,
		m.tickElapsed(),
		m.runComposeUp(),
	)
}

func (m ProgressModel) tickElapsed() tea.Cmd {
	return tea.Tick(time.Second, func(time.Time) tea.Msg {
		return installTickMsg{}
	})
}

func (m ProgressModel) runComposeUp() tea.Cmd {
	return func() tea.Msg {
		cfg := m.state.ToConfig()

		// Auto-generate Fernet key if not already set.
		if m.state.FernetKey == "" {
			m.state.FernetKey = engine.GenerateFernetKey()
		}

		// Generate .env.
		envPath := filepath.Join(m.state.ProjectDir, ".env")
		examplePath := filepath.Join(m.state.ProjectDir, ".env.example")
		_ = engine.GenerateDotEnv(envPath, examplePath, cfg, m.state.FernetKey)

		// Generate config.yaml.
		configPath := filepath.Join(m.state.ProjectDir, "config.yaml")
		_ = engine.WriteConfig(configPath, cfg)

		// Generate overlay if needed.
		if cfg.Ollama.Mode == "local" {
			url := "http://host.docker.internal:11434"
			if cfg.Ollama.RemoteURL != "" {
				url = cfg.Ollama.RemoteURL
			}
			_ = engine.GenerateLocalOllamaOverlay(m.state.ProjectDir, url)
		} else {
			_ = engine.RemoveLocalOllamaOverlay(m.state.ProjectDir)
		}

		// Run docker compose up (output captured to log file).
		composeArgs := engine.BuildComposeArgs(cfg)
		err := engine.ComposeUp(m.state.ProjectDir, composeArgs, true)
		return composeUpDoneMsg{err: err}
	}
}

func (m ProgressModel) runHealthCheck() tea.Cmd {
	return func() tea.Msg {
		cfg := m.state.ToConfig()
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Minute)
		defer cancel()

		err := engine.PollHealth(ctx, cfg, 3*time.Second, func(results []engine.ServiceHealth) {
			// PollHealth callback — results are consumed on completion.
		})
		return healthDoneMsg{err: err}
	}
}

func (m ProgressModel) runModelPull(index int) tea.Cmd {
	return func() tea.Msg {
		model := m.modelState[index].Name
		useLocal := m.state.OllamaMode == "local"
		err := engine.PullModel(m.state.ProjectDir, model, useLocal)
		return modelPullDoneMsg{index: index, err: err}
	}
}

func (m ProgressModel) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width = msg.Width
		return m, nil

	case spinner.TickMsg:
		var cmd tea.Cmd
		m.spinner, cmd = m.spinner.Update(msg)
		return m, cmd

	case installTickMsg:
		m.elapsed = time.Since(m.startTime)
		if !m.done {
			return m, m.tickElapsed()
		}
		return m, nil

	case composeUpDoneMsg:
		if msg.err != nil {
			m.err = msg.err
			m.logPath = engine.ComposeLogPath(msg.err)
			m.done = true
			m.state.InstallError = msg.err
			return m, nil
		}
		m.phase = phaseHealthCheck
		// Mark all health checks as active.
		for _, name := range m.healthOrder {
			m.healthState[name] = statusActive
		}
		return m, m.runHealthCheck()

	case healthDoneMsg:
		if msg.err != nil {
			// Mark all still-active services as failed.
			for _, name := range m.healthOrder {
				if m.healthState[name] == statusActive {
					m.healthState[name] = statusFailed
				}
			}
			m.err = msg.err
			m.done = true
			m.state.InstallError = msg.err
			return m, nil
		}
		// All healthy — mark all services as done.
		for _, name := range m.healthOrder {
			m.healthState[name] = statusDone
		}
		m.phase = phaseModelPull
		// Start pulling models sequentially.
		if len(m.modelState) > 0 {
			m.modelState[0].Status = "pulling"
			return m, m.runModelPull(0)
		}
		m.phase = phaseDone
		m.done = true
		m.state.InstallDone = true
		return m, func() tea.Msg { return NextScreenMsg{} }

	case modelPullDoneMsg:
		if msg.err != nil {
			m.modelState[msg.index].Status = "error"
		} else {
			m.modelState[msg.index].Status = "done"
		}

		// Pull next model.
		next := msg.index + 1
		if next < len(m.modelState) {
			m.modelState[next].Status = "pulling"
			return m, m.runModelPull(next)
		}

		// All models done.
		m.phase = phaseDone
		m.done = true
		m.state.InstallDone = true
		return m, func() tea.Msg { return NextScreenMsg{} }

	case tea.KeyMsg:
		switch msg.String() {
		case "ctrl+c":
			// Cleanup: stop docker compose.
			cfg := m.state.ToConfig()
			composeArgs := engine.BuildComposeArgs(cfg)
			_ = engine.ComposeDown(m.state.ProjectDir, composeArgs, false)
			return m, tea.Quit
		}
	}

	return m, nil
}

// ---------------------------------------------------------------------------
// View — clean, step-by-step progress display.
// ---------------------------------------------------------------------------

// serviceDisplayName returns the user-friendly display name for a service.
var serviceDisplayNames = map[string]string{
	"qdrant":   "Qdrant",
	"ollama":   "Ollama",
	"backend":  "Backend",
	"frontend": "Frontend",
}

func (m ProgressModel) View() string {
	s := TitleStyle.Render("  Installing The Embedinator") + "\n\n"

	// --- Step 1: Building images ---
	s += m.viewStepLine(
		"Building images...", "Images built",
		m.phase == phaseComposeUp,       // active when compose is running
		m.phase > phaseComposeUp,        // done when compose finishes
		m.err != nil && m.phase == phaseComposeUp, // failed
	)

	// --- Step 2: Starting containers ---
	s += m.viewStepLine(
		"Starting containers...", "Containers started",
		m.phase == phaseComposeUp,       // active during compose (build+start is one op)
		m.phase > phaseComposeUp,        // done when compose finishes
		m.err != nil && m.phase == phaseComposeUp,
	)

	// --- Steps 3-6: Per-service health checks ---
	for _, name := range m.healthOrder {
		status := m.healthState[name]
		displayName := serviceDisplayNames[name]
		if displayName == "" {
			displayName = name
		}

		s += m.viewStepLine(
			fmt.Sprintf("Waiting for %s...", displayName),
			fmt.Sprintf("%s healthy", displayName),
			status == statusActive,
			status == statusDone,
			status == statusFailed,
		)
	}

	// --- Model downloads ---
	if m.phase >= phaseModelPull && len(m.modelState) > 0 {
		s += "\n"
		for _, ms := range m.modelState {
			icon := DotMark
			label := ms.Name
			switch ms.Status {
			case "pulling":
				icon = m.spinner.View()
				label = fmt.Sprintf("Pulling %s...", ms.Name)
			case "done":
				icon = CheckMark
				label = fmt.Sprintf("%s ready", ms.Name)
			case "error":
				icon = CrossMark
				label = fmt.Sprintf("%s failed", ms.Name)
			}
			s += fmt.Sprintf("  %s %s\n", icon, label)
		}
	}

	s += "\n"

	// --- Error display ---
	if m.err != nil {
		errMsg := fmt.Sprintf("Error: %v", m.err)
		if m.logPath != "" {
			errMsg += fmt.Sprintf("\n\nFull log: %s", m.logPath)
		}
		errMsg += "\n\nRun 'embedinator logs' to debug."
		s += ErrorBoxStyle.Render(errMsg) + "\n"
	}

	// --- Elapsed time ---
	s += DimStyle.Render(fmt.Sprintf("  Elapsed: %s", m.elapsed.Truncate(time.Second))) + "\n"

	return s
}

// viewStepLine renders a single step as a line with icon + label.
// Only one of isActive/isDone/isFailed should be true at a time.
// If none are true, the step is pending and not yet shown.
func (m ProgressModel) viewStepLine(activeLabel, doneLabel string, isActive, isDone, isFailed bool) string {
	switch {
	case isFailed:
		return fmt.Sprintf("  %s %s\n", CrossMark, activeLabel)
	case isDone:
		return fmt.Sprintf("  %s %s\n", CheckMark, doneLabel)
	case isActive:
		return fmt.Sprintf("  %s %s\n", m.spinner.View(), activeLabel)
	default:
		// Pending — not shown yet.
		return ""
	}
}
