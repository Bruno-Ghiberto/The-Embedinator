package cmd

import (
	"fmt"

	"github.com/spf13/cobra"
)

var restartCmd = &cobra.Command{
	Use:   "restart",
	Short: "Restart all services",
	Long:  "Stop then start all services. Accepts all flags from both start and stop.",
	RunE:  runRestart,
}

func init() {
	restartCmd.Flags().BoolVar(&startDev, "dev", false, "Include dev overlay (hot reload)")
	restartCmd.Flags().BoolVar(&startOpen, "open", false, "Open browser after services are healthy")
	restartCmd.Flags().BoolVar(&stopVolumes, "volumes", false, "Also remove Docker volumes (destructive)")
	rootCmd.AddCommand(restartCmd)
}

func runRestart(cmd *cobra.Command, args []string) error {
	fmt.Println("Restarting all services...")

	if err := runStop(cmd, args); err != nil {
		return err
	}

	return runStart(cmd, args)
}
