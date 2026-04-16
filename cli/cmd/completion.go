package cmd

import (
	"os"

	"github.com/spf13/cobra"
)

var completionCmd = &cobra.Command{
	Use:   "completion [bash|zsh|fish|powershell]",
	Short: "Generate shell completion scripts",
	Long: `Generate shell completion scripts for embedinator.

To load completions:

Bash:
  $ source <(embedinator completion bash)
  # To install permanently:
  $ embedinator completion bash > /etc/bash_completion.d/embedinator

Zsh:
  $ source <(embedinator completion zsh)
  # To install permanently:
  $ embedinator completion zsh > "${fpath[1]}/_embedinator"

Fish:
  $ embedinator completion fish | source
  # To install permanently:
  $ embedinator completion fish > ~/.config/fish/completions/embedinator.fish

PowerShell:
  PS> embedinator completion powershell | Out-String | Invoke-Expression
  # To install permanently, add the output to your PowerShell profile.
`,
	DisableFlagsInUseLine: true,
	ValidArgs:             []string{"bash", "zsh", "fish", "powershell"},
	Args:                  cobra.MatchAll(cobra.ExactArgs(1), cobra.OnlyValidArgs),
	RunE: func(cmd *cobra.Command, args []string) error {
		switch args[0] {
		case "bash":
			return rootCmd.GenBashCompletion(os.Stdout)
		case "zsh":
			return rootCmd.GenZshCompletion(os.Stdout)
		case "fish":
			return rootCmd.GenFishCompletion(os.Stdout, true)
		case "powershell":
			return rootCmd.GenPowerShellCompletionWithDesc(os.Stdout)
		}
		return nil
	},
}

func init() {
	rootCmd.AddCommand(completionCmd)
}
