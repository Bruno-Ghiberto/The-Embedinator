package cmd

import (
	"fmt"
	"path/filepath"

	"github.com/spf13/cobra"

	"github.com/Bruno-Ghiberto/The-Embedinator/cli/internal/engine"
)

var (
	stopVolumes bool
)

var stopCmd = &cobra.Command{
	Use:   "stop",
	Short: "Stop all services",
	Long:  "Stop all Docker Compose services.",
	RunE:  runStop,
}

func init() {
	stopCmd.Flags().BoolVar(&stopVolumes, "volumes", false, "Also remove Docker volumes (destructive)")
	rootCmd.AddCommand(stopCmd)
}

func runStop(cmd *cobra.Command, args []string) error {
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

	fmt.Println("Stopping all services...")
	if err := engine.ComposeDown(dir, composeArgs, stopVolumes); err != nil {
		return fmt.Errorf("docker compose down: %w", err)
	}

	fmt.Println("All services stopped.")
	return nil
}
