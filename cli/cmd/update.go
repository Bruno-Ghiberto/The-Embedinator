package cmd

import (
	"fmt"
	"os"
	"path/filepath"

	"github.com/spf13/cobra"

	"github.com/Bruno-Ghiberto/The-Embedinator/cli/internal/engine"
	"github.com/Bruno-Ghiberto/The-Embedinator/cli/internal/version"
)

var (
	updateSelfOnly   bool
	updateImagesOnly bool
	updateYes        bool
)

var updateCmd = &cobra.Command{
	Use:   "update",
	Short: "Update the CLI binary and Docker images",
	Long:  "Check for a new CLI version and pull latest Docker images.",
	RunE:  runUpdate,
}

func init() {
	updateCmd.Flags().BoolVar(&updateSelfOnly, "self-only", false, "Only update the binary, not Docker images")
	updateCmd.Flags().BoolVar(&updateImagesOnly, "images-only", false, "Only update Docker images, not the binary")
	updateCmd.Flags().BoolVar(&updateYes, "yes", false, "Auto-confirm restart")
	rootCmd.AddCommand(updateCmd)
}

func runUpdate(cmd *cobra.Command, args []string) error {
	if !updateImagesOnly {
		fmt.Printf("Current version: %s\n", version.Full())
		fmt.Println("Checking for updates...")

		release, err := engine.CheckLatestVersion()
		if err != nil {
			fmt.Printf("Could not check for updates: %v\n", err)
		} else if engine.IsNewerVersion(release) {
			fmt.Printf("New version available: %s\n", release.TagName)
			fmt.Println("Downloading update...")

			tmpPath, err := engine.DownloadUpdate(release)
			if err != nil {
				fmt.Printf("Download failed: %v\n", err)
			} else {
				if err := engine.ApplySelfUpdate(tmpPath); err != nil {
					fmt.Printf("Update failed: %v\n", err)
					os.Remove(tmpPath)
				} else {
					fmt.Printf("Updated to %s. Restart the CLI to use the new version.\n", release.TagName)
				}
			}
		} else {
			fmt.Println("Already up to date.")
		}
	}

	if !updateSelfOnly {
		fmt.Println("\nUpdating Docker images...")

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
		pullArgs := append([]string{"compose"}, composeArgs...)
		pullArgs = append(pullArgs, "pull")

		pullCmd := engine.DockerCommand(pullArgs...)
		pullCmd.Dir = dir
		pullCmd.Stdout = os.Stdout
		pullCmd.Stderr = os.Stderr

		if err := pullCmd.Run(); err != nil {
			fmt.Printf("Image pull failed: %v\n", err)
		} else {
			fmt.Println("Docker images updated.")

			if engine.IsStackRunning(dir) {
				if updateYes {
					fmt.Println("Restarting services with new images...")
					_ = runRestart(cmd, args)
				} else {
					fmt.Println("Services are running. Run 'embedinator restart' to use the new images.")
				}
			}
		}
	}

	return nil
}
