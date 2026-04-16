package cmd

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"path/filepath"
	"time"

	"github.com/spf13/cobra"

	"github.com/Bruno-Ghiberto/The-Embedinator/cli/internal/engine"
)

var (
	statusJSON bool
)

var statusCmd = &cobra.Command{
	Use:   "status",
	Short: "Show service health status",
	Long:  "Check and display the health status of all services.",
	RunE:  runStatus,
}

func init() {
	statusCmd.Flags().BoolVar(&statusJSON, "json", false, "Output as JSON")
	rootCmd.AddCommand(statusCmd)
}

func runStatus(cmd *cobra.Command, args []string) error {
	dir, err := resolveProjectDir()
	if err != nil {
		return err
	}

	configPath := filepath.Join(dir, "config.yaml")
	cfg := engine.DefaultConfig()
	if engine.ConfigExists(configPath) {
		cfg, _ = engine.ReadConfig(configPath)
	}

	endpoints := engine.GetHealthEndpoints(cfg)
	client := &http.Client{Timeout: 3 * time.Second}

	type statusEntry struct {
		Name    string `json:"name"`
		Status  string `json:"status"`
		Port    int    `json:"port"`
		Healthy bool   `json:"healthy"`
	}

	entries := make([]statusEntry, len(endpoints))

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	for i, ep := range endpoints {
		entries[i] = statusEntry{
			Name: ep.Name,
			Port: ep.Port,
		}

		req, err := http.NewRequestWithContext(ctx, "GET", ep.URL, nil)
		if err != nil {
			entries[i].Status = "error"
			continue
		}

		resp, err := client.Do(req)
		if err != nil {
			entries[i].Status = "unreachable"
			continue
		}
		resp.Body.Close()

		if resp.StatusCode < 500 {
			entries[i].Status = "healthy"
			entries[i].Healthy = true
		} else {
			entries[i].Status = "unhealthy"
		}
	}

	if statusJSON {
		data, _ := json.MarshalIndent(entries, "", "  ")
		fmt.Println(string(data))
		return nil
	}

	fmt.Println("\nService Health Status")
	fmt.Println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
	for _, e := range entries {
		status := e.Status
		fmt.Printf("  %-12s %-12s port %d\n", e.Name, status, e.Port)
	}
	fmt.Println()

	return nil
}
