package cmd

import (
	"fmt"
	"os"
	"path/filepath"

	"github.com/spf13/cobra"

	"github.com/Bruno-Ghiberto/The-Embedinator/cli/internal/engine"
	"github.com/Bruno-Ghiberto/The-Embedinator/cli/internal/wizard"
)

var (
	// Global flags.
	projectDir string
)

var rootCmd = &cobra.Command{
	Use:   "embedinator",
	Short: "The Embedinator -- Self-hosted agentic RAG for private documents",
	Long: `The Embedinator is a self-hosted agentic RAG system for private documents.

Run 'embedinator' with no arguments to:
  - Launch the setup wizard (if not yet configured)
  - Start services (if already configured but stopped)
  - Show status (if already running)`,
	SilenceUsage:  true,
	SilenceErrors: true,
	RunE:          runRoot,
}

func init() {
	rootCmd.PersistentFlags().StringVar(&projectDir, "project-dir", "", "Project directory (default: auto-detect)")
}

// Execute runs the root command.
func Execute() error {
	return rootCmd.Execute()
}

// resolveProjectDir finds the project directory.
//
// Resolution order:
//  1. --project-dir flag (explicit)
//  2. Walk CWD → parents looking for docker-compose.yml (developer mode)
//  3. XDG data directory with extracted compose (user mode)
//
// If nothing is found, the data directory is initialized (compose extracted)
// so the wizard can run.
func resolveProjectDir() (string, error) {
	if projectDir != "" {
		abs, err := filepath.Abs(projectDir)
		if err != nil {
			return "", fmt.Errorf("resolve project dir: %w", err)
		}
		return abs, nil
	}

	// Developer mode: look for docker-compose.yml in current dir or parents.
	dir, err := os.Getwd()
	if err != nil {
		return "", err
	}

	for {
		if _, err := os.Stat(filepath.Join(dir, "docker-compose.yml")); err == nil {
			return dir, nil
		}
		parent := filepath.Dir(dir)
		if parent == dir {
			break
		}
		dir = parent
	}

	// User mode: use the XDG data directory.
	// If already initialized, return it. Otherwise, extract embedded compose.
	if engine.IsDataDirInitialized() {
		return engine.DataDir(), nil
	}

	return engine.InitDataDir()
}

// runRoot implements the smart default behavior.
func runRoot(cmd *cobra.Command, args []string) error {
	dir, err := resolveProjectDir()
	if err != nil {
		return err
	}

	configPath := filepath.Join(dir, "config.yaml")

	// If no config exists, run the setup wizard.
	if !engine.ConfigExists(configPath) {
		state := wizard.DefaultWizardState(dir)
		return wizard.Run(state)
	}

	// Config exists. Check if services are running.
	if engine.IsStackRunning(dir) {
		// Show status.
		return runStatus(cmd, args)
	}

	// Services not running. Start them.
	return runStart(cmd, args)
}
