package engine

import (
	"embed"
	"fmt"
	"os"
	"path/filepath"
)

//go:embed embedded/docker-compose.yml
var embeddedCompose embed.FS

// ExtractCompose writes the embedded docker-compose.yml to the given directory.
// It is a no-op if the file already exists (preserves user modifications via
// overlay files). To force re-extraction, delete the target first.
func ExtractCompose(dir string) error {
	dest := filepath.Join(dir, "docker-compose.yml")

	if _, err := os.Stat(dest); err == nil {
		return nil // already extracted
	}

	data, err := embeddedCompose.ReadFile("embedded/docker-compose.yml")
	if err != nil {
		return fmt.Errorf("read embedded compose: %w", err)
	}

	// Atomic write: temp then rename.
	tmp := dest + ".tmp"
	if err := os.WriteFile(tmp, data, 0644); err != nil {
		return fmt.Errorf("write compose temp: %w", err)
	}
	if err := os.Rename(tmp, dest); err != nil {
		os.Remove(tmp)
		return fmt.Errorf("rename compose: %w", err)
	}

	return nil
}

// InitDataDir ensures the data directory exists, extracts the embedded
// compose template, and returns the data directory path.
// This is the main entry point for first-time user setup (no git clone).
func InitDataDir() (string, error) {
	dir, err := EnsureDataDir()
	if err != nil {
		return "", err
	}

	if err := ExtractCompose(dir); err != nil {
		return "", fmt.Errorf("extract compose: %w", err)
	}

	return dir, nil
}
