package main

import (
	"os"

	"github.com/Bruno-Ghiberto/The-Embedinator/cli/cmd"
)

func main() {
	if err := cmd.Execute(); err != nil {
		os.Exit(1)
	}
}
