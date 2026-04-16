package engine

import (
	"fmt"
	"io"
	"os"
	"path/filepath"
	"runtime"
	"strings"
)

// InstallResult describes the outcome of a self-install attempt.
type InstallResult struct {
	InstalledPath   string // absolute path where binary was installed
	NeedsPathUpdate bool   // true if the install dir is not currently in $PATH
	PathExport      string // shell line to add (e.g. export PATH="...")
	Skipped         bool   // true if already running from a system location
	Err             error
}

// SelfInstall copies the running binary to a system-accessible location.
//
// Candidate order (first writable wins):
//   - Linux/macOS: ~/.local/bin  (no sudo required)
//   - Linux/macOS: /usr/local/bin (requires write permission)
//   - Windows:     %LOCALAPPDATA%\Programs\embedinator\
//
// If the binary is already running from one of these locations, Skipped is set
// to true and no copy is performed.
func SelfInstall() InstallResult {
	exe, err := os.Executable()
	if err != nil {
		return InstallResult{Err: fmt.Errorf("get executable path: %w", err)}
	}
	exe, err = filepath.EvalSymlinks(exe)
	if err != nil {
		return InstallResult{Err: fmt.Errorf("resolve executable symlinks: %w", err)}
	}

	candidates := installCandidates()

	// Already running from a system location — nothing to do.
	exeDir := filepath.Clean(filepath.Dir(exe))
	for _, c := range candidates {
		if filepath.Clean(c) == exeDir {
			return InstallResult{
				InstalledPath: exe,
				Skipped:       true,
			}
		}
	}

	// Try each candidate in order; use the first one we can write to.
	for _, dir := range candidates {
		dest := filepath.Join(dir, binaryName())
		if err := copyExecutable(exe, dest); err != nil {
			continue
		}
		needsPath := !isDirInPath(dir)
		var export string
		if needsPath {
			export = pathExportLine(dir)
		}
		return InstallResult{
			InstalledPath:   dest,
			NeedsPathUpdate: needsPath,
			PathExport:      export,
		}
	}

	return InstallResult{
		Err: fmt.Errorf("could not install to any writable location (tried: %s)",
			strings.Join(candidates, ", ")),
	}
}

// installCandidates returns install target directories in preference order.
func installCandidates() []string {
	if runtime.GOOS == "windows" {
		localAppData := os.Getenv("LOCALAPPDATA")
		if localAppData == "" {
			localAppData = filepath.Join(os.Getenv("USERPROFILE"), "AppData", "Local")
		}
		return []string{
			filepath.Join(localAppData, "Programs", "embedinator"),
		}
	}

	home, _ := os.UserHomeDir()
	return []string{
		filepath.Join(home, ".local", "bin"),
		"/usr/local/bin",
	}
}

// binaryName returns the platform-appropriate binary filename.
func binaryName() string {
	if runtime.GOOS == "windows" {
		return "embedinator.exe"
	}
	return "embedinator"
}

// copyExecutable copies src to dest with executable permissions (0755).
// The destination directory is created if it does not exist.
// Uses an atomic temp-then-rename to avoid partial writes.
func copyExecutable(src, dest string) error {
	if err := os.MkdirAll(filepath.Dir(dest), 0755); err != nil {
		return fmt.Errorf("create dir: %w", err)
	}

	in, err := os.Open(src)
	if err != nil {
		return fmt.Errorf("open source: %w", err)
	}
	defer in.Close()

	tmp := dest + ".tmp"
	out, err := os.OpenFile(tmp, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0755)
	if err != nil {
		return fmt.Errorf("create dest: %w", err)
	}

	if _, err := io.Copy(out, in); err != nil {
		out.Close()
		os.Remove(tmp)
		return fmt.Errorf("copy bytes: %w", err)
	}
	if err := out.Close(); err != nil {
		os.Remove(tmp)
		return fmt.Errorf("close dest: %w", err)
	}
	if err := os.Rename(tmp, dest); err != nil {
		os.Remove(tmp)
		return fmt.Errorf("atomic rename: %w", err)
	}

	return nil
}

// isDirInPath reports whether dir is present in the PATH environment variable.
func isDirInPath(dir string) bool {
	clean := filepath.Clean(dir)
	for _, d := range filepath.SplitList(os.Getenv("PATH")) {
		if filepath.Clean(d) == clean {
			return true
		}
	}
	return false
}

// pathExportLine returns the shell line the user needs to add to their profile.
func pathExportLine(dir string) string {
	if runtime.GOOS == "windows" {
		return fmt.Sprintf(`setx PATH "%%PATH%%;%s"`, dir)
	}
	return fmt.Sprintf(`export PATH="%s:$PATH"`, dir)
}
