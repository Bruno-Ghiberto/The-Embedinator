//go:build windows

package engine

import (
	"fmt"

	"golang.org/x/sys/windows"
)

// CheckDiskSpace checks available disk space at the given path.
// Returns the result with available GB and whether it meets the minimum.
func CheckDiskSpace(path string, minGB uint64) PreflightResult {
	result := PreflightResult{Name: "Disk space"}

	pathPtr, err := windows.UTF16PtrFromString(path)
	if err != nil {
		result.OK = false
		result.Error = fmt.Sprintf("invalid path: %v", err)
		return result
	}

	var freeBytesAvailable, totalBytes, totalFreeBytes uint64
	if err := windows.GetDiskFreeSpaceEx(pathPtr, &freeBytesAvailable, &totalBytes, &totalFreeBytes); err != nil {
		result.OK = false
		result.Error = fmt.Sprintf("unable to check disk space: %v", err)
		return result
	}

	availableGB := freeBytesAvailable / (1024 * 1024 * 1024)

	if availableGB < minGB {
		result.OK = false
		result.Error = fmt.Sprintf("%d GB available, %d GB required", availableGB, minGB)
		return result
	}

	result.OK = true
	result.Detail = fmt.Sprintf("%d GB available (%d GB required)", availableGB, minGB)
	return result
}
