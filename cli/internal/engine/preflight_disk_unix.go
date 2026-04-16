//go:build !windows

package engine

import (
	"fmt"
	"syscall"
)

// CheckDiskSpace checks available disk space at the given path.
// Returns the result with available GB and whether it meets the minimum.
func CheckDiskSpace(path string, minGB uint64) PreflightResult {
	result := PreflightResult{Name: "Disk space"}

	var stat syscall.Statfs_t
	if err := syscall.Statfs(path, &stat); err != nil {
		result.OK = false
		result.Error = fmt.Sprintf("unable to check disk space: %v", err)
		return result
	}

	availableBytes := stat.Bavail * uint64(stat.Bsize)
	availableGB := availableBytes / (1024 * 1024 * 1024)

	if availableGB < minGB {
		result.OK = false
		result.Error = fmt.Sprintf("%d GB available, %d GB required", availableGB, minGB)
		return result
	}

	result.OK = true
	result.Detail = fmt.Sprintf("%d GB available (%d GB required)", availableGB, minGB)
	return result
}
