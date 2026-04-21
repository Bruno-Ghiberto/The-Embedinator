package engine

import (
	"archive/tar"
	"archive/zip"
	"compress/gzip"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"time"

	"github.com/Bruno-Ghiberto/The-Embedinator/cli/internal/version"
)

const githubReleasesURL = "https://api.github.com/repos/Bruno-Ghiberto/The-Embedinator/releases/latest"

// ReleaseInfo holds information about a GitHub release.
type ReleaseInfo struct {
	TagName string `json:"tag_name"`
	Assets  []struct {
		Name               string `json:"name"`
		BrowserDownloadURL string `json:"browser_download_url"`
	} `json:"assets"`
}

// CheckLatestVersion queries GitHub for the latest release.
func CheckLatestVersion() (*ReleaseInfo, error) {
	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Get(githubReleasesURL)
	if err != nil {
		return nil, fmt.Errorf("check update: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("GitHub API returned status %d", resp.StatusCode)
	}

	var release ReleaseInfo
	if err := json.NewDecoder(resp.Body).Decode(&release); err != nil {
		return nil, fmt.Errorf("parse release: %w", err)
	}

	return &release, nil
}

// IsNewerVersion checks if the release is newer than the current version.
func IsNewerVersion(release *ReleaseInfo) bool {
	current := version.Version
	if current == "dev" {
		return false // dev builds don't auto-update
	}
	latest := release.TagName
	if len(latest) > 0 && latest[0] == 'v' {
		latest = latest[1:]
	}
	return latest != current
}

// DownloadUpdate downloads the archive for the current OS/arch from the release.
// Returns the path to the downloaded archive file.
func DownloadUpdate(release *ReleaseInfo) (string, error) {
	assetName := fmt.Sprintf("embedinator_%s_%s", runtime.GOOS, runtime.GOARCH)

	var downloadURL string
	var matchedAsset string
	for _, asset := range release.Assets {
		if asset.Name == assetName+".tar.gz" || asset.Name == assetName+".zip" {
			downloadURL = asset.BrowserDownloadURL
			matchedAsset = asset.Name
			break
		}
	}

	if downloadURL == "" {
		return "", fmt.Errorf("no binary found for %s/%s in release %s", runtime.GOOS, runtime.GOARCH, release.TagName)
	}

	client := &http.Client{Timeout: 120 * time.Second}
	resp, err := client.Get(downloadURL)
	if err != nil {
		return "", fmt.Errorf("download binary: %w", err)
	}
	defer resp.Body.Close()

	// Use the real asset extension so ApplySelfUpdate can detect the format.
	suffix := ".tar.gz"
	if strings.HasSuffix(matchedAsset, ".zip") {
		suffix = ".zip"
	}
	tmpFile, err := os.CreateTemp("", "embedinator-update-*"+suffix)
	if err != nil {
		return "", fmt.Errorf("create temp file: %w", err)
	}

	if _, err := io.Copy(tmpFile, resp.Body); err != nil {
		tmpFile.Close()
		os.Remove(tmpFile.Name())
		return "", fmt.Errorf("write update: %w", err)
	}
	tmpFile.Close()

	return tmpFile.Name(), nil
}

// ApplySelfUpdate extracts the binary from the downloaded archive and replaces
// the current executable. The archive is a .tar.gz (Linux/macOS) or .zip (Windows)
// produced by goreleaser, containing the "embedinator" binary at the top level.
func ApplySelfUpdate(archivePath string) error {
	execPath, err := os.Executable()
	if err != nil {
		return fmt.Errorf("get executable path: %w", err)
	}

	// Create a temp directory for extraction.
	tmpDir, err := os.MkdirTemp("", "embedinator-extract-*")
	if err != nil {
		return fmt.Errorf("create temp dir: %w", err)
	}
	defer os.RemoveAll(tmpDir)

	// Extract the binary from the archive.
	var binaryPath string
	if strings.HasSuffix(archivePath, ".zip") {
		binaryPath, err = extractFromZip(archivePath, tmpDir)
	} else {
		binaryPath, err = extractFromTarGz(archivePath, tmpDir)
	}
	if err != nil {
		return fmt.Errorf("extract archive: %w", err)
	}

	// Clean up the downloaded archive.
	os.Remove(archivePath)

	// Atomic replace: rename extracted binary over the current executable.
	if err := os.Rename(binaryPath, execPath); err != nil {
		// Rename may fail across filesystems; fall back to copy.
		if err := copyFile(binaryPath, execPath); err != nil {
			return fmt.Errorf("replace binary: %w", err)
		}
	}

	return os.Chmod(execPath, 0755)
}

// extractFromTarGz extracts the embedinator binary from a .tar.gz archive.
func extractFromTarGz(archivePath, destDir string) (string, error) {
	f, err := os.Open(archivePath)
	if err != nil {
		return "", err
	}
	defer f.Close()

	gz, err := gzip.NewReader(f)
	if err != nil {
		return "", fmt.Errorf("gzip reader: %w", err)
	}
	defer gz.Close()

	tr := tar.NewReader(gz)
	binaryName := "embedinator"
	if runtime.GOOS == "windows" {
		binaryName = "embedinator.exe"
	}

	for {
		hdr, err := tr.Next()
		if err == io.EOF {
			break
		}
		if err != nil {
			return "", fmt.Errorf("tar read: %w", err)
		}

		// Match the binary by base name (goreleaser may nest in a directory).
		baseName := filepath.Base(hdr.Name)
		if baseName == binaryName && hdr.Typeflag == tar.TypeReg {
			outPath := filepath.Join(destDir, binaryName)
			outFile, err := os.OpenFile(outPath, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0755)
			if err != nil {
				return "", err
			}
			if _, err := io.Copy(outFile, tr); err != nil {
				outFile.Close()
				return "", err
			}
			outFile.Close()
			return outPath, nil
		}
	}

	return "", fmt.Errorf("binary %q not found in tar.gz archive", binaryName)
}

// extractFromZip extracts the embedinator binary from a .zip archive.
func extractFromZip(archivePath, destDir string) (string, error) {
	r, err := zip.OpenReader(archivePath)
	if err != nil {
		return "", fmt.Errorf("zip open: %w", err)
	}
	defer r.Close()

	binaryName := "embedinator"
	if runtime.GOOS == "windows" {
		binaryName = "embedinator.exe"
	}

	for _, f := range r.File {
		baseName := filepath.Base(f.Name)
		if baseName == binaryName && !f.FileInfo().IsDir() {
			rc, err := f.Open()
			if err != nil {
				return "", err
			}

			outPath := filepath.Join(destDir, binaryName)
			outFile, err := os.OpenFile(outPath, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0755)
			if err != nil {
				rc.Close()
				return "", err
			}

			if _, err := io.Copy(outFile, rc); err != nil {
				outFile.Close()
				rc.Close()
				return "", err
			}

			outFile.Close()
			rc.Close()
			return outPath, nil
		}
	}

	return "", fmt.Errorf("binary %q not found in zip archive", binaryName)
}

// copyFile copies src to dst, used as fallback when rename fails across filesystems.
func copyFile(src, dst string) error {
	in, err := os.Open(src)
	if err != nil {
		return err
	}
	defer in.Close()

	out, err := os.OpenFile(dst, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0755)
	if err != nil {
		return err
	}
	defer out.Close()

	_, err = io.Copy(out, in)
	return err
}
