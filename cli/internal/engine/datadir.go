package engine

import (
	"fmt"
	"os"
	"path/filepath"
	"runtime"
)

// DataDir returns the platform-specific data directory for The Embedinator.
//
// Locations:
//   - Linux:   $XDG_DATA_HOME/embedinator or ~/.local/share/embedinator
//   - macOS:   ~/Library/Application Support/embedinator
//   - Windows: %LOCALAPPDATA%\embedinator
//
// The EMBEDINATOR_DATA_DIR environment variable overrides all defaults.
func DataDir() string {
	if d := os.Getenv("EMBEDINATOR_DATA_DIR"); d != "" {
		return d
	}

	switch runtime.GOOS {
	case "darwin":
		home, _ := os.UserHomeDir()
		return filepath.Join(home, "Library", "Application Support", "embedinator")
	case "windows":
		local := os.Getenv("LOCALAPPDATA")
		if local == "" {
			home, _ := os.UserHomeDir()
			local = filepath.Join(home, "AppData", "Local")
		}
		return filepath.Join(local, "embedinator")
	default: // linux and others — follow XDG
		if xdg := os.Getenv("XDG_DATA_HOME"); xdg != "" {
			return filepath.Join(xdg, "embedinator")
		}
		home, _ := os.UserHomeDir()
		return filepath.Join(home, ".local", "share", "embedinator")
	}
}

// EnsureDataDir creates the data directory and required subdirectories.
// Returns the data directory path.
func EnsureDataDir() (string, error) {
	dir := DataDir()

	for _, sub := range []string{
		dir,
		filepath.Join(dir, "data"),
		filepath.Join(dir, "data", "qdrant_db"),
		filepath.Join(dir, "data", "uploads"),
	} {
		if err := os.MkdirAll(sub, 0755); err != nil {
			return "", fmt.Errorf("create %s: %w", sub, err)
		}
	}

	return dir, nil
}

// IsDataDirInitialized reports whether the data directory has a
// docker-compose.yml (extracted from the binary during first setup).
func IsDataDirInitialized() bool {
	_, err := os.Stat(filepath.Join(DataDir(), "docker-compose.yml"))
	return err == nil
}
