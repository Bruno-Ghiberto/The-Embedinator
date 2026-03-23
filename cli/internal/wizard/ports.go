package wizard

import (
	"fmt"
	"strconv"
	"strings"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/huh"

	"github.com/Bruno-Ghiberto/The-Embedinator/cli/internal/engine"
)

// portPhase tracks which phase the port screen is in.
type portPhase int

const (
	portPhaseScanning    portPhase = iota // Phase 1: scanning all ports
	portPhaseResolving                    // Phase 2: interactive resolution per conflict
	portPhaseCustomInput                  // Phase 2b: huh.Input for a custom port number
	portPhaseReview                       // Phase 3: final review table
)

// PortsModel is the bubbletea model for port configuration (Screen 4).
type PortsModel struct {
	state *WizardState

	// Port scan results (indices match AllPortInfos order).
	portStatus []engine.PortStatus

	// Original default ports for "changed from" display in review.
	originalPorts []int

	// Phase state machine.
	phase portPhase

	// Conflict resolution state.
	conflicts   []int   // indices into portStatus that need resolution
	conflictIdx int     // which conflict we are currently resolving
	suggested   int     // suggested next-available port for the current conflict
	choice      *string // "suggested" | "custom" | "keep" — set by huh.Select (heap ptr survives value-receiver copies)

	// Custom port input state.
	customPort    *string // user-typed port string (bound to huh.Input, heap ptr survives value-receiver copies)
	customPortErr string  // validation error to display

	// huh form for the current resolution step.
	form     *huh.Form
	formDone bool

	width int
}

// portScanDoneMsg carries scan results back from the Init command.
type portScanDoneMsg struct {
	status []engine.PortStatus
}

// NewPortsModel creates the port configuration screen.
func NewPortsModel(state *WizardState) PortsModel {
	choice := ""
	customPort := ""
	return PortsModel{
		state:      state,
		phase:      portPhaseScanning,
		choice:     &choice,
		customPort: &customPort,
	}
}

func (m PortsModel) Init() tea.Cmd {
	return func() tea.Msg {
		cfg := engine.Config{Ports: m.state.Ports}
		status := engine.CheckAllPorts(cfg)
		return portScanDoneMsg{status: status}
	}
}

func (m PortsModel) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width = msg.Width
		return m, nil

	case portScanDoneMsg:
		return m.handleScanDone(msg)

	case tea.KeyMsg:
		// ctrl+c always quits, regardless of phase.
		if msg.String() == "ctrl+c" {
			return m, tea.Quit
		}

		// During form phases, forward ALL key events to the huh form.
		if m.form != nil && (m.phase == portPhaseResolving || m.phase == portPhaseCustomInput) {
			return m.updateForm(msg)
		}

		// In review or scanning phase, handle keys directly.
		return m.handleKey(msg)
	}

	// Forward non-key messages to huh form if active.
	if m.form != nil && (m.phase == portPhaseResolving || m.phase == portPhaseCustomInput) {
		return m.updateForm(msg)
	}

	return m, nil
}

// ---------------------------------------------------------------------------
// Phase transitions
// ---------------------------------------------------------------------------

func (m PortsModel) handleScanDone(msg portScanDoneMsg) (tea.Model, tea.Cmd) {
	m.portStatus = msg.status

	// Save original ports for the review "changed from" display.
	m.originalPorts = make([]int, len(m.portStatus))
	for i, ps := range m.portStatus {
		m.originalPorts[i] = ps.Port
	}

	// Identify conflicts (skip Ollama when using local mode).
	m.conflicts = nil
	for i, ps := range m.portStatus {
		if ps.Available {
			continue
		}
		if m.isLocalOllamaPort(ps.Name) {
			continue
		}
		m.conflicts = append(m.conflicts, i)
	}

	if len(m.conflicts) == 0 {
		// No conflicts — skip straight to review.
		m.phase = portPhaseReview
		return m, nil
	}

	// Start resolving the first conflict.
	m.conflictIdx = 0
	return m.startConflictResolution()
}

func (m PortsModel) startConflictResolution() (tea.Model, tea.Cmd) {
	m.phase = portPhaseResolving
	m.formDone = false
	// Allocate a fresh heap string so the new form's pointer accessor is independent
	// of any previously completed form — avoids aliasing across conflict steps.
	choice := ""
	m.choice = &choice
	customPort := ""
	m.customPort = &customPort
	m.customPortErr = ""

	idx := m.conflicts[m.conflictIdx]
	ps := m.portStatus[idx]

	// Find a suggested alternative, excluding ports already assigned to other
	// services in this wizard session so two conflicts never get the same suggestion.
	alreadyAssigned := engine.CollectAssignedPorts(m.portStatus, idx)
	suggested, err := engine.FindAvailablePortExcluding(ps.Port+1, 20, alreadyAssigned)
	if err != nil {
		suggested = 0 // no suggestion available
	}
	m.suggested = suggested

	m.form = m.buildResolveForm(ps, suggested)
	return m, m.form.Init()
}

func (m PortsModel) buildResolveForm(ps engine.PortStatus, suggested int) *huh.Form {
	options := []huh.Option[string]{}

	if suggested > 0 {
		label := fmt.Sprintf("Use next available port: %d", suggested)
		options = append(options, huh.NewOption(label, "suggested"))
	}

	options = append(options,
		huh.NewOption("Enter a custom port number", "custom"),
		huh.NewOption(fmt.Sprintf("Keep %d (I will free it myself)", ps.Port), "keep"),
	)

	sel := huh.NewSelect[string]().
		Title(fmt.Sprintf("Port %d (%s) is in use. Choose a resolution:", ps.Port, ps.Name)).
		Options(options...).
		Value(m.choice)

	return huh.NewForm(huh.NewGroup(sel)).WithShowHelp(true)
}

func (m PortsModel) startCustomInput() (tea.Model, tea.Cmd) {
	m.phase = portPhaseCustomInput
	m.formDone = false
	// Allocate a fresh heap string for the new input form's pointer accessor.
	customPort := ""
	m.customPort = &customPort
	m.customPortErr = ""

	idx := m.conflicts[m.conflictIdx]
	ps := m.portStatus[idx]

	input := huh.NewInput().
		Title(fmt.Sprintf("Enter port number for %s:", ps.Name)).
		Placeholder("e.g. 9000").
		Value(m.customPort).
		Validate(func(s string) error {
			if strings.TrimSpace(s) == "" {
				return fmt.Errorf("port number required")
			}
			port, err := strconv.Atoi(strings.TrimSpace(s))
			if err != nil {
				return fmt.Errorf("must be a number")
			}
			otherPorts := engine.CollectAssignedPorts(m.portStatus, idx)
			if err := engine.ValidatePort(port, otherPorts); err != nil {
				return err
			}
			return nil
		})

	m.form = huh.NewForm(huh.NewGroup(input)).WithShowHelp(true)
	return m, m.form.Init()
}

func (m PortsModel) advanceConflict() (tea.Model, tea.Cmd) {
	m.conflictIdx++
	if m.conflictIdx >= len(m.conflicts) {
		// All conflicts resolved — go to review.
		m.phase = portPhaseReview
		m.form = nil
		return m, nil
	}
	return m.startConflictResolution()
}

// ---------------------------------------------------------------------------
// Form update delegation
// ---------------------------------------------------------------------------

func (m PortsModel) updateForm(msg tea.Msg) (tea.Model, tea.Cmd) {
	form, cmd := m.form.Update(msg)
	if f, ok := form.(*huh.Form); ok {
		m.form = f
	}

	if m.form.State == huh.StateCompleted && !m.formDone {
		m.formDone = true

		if m.phase == portPhaseResolving {
			return m.handleResolveChoice()
		}
		if m.phase == portPhaseCustomInput {
			return m.handleCustomPortSubmit()
		}
	}

	return m, cmd
}

func (m PortsModel) handleResolveChoice() (tea.Model, tea.Cmd) {
	idx := m.conflicts[m.conflictIdx]

	switch *m.choice {
	case "suggested":
		m.portStatus[idx].Port = m.suggested
		m.portStatus[idx].Available = true
		m.applyPort(m.portStatus[idx].Name, m.suggested)
		return m.advanceConflict()

	case "custom":
		return m.startCustomInput()

	case "keep":
		// Leave port as-is. It will fail at Docker startup — user was warned.
		return m.advanceConflict()
	}

	return m, nil
}

func (m PortsModel) handleCustomPortSubmit() (tea.Model, tea.Cmd) {
	port, err := strconv.Atoi(strings.TrimSpace(*m.customPort))
	if err != nil {
		// Should not happen due to form validation, but be safe.
		return m.startCustomInput()
	}

	idx := m.conflicts[m.conflictIdx]

	// Check if the port is currently in use (but valid range + no conflict).
	inUse, valErr := engine.ValidateCustomPort(port, engine.CollectAssignedPorts(m.portStatus, idx))
	if valErr != nil {
		// Validation error — restart custom input.
		m.customPortErr = valErr.Error()
		return m.startCustomInput()
	}

	m.portStatus[idx].Port = port
	m.portStatus[idx].Available = !inUse
	m.applyPort(m.portStatus[idx].Name, port)

	return m.advanceConflict()
}

// ---------------------------------------------------------------------------
// Key handling (review phase + quit)
// ---------------------------------------------------------------------------

func (m PortsModel) handleKey(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
	switch msg.String() {
	case "enter":
		if m.phase == portPhaseReview {
			return m, func() tea.Msg { return NextScreenMsg{} }
		}
	case "q":
		// Only quit via 'q' when NOT in a form (review/scanning phases).
		return m, tea.Quit
	}
	return m, nil
}

// ---------------------------------------------------------------------------
// State mutation
// ---------------------------------------------------------------------------

func (m *PortsModel) applyPort(name string, port int) {
	switch name {
	case "Frontend (Next.js)":
		m.state.Ports.Frontend = port
	case "Backend (FastAPI)":
		m.state.Ports.Backend = port
	case "Qdrant (vector DB)":
		m.state.Ports.Qdrant = port
	case "Qdrant gRPC":
		m.state.Ports.QdrantGRPC = port
	case "Ollama":
		m.state.Ports.Ollama = port
	}
}

func (m PortsModel) isLocalOllamaPort(name string) bool {
	return m.state.OllamaMode == "local" && name == "Ollama"
}

// ---------------------------------------------------------------------------
// View
// ---------------------------------------------------------------------------

func (m PortsModel) View() string {
	switch m.phase {
	case portPhaseScanning:
		return m.viewScanning()
	case portPhaseResolving:
		return m.viewResolving()
	case portPhaseCustomInput:
		return m.viewCustomInput()
	case portPhaseReview:
		return m.viewReview()
	}
	return ""
}

func (m PortsModel) viewScanning() string {
	s := TitleStyle.Render("  Port Configuration") + "\n\n"
	s += "  Scanning ports for conflicts...\n\n"

	services := []string{
		"Frontend (Next.js)", "Backend (FastAPI)",
		"Qdrant (vector DB)", "Qdrant gRPC", "Ollama",
	}
	defaults := []int{3000, 8000, 6333, 6334, 11434}

	for i, name := range services {
		s += fmt.Sprintf("    %-24s :%d   %s\n", name, defaults[i],
			DimStyle.Render("... scanning"))
	}
	return s
}

func (m PortsModel) viewResolving() string {
	s := TitleStyle.Render("  Port Configuration") + "\n\n"

	// Show current scan status table.
	s += m.renderPortTable()
	s += "\n"

	// Show which conflict we are on.
	total := len(m.conflicts)
	current := m.conflictIdx + 1
	s += DimStyle.Render(fmt.Sprintf("  Resolving conflict %d of %d", current, total)) + "\n\n"

	// Render the huh form.
	if m.form != nil {
		s += "  " + m.form.View() + "\n"
	}

	return s
}

func (m PortsModel) viewCustomInput() string {
	s := TitleStyle.Render("  Port Configuration") + "\n\n"

	// Show current scan status table.
	s += m.renderPortTable()
	s += "\n"

	if m.customPortErr != "" {
		s += ErrorStyle.Render(fmt.Sprintf("  Error: %s", m.customPortErr)) + "\n\n"
	}

	// Render the huh input form.
	if m.form != nil {
		s += "  " + m.form.View() + "\n"
	}

	return s
}

func (m PortsModel) viewReview() string {
	s := TitleStyle.Render("  Port Configuration — Final Assignment") + "\n\n"

	for i, ps := range m.portStatus {
		portStr := fmt.Sprintf(":%d", ps.Port)
		status := CheckMark + " available"

		if !ps.Available {
			if m.isLocalOllamaPort(ps.Name) {
				status = DimStyle.Render("skipped (using local)")
			} else {
				status = WarningMark + WarningStyle.Render(" in use — will conflict at startup")
			}
		}

		// Show "changed from" annotation when port was modified.
		changed := ""
		if i < len(m.originalPorts) && m.originalPorts[i] != ps.Port {
			changed = AccentStyle.Render(fmt.Sprintf(" (changed from %d)", m.originalPorts[i]))
		}

		s += fmt.Sprintf("    %-24s %-8s %s%s\n", ps.Name, portStr, status, changed)
	}

	s += "\n"

	allGood := true
	for _, ps := range m.portStatus {
		if !ps.Available && !m.isLocalOllamaPort(ps.Name) {
			allGood = false
			break
		}
	}

	if allGood {
		s += SuccessStyle.Render("  All ports confirmed.") + "\n\n"
	} else {
		s += WarningStyle.Render("  Warning: Some ports are still in use. Docker Compose may fail to bind them.") + "\n"
		s += WarningStyle.Render("  Free those ports before running `embedinator start`.") + "\n\n"
	}

	s += DimStyle.Render("  Press Enter to continue.") + "\n"

	return s
}

// renderPortTable draws the scan results table used in Phase 2 views.
func (m PortsModel) renderPortTable() string {
	var s string
	for _, ps := range m.portStatus {
		portStr := fmt.Sprintf(":%d", ps.Port)
		status := CheckMark + " available"

		if !ps.Available {
			if m.isLocalOllamaPort(ps.Name) {
				status = DimStyle.Render("skipped (using local)")
			} else {
				status = CrossMark + " in use"
			}
		}

		s += fmt.Sprintf("    %-24s %-8s %s\n", ps.Name, portStr, status)
	}
	return s
}
