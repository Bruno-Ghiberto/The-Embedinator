package cmd

import (
	"fmt"

	"github.com/spf13/cobra"

	"github.com/Bruno-Ghiberto/The-Embedinator/cli/internal/version"
)

var versionCmd = &cobra.Command{
	Use:   "version",
	Short: "Print version information",
	Long:  "Print the embedinator CLI version, commit hash, and build date.",
	Run: func(cmd *cobra.Command, args []string) {
		fmt.Println(version.Full())
	},
}

func init() {
	rootCmd.AddCommand(versionCmd)
}
