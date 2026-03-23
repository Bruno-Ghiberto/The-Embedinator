package cmd

import (
	"context"
	"fmt"
	"path/filepath"
	"time"

	"github.com/spf13/cobra"

	"github.com/Bruno-Ghiberto/The-Embedinator/cli/internal/engine"
)

var (
	startDev     bool
	startOpen    bool
	startTimeout time.Duration
)

var startCmd = &cobra.Command{
	Use:   "start",
	Short: "Start all services",
	Long:  "Start the Docker Compose stack. Requires a prior 'embedinator setup'.",
	RunE:  runStart,
}

func init() {
	startCmd.Flags().BoolVar(&startDev, "dev", false, "Include dev overlay (hot reload)")
	startCmd.Flags().BoolVar(&startOpen, "open", false, "Open browser after services are healthy")
	startCmd.Flags().DurationVar(&startTimeout, "timeout", 2*time.Minute, "Health check timeout")
	rootCmd.AddCommand(startCmd)
}

func runStart(cmd *cobra.Command, args []string) error {
	dir, err := resolveProjectDir()
	if err != nil {
		return err
	}

	configPath := filepath.Join(dir, "config.yaml")
	if !engine.ConfigExists(configPath) {
		return fmt.Errorf("config.yaml not found. Run 'embedinator setup' first")
	}

	cfg, err := engine.ReadConfig(configPath)
	if err != nil {
		return fmt.Errorf("read config: %w", err)
	}

	if err := engine.ValidateConfig(cfg); err != nil {
		return fmt.Errorf("invalid config: %w", err)
	}

	cfg.DevMode = startDev

	// Check Docker.
	dockerCheck := engine.CheckDocker()
	if !dockerCheck.OK {
		return fmt.Errorf("%s", dockerCheck.Error)
	}

	// Build compose args.
	composeArgs := engine.BuildComposeArgs(cfg)

	fmt.Println("Starting services...")
	if err := engine.ComposeUp(dir, composeArgs, true); err != nil {
		return fmt.Errorf("docker compose up: %w", err)
	}

	// Poll health.
	fmt.Println("Waiting for services to be healthy...")
	ctx, cancel := context.WithTimeout(context.Background(), startTimeout)
	defer cancel()

	err = engine.PollHealth(ctx, cfg, 3*time.Second, func(results []engine.ServiceHealth) {
		for _, r := range results {
			status := "waiting"
			if r.Healthy {
				status = "healthy"
			}
			fmt.Printf("  %-12s %s\n", r.Name, status)
		}
	})
	if err != nil {
		return fmt.Errorf("health check timeout: %w", err)
	}

	fmt.Println("\nAll services are healthy.")
	fmt.Printf("\n  Application: http://localhost:%d\n", cfg.Ports.Frontend)
	fmt.Printf("  Backend API: http://localhost:%d\n\n", cfg.Ports.Backend)

	if startOpen {
		url := fmt.Sprintf("http://localhost:%d", cfg.Ports.Frontend)
		fmt.Printf("Opening %s in browser...\n", url)
	}

	return nil
}
