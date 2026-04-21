package cmd

import (
	"path/filepath"

	"github.com/spf13/cobra"

	"github.com/Bruno-Ghiberto/The-Embedinator/cli/internal/engine"
	"github.com/Bruno-Ghiberto/The-Embedinator/cli/internal/wizard"
)

var configCmd = &cobra.Command{
	Use:   "config",
	Short: "Re-run the configuration wizard",
	Long: `Re-run the configuration wizard (screens 3-8, skipping welcome and prerequisites).
Pre-populates all fields from existing config.yaml.`,
	RunE: runConfig,
}

func init() {
	rootCmd.AddCommand(configCmd)
}

func runConfig(cmd *cobra.Command, args []string) error {
	dir, err := resolveProjectDir()
	if err != nil {
		return err
	}

	configPath := filepath.Join(dir, "config.yaml")
	state := wizard.DefaultWizardState(dir)

	// Pre-populate from existing config.
	if engine.ConfigExists(configPath) {
		cfg, err := engine.ReadConfig(configPath)
		if err == nil {
			state.OllamaMode = cfg.Ollama.Mode
			state.OllamaRemoteURL = cfg.Ollama.RemoteURL
			state.Ports = cfg.Ports
			state.GPUResult.Profile = cfg.GPU.Profile
			state.GPUResult.AutoDetected = cfg.GPU.AutoDetected
			state.LLMModels = cfg.Ollama.Models.LLM
			state.EmbeddingModels = cfg.Ollama.Models.Embedding
			state.UseOpenAI = cfg.Providers.OpenAI
			state.UseAnthropic = cfg.Providers.Anthropic
			state.UseOpenRouter = cfg.Providers.OpenRouter
			state.DevMode = cfg.DevMode
		}
	}

	return wizard.RunConfig(state)
}
