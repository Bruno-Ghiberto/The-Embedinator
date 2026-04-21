package cmd

import (
	"context"
	"fmt"
	"path/filepath"
	"time"

	"github.com/spf13/cobra"

	"github.com/Bruno-Ghiberto/The-Embedinator/cli/internal/engine"
	"github.com/Bruno-Ghiberto/The-Embedinator/cli/internal/wizard"
)

var (
	setupNonInteractive bool
)

var setupCmd = &cobra.Command{
	Use:   "setup",
	Short: "Run the full TUI setup wizard",
	Long:  "Launch the interactive setup wizard to configure and install The Embedinator.",
	RunE:  runSetup,
}

func init() {
	setupCmd.Flags().BoolVar(&setupNonInteractive, "non-interactive", false, "Skip TUI, use defaults or existing config values")
	setupCmd.Flags().BoolVar(&setupNonInteractive, "accept-defaults", false, "Same as --non-interactive")
	rootCmd.AddCommand(setupCmd)
}

func runSetup(cmd *cobra.Command, args []string) error {
	dir, err := resolveProjectDir()
	if err != nil {
		return err
	}

	state := wizard.DefaultWizardState(dir)

	if setupNonInteractive {
		return runNonInteractiveSetup(dir, state)
	}

	return wizard.Run(state)
}

// runNonInteractiveSetup performs the full setup using defaults (or existing
// config.yaml values) without launching any TUI screens.
func runNonInteractiveSetup(dir string, state *wizard.WizardState) error {
	fmt.Println("Running non-interactive setup with defaults...")

	// Step 1: Load existing config if present, otherwise use defaults.
	configPath := filepath.Join(dir, "config.yaml")
	cfg := engine.DefaultConfig()
	if engine.ConfigExists(configPath) {
		existing, err := engine.ReadConfig(configPath)
		if err == nil {
			cfg = existing
			fmt.Println("  Loaded existing config.yaml")
		}
	}

	// Step 2: Run preflight checks.
	fmt.Println("\nPreflight checks:")
	results := engine.RunAllPreflights(dir)
	allOK := true
	for _, r := range results {
		if r.OK {
			fmt.Printf("  [ok] %-20s %s\n", r.Name, r.Detail)
		} else {
			fmt.Printf("  [!!] %-20s %s\n", r.Name, r.Error)
			allOK = false
		}
	}
	if !allOK {
		return fmt.Errorf("preflight checks failed; resolve the issues above and retry")
	}

	// Step 3: Generate Fernet key if not already set.
	fernetKey := state.FernetKey
	if fernetKey == "" {
		fernetKey = engine.GenerateFernetKey()
	}

	// Step 4: Generate .env file.
	envPath := filepath.Join(dir, ".env")
	examplePath := filepath.Join(dir, ".env.example")
	if err := engine.GenerateDotEnv(envPath, examplePath, cfg, fernetKey); err != nil {
		return fmt.Errorf("generate .env: %w", err)
	}
	fmt.Println("\n  Generated .env")

	// Step 5: Write config.yaml.
	if err := engine.WriteConfig(configPath, cfg); err != nil {
		return fmt.Errorf("write config.yaml: %w", err)
	}
	fmt.Println("  Generated config.yaml")

	// Step 6: Generate overlay if using local/remote Ollama.
	if cfg.Ollama.Mode == "local" || cfg.Ollama.Mode == "remote" {
		url := "http://host.docker.internal:11434"
		if cfg.Ollama.RemoteURL != "" {
			url = cfg.Ollama.RemoteURL
		}
		_ = engine.GenerateLocalOllamaOverlay(dir, url)
	} else {
		_ = engine.RemoveLocalOllamaOverlay(dir)
	}

	// Step 7: Docker Compose up.
	fmt.Println("\nStarting Docker Compose...")
	composeArgs := engine.BuildComposeArgs(cfg, dir)
	if err := engine.ComposeUp(dir, composeArgs, true); err != nil {
		return fmt.Errorf("docker compose up: %w", err)
	}
	fmt.Println("  Docker Compose started.")

	// Step 8: Health check.
	fmt.Println("\nWaiting for services to become healthy...")
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Minute)
	defer cancel()
	if err := engine.PollHealth(ctx, cfg, 3*time.Second, nil); err != nil {
		return fmt.Errorf("health check: %w", err)
	}
	fmt.Println("  All services healthy.")

	// Step 9: Pull models.
	allModels := append(cfg.Ollama.Models.LLM, cfg.Ollama.Models.Embedding...)
	if len(allModels) > 0 {
		fmt.Println("\nPulling models:")
		useLocal := cfg.Ollama.Mode == "local"
		for _, model := range allModels {
			fmt.Printf("  Pulling %s...", model)
			if err := engine.PullModel(dir, model, useLocal); err != nil {
				fmt.Printf(" error: %v\n", err)
			} else {
				fmt.Println(" done.")
			}
		}
	}

	// Step 10: Summary.
	fmt.Println("\nSetup complete!")
	fmt.Printf("  Ollama mode:   %s\n", cfg.Ollama.Mode)
	fmt.Printf("  Frontend:      http://localhost:%d\n", cfg.Ports.Frontend)
	fmt.Printf("  Backend API:   http://localhost:%d\n", cfg.Ports.Backend)
	fmt.Printf("  Qdrant:        http://localhost:%d\n", cfg.Ports.Qdrant)
	fmt.Printf("  GPU profile:   %s\n", cfg.GPU.Profile)
	fmt.Printf("  Fernet key:    auto-generated\n")

	return nil
}
