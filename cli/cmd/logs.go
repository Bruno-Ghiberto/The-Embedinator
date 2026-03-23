package cmd

import (
	"path/filepath"

	"github.com/spf13/cobra"

	"github.com/Bruno-Ghiberto/The-Embedinator/cli/internal/engine"
)

var (
	logsTail  int
	logsSince string
)

var logsCmd = &cobra.Command{
	Use:   "logs [SERVICE]",
	Short: "Stream service logs",
	Long:  "Stream Docker Compose logs. Optionally specify a service: qdrant, ollama, backend, frontend.",
	Args:  cobra.MaximumNArgs(1),
	RunE:  runLogs,
}

func init() {
	logsCmd.Flags().IntVar(&logsTail, "tail", 100, "Number of lines to show from the end")
	logsCmd.Flags().StringVar(&logsSince, "since", "", "Show logs since timestamp (e.g., 1h, 2024-01-01T00:00:00)")
	rootCmd.AddCommand(logsCmd)
}

func runLogs(cmd *cobra.Command, args []string) error {
	dir, err := resolveProjectDir()
	if err != nil {
		return err
	}

	configPath := filepath.Join(dir, "config.yaml")
	cfg := engine.DefaultConfig()
	if engine.ConfigExists(configPath) {
		cfg, _ = engine.ReadConfig(configPath)
	}

	composeArgs := engine.BuildComposeArgs(cfg)

	service := ""
	if len(args) > 0 {
		service = args[0]
	}

	return engine.ComposeLogs(dir, composeArgs, service, logsTail, logsSince)
}
