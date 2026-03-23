package wizard

import "github.com/Bruno-Ghiberto/The-Embedinator/cli/internal/engine"

// Screen identifies which wizard screen is active.
type Screen int

const (
	ScreenWelcome Screen = iota
	ScreenPrerequisites
	ScreenOllama
	ScreenPorts
	ScreenGPU
	ScreenModels
	ScreenAPIKeys
	ScreenSummary
	ScreenProgress
	ScreenComplete
)

// WizardState carries data between screens during the wizard flow.
type WizardState struct {
	// Project directory (where docker-compose.yml lives).
	ProjectDir string

	// Preflight results from Screen 2.
	PreflightResults []engine.PreflightResult

	// Ollama configuration from Screen 3.
	OllamaMode      string // docker | local | remote
	OllamaRemoteURL string
	OllamaDetection engine.OllamaDetection

	// Port configuration from Screen 4.
	Ports engine.PortsConfig

	// GPU detection from Screen 5.
	GPUResult engine.GPUResult
	GPUDiag   *engine.GPUDiagnostic

	// Model selection from Screen 6.
	LLMModels       []string
	EmbeddingModels []string

	// API keys from Screen 7.
	OpenAIKey     string
	AnthropicKey  string
	OpenRouterKey string

	// Cloud provider toggles.
	UseOpenAI     bool
	UseAnthropic  bool
	UseOpenRouter bool

	// Dev mode.
	DevMode bool

	// Fernet key (generated during install).
	FernetKey string

	// Progress tracking for Screen 9.
	InstallDone bool
	InstallError error
}

// ToConfig converts wizard state into an engine.Config.
func (s *WizardState) ToConfig() engine.Config {
	cfg := engine.DefaultConfig()

	cfg.Ollama.Mode = s.OllamaMode
	cfg.Ollama.RemoteURL = s.OllamaRemoteURL
	cfg.Ollama.Models.LLM = s.LLMModels
	cfg.Ollama.Models.Embedding = s.EmbeddingModels

	cfg.GPU.Profile = s.GPUResult.Profile
	cfg.GPU.AutoDetected = s.GPUResult.AutoDetected

	cfg.Ports = s.Ports

	cfg.Providers.OpenAI = s.UseOpenAI
	cfg.Providers.Anthropic = s.UseAnthropic
	cfg.Providers.OpenRouter = s.UseOpenRouter

	cfg.DevMode = s.DevMode

	return cfg
}

// DefaultWizardState returns an initial wizard state with defaults.
func DefaultWizardState(projectDir string) *WizardState {
	return &WizardState{
		ProjectDir: projectDir,
		OllamaMode: "docker",
		Ports: engine.PortsConfig{
			Frontend:   3000,
			Backend:    8000,
			Qdrant:     6333,
			QdrantGRPC: 6334,
			Ollama:     11434,
		},
		LLMModels:       []string{"qwen2.5:7b"},
		EmbeddingModels: []string{"nomic-embed-text"},
	}
}
