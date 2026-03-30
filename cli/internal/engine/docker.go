package engine

import (
	"context"
	"errors"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"time"

	dockerclient "github.com/docker/docker/client"
	"github.com/docker/docker/api/types/container"
	"github.com/docker/docker/api/types/filters"
	"github.com/docker/docker/api/types/image"
)

// ---------------------------------------------------------------------------
// DockerAPI — testable interface for Docker Engine SDK operations.
// ---------------------------------------------------------------------------

// ContainerInfo holds summary information about a running container.
type ContainerInfo struct {
	ID     string
	Name   string
	Image  string
	State  string
	Status string
	Ports  []PortBinding
	Labels map[string]string
}

// PortBinding maps a container port to a host binding.
type PortBinding struct {
	ContainerPort uint16
	HostPort      uint16
	Protocol      string // "tcp" or "udp"
}

// ContainerDetail holds detailed inspection data for a single container.
type ContainerDetail struct {
	ID         string
	Name       string
	Image      string
	State      string
	Status     string
	Platform   string
	Created    string
	RestartCnt int
	Ports      []PortBinding
	Labels     map[string]string
	Mounts     []string
}

// DockerAPI is the interface for Docker Engine SDK operations.
// Compose operations are intentionally excluded — they stay as CLI exec.
type DockerAPI interface {
	// Ping checks whether the Docker daemon is reachable.
	Ping(ctx context.Context) error
	// IsRunning returns true when the Docker daemon responds to a ping.
	IsRunning() bool
	// PullImage pulls an image by reference (e.g. "nginx:latest").
	// The caller must NOT close the returned reader — PullImage drains it.
	PullImage(ctx context.Context, refStr string) error
	// ListContainers lists containers matching the given filters.
	// Pass nil for no filtering.
	ListContainers(ctx context.Context, labelFilters map[string]string) ([]ContainerInfo, error)
	// InspectContainer returns detailed information about a single container.
	InspectContainer(ctx context.Context, id string) (*ContainerDetail, error)
	// Close releases the underlying HTTP client resources.
	Close() error
}

// ---------------------------------------------------------------------------
// DockerClient — SDK-backed implementation of DockerAPI.
// ---------------------------------------------------------------------------

// DockerClient wraps the official Docker Engine API client.
type DockerClient struct {
	cli *dockerclient.Client
}

// compile-time interface check
var _ DockerAPI = (*DockerClient)(nil)

// NewDockerClient creates a DockerClient that auto-detects its connection
// settings from the environment (DOCKER_HOST, DOCKER_TLS_VERIFY, etc.).
// On Linux, when the Engine socket exists, it forces DOCKER_HOST to the
// Engine socket so the SDK talks to Docker Engine (not Docker Desktop).
func NewDockerClient() (*DockerClient, error) {
	opts := []dockerclient.Opt{
		dockerclient.FromEnv,
		dockerclient.WithAPIVersionNegotiation(),
	}

	// On Linux, prefer the Engine socket when it exists — mirrors DockerCommand().
	if runtime.GOOS == "linux" {
		if _, err := os.Stat("/var/run/docker.sock"); err == nil {
			opts = append(opts, dockerclient.WithHost(DockerEngineSocket))
		}
	}

	cli, err := dockerclient.NewClientWithOpts(opts...)
	if err != nil {
		return nil, fmt.Errorf("create docker client: %w", err)
	}
	return &DockerClient{cli: cli}, nil
}

// Ping checks whether the Docker daemon is reachable.
func (d *DockerClient) Ping(ctx context.Context) error {
	_, err := d.cli.Ping(ctx)
	if err != nil {
		return fmt.Errorf("docker ping: %w", err)
	}
	return nil
}

// IsRunning returns true when the Docker daemon responds to a ping within 3 s.
func (d *DockerClient) IsRunning() bool {
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	return d.Ping(ctx) == nil
}

// PullImage pulls an image by reference, draining the progress stream to
// completion. Returns an error if the pull fails or the daemon is unreachable.
func (d *DockerClient) PullImage(ctx context.Context, refStr string) error {
	reader, err := d.cli.ImagePull(ctx, refStr, image.PullOptions{})
	if err != nil {
		return fmt.Errorf("image pull %s: %w", refStr, err)
	}
	defer reader.Close()

	// Drain the stream — the pull is not complete until EOF.
	if _, err := io.Copy(io.Discard, reader); err != nil {
		return fmt.Errorf("image pull stream %s: %w", refStr, err)
	}
	return nil
}

// ListContainers lists containers matching the given label filters.
// Pass nil or an empty map to list all running containers.
func (d *DockerClient) ListContainers(ctx context.Context, labelFilters map[string]string) ([]ContainerInfo, error) {
	opts := container.ListOptions{}
	if len(labelFilters) > 0 {
		f := filters.NewArgs()
		for k, v := range labelFilters {
			f.Add("label", k+"="+v)
		}
		opts.Filters = f
	}

	containers, err := d.cli.ContainerList(ctx, opts)
	if err != nil {
		return nil, fmt.Errorf("list containers: %w", err)
	}

	result := make([]ContainerInfo, 0, len(containers))
	for _, c := range containers {
		name := ""
		if len(c.Names) > 0 {
			name = strings.TrimPrefix(c.Names[0], "/")
		}

		ports := make([]PortBinding, 0, len(c.Ports))
		for _, p := range c.Ports {
			ports = append(ports, PortBinding{
				ContainerPort: p.PrivatePort,
				HostPort:      p.PublicPort,
				Protocol:      p.Type,
			})
		}

		result = append(result, ContainerInfo{
			ID:     c.ID[:12], // short ID, like docker CLI
			Name:   name,
			Image:  c.Image,
			State:  string(c.State),
			Status: c.Status,
			Ports:  ports,
			Labels: c.Labels,
		})
	}
	return result, nil
}

// InspectContainer returns detailed information about a single container.
func (d *DockerClient) InspectContainer(ctx context.Context, id string) (*ContainerDetail, error) {
	resp, err := d.cli.ContainerInspect(ctx, id)
	if err != nil {
		return nil, fmt.Errorf("inspect container %s: %w", id, err)
	}

	detail := &ContainerDetail{
		ID:      resp.ID[:12],
		Name:    strings.TrimPrefix(resp.Name, "/"),
		Image:   resp.Image,
		Created: resp.Created,
		Labels:  resp.Config.Labels,
	}

	if resp.State != nil {
		detail.State = resp.State.Status
		detail.Status = resp.State.Status
	}
	detail.Platform = resp.Platform
	detail.RestartCnt = resp.RestartCount

	// Map port bindings.
	if resp.NetworkSettings != nil {
		for port, bindings := range resp.NetworkSettings.Ports {
			for _, b := range bindings {
				var hostPort uint16
				if b.HostPort != "" {
					// Port string -> uint16 (safe; Docker only returns valid ports).
					for _, ch := range b.HostPort {
						hostPort = hostPort*10 + uint16(ch-'0')
					}
				}
				detail.Ports = append(detail.Ports, PortBinding{
					ContainerPort: uint16(port.Int()),
					HostPort:      hostPort,
					Protocol:      port.Proto(),
				})
			}
		}
	}

	// Flatten mount destinations.
	for _, m := range resp.Mounts {
		detail.Mounts = append(detail.Mounts, m.Destination)
	}

	return detail, nil
}

// Close releases the underlying HTTP transport.
func (d *DockerClient) Close() error {
	return d.cli.Close()
}

// ---------------------------------------------------------------------------
// DockerCommand — CLI exec helper (preserved for Compose operations & GPU).
// ---------------------------------------------------------------------------

// DockerEngineSocket is the default Unix socket for Docker Engine on Linux.
const DockerEngineSocket = "unix:///var/run/docker.sock"

// DockerCommand creates an exec.Command targeting Docker Engine.
// On Linux, sets DOCKER_HOST to the Engine socket to bypass Docker Desktop.
func DockerCommand(args ...string) *exec.Cmd {
	cmd := exec.Command("docker", args...)
	if runtime.GOOS == "linux" {
		if _, err := os.Stat("/var/run/docker.sock"); err == nil {
			env := os.Environ()
			// Remove any existing DOCKER_HOST to avoid talking to Desktop.
			filtered := make([]string, 0, len(env))
			for _, e := range env {
				if !strings.HasPrefix(e, "DOCKER_HOST=") {
					filtered = append(filtered, e)
				}
			}
			filtered = append(filtered, "DOCKER_HOST="+DockerEngineSocket)
			cmd.Env = filtered
		}
	}
	return cmd
}

// ---------------------------------------------------------------------------
// ServiceHealth & health polling (unchanged).
// ---------------------------------------------------------------------------

// ServiceHealth holds the health status of a single service.
type ServiceHealth struct {
	Name      string
	Healthy   bool
	Port      int
	Container string
}

// HealthEndpoint defines a service health check endpoint.
type HealthEndpoint struct {
	Name string
	URL  string
	Port int
}

// GetHealthEndpoints returns health check URLs for all services.
func GetHealthEndpoints(cfg Config) []HealthEndpoint {
	return []HealthEndpoint{
		{Name: "qdrant", URL: fmt.Sprintf("http://localhost:%d/healthz", cfg.Ports.Qdrant), Port: cfg.Ports.Qdrant},
		{Name: "ollama", URL: fmt.Sprintf("http://localhost:%d/api/tags", cfg.Ports.Ollama), Port: cfg.Ports.Ollama},
		{Name: "backend", URL: fmt.Sprintf("http://localhost:%d/api/health/live", cfg.Ports.Backend), Port: cfg.Ports.Backend},
		{Name: "frontend", URL: fmt.Sprintf("http://localhost:%d/healthz", cfg.Ports.Frontend), Port: cfg.Ports.Frontend},
	}
}

// PollHealth polls all health endpoints until all are healthy or context is cancelled.
func PollHealth(ctx context.Context, cfg Config, interval time.Duration, callback func(results []ServiceHealth)) error {
	endpoints := GetHealthEndpoints(cfg)

	// If using local ollama, check localhost:11434 directly.
	if cfg.Ollama.Mode == "local" {
		for i, ep := range endpoints {
			if ep.Name == "ollama" {
				endpoints[i].URL = "http://localhost:11434/api/tags"
				endpoints[i].Port = 11434
			}
		}
	}

	client := &http.Client{Timeout: 3 * time.Second}
	healthy := make(map[string]bool)

	for {
		select {
		case <-ctx.Done():
			return ctx.Err()
		default:
		}

		results := make([]ServiceHealth, len(endpoints))
		allHealthy := true

		for i, ep := range endpoints {
			results[i] = ServiceHealth{
				Name: ep.Name,
				Port: ep.Port,
			}

			if healthy[ep.Name] {
				results[i].Healthy = true
				continue
			}

			resp, err := client.Get(ep.URL)
			if err == nil {
				resp.Body.Close()
				if resp.StatusCode < 500 {
					healthy[ep.Name] = true
					results[i].Healthy = true
					continue
				}
			}

			allHealthy = false
		}

		if callback != nil {
			callback(results)
		}

		if allHealthy {
			return nil
		}

		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-time.After(interval):
		}
	}
}

// ---------------------------------------------------------------------------
// Compose CLI wrappers (unchanged — Compose stays as CLI exec).
// ---------------------------------------------------------------------------

// BuildComposeArgs constructs the docker compose file arguments.
// projectDir is the directory containing docker-compose.yml and overlay files.
func BuildComposeArgs(cfg Config, projectDir string) []string {
	compose := func(name string) string {
		return filepath.Join(projectDir, name)
	}
	hasFile := func(name string) bool {
		_, err := os.Stat(compose(name))
		return err == nil
	}

	args := []string{"-f", compose("docker-compose.yml")}

	if cfg.Ollama.Mode == "local" || cfg.Ollama.Mode == "remote" {
		// Use the local-ollama overlay to disable Docker Ollama.
		if hasFile("docker-compose.local-ollama.yml") {
			args = append(args, "-f", compose("docker-compose.local-ollama.yml"))
		}
	} else {
		// GPU overlay only applies to Docker Ollama.
		switch cfg.GPU.Profile {
		case "nvidia":
			if hasFile("docker-compose.gpu-nvidia.yml") {
				args = append(args, "-f", compose("docker-compose.gpu-nvidia.yml"))
			}
		case "amd":
			if hasFile("docker-compose.gpu-amd.yml") {
				args = append(args, "-f", compose("docker-compose.gpu-amd.yml"))
			}
		case "intel":
			if hasFile("docker-compose.gpu-intel.yml") {
				args = append(args, "-f", compose("docker-compose.gpu-intel.yml"))
			}
		}
	}

	if cfg.DevMode {
		if hasFile("docker-compose.dev.yml") {
			args = append(args, "-f", compose("docker-compose.dev.yml"))
		}
	}

	return args
}

// ComposeUp starts services via docker compose up.
// Output is captured to a log file instead of printing to stdout/stderr.
// On failure, the returned error includes the last portion of stderr for diagnostics.
func ComposeUp(projectDir string, composeArgs []string, build bool) error {
	cmdArgs := append([]string{"compose"}, composeArgs...)
	cmdArgs = append(cmdArgs, "up", "-d")
	if build {
		cmdArgs = append(cmdArgs, "--build")
	}

	cmd := DockerCommand(cmdArgs...)
	cmd.Dir = projectDir

	logFile, logPath, err := createComposeLogFile()
	if err != nil {
		// Fallback: discard output if log file creation fails.
		cmd.Stdout = io.Discard
		cmd.Stderr = io.Discard
		if runErr := cmd.Run(); runErr != nil {
			return fmt.Errorf("compose up failed: %w", runErr)
		}
		return nil
	}
	defer logFile.Close()

	cmd.Stdout = logFile
	cmd.Stderr = logFile

	if runErr := cmd.Run(); runErr != nil {
		return &ComposeError{
			Op:      "compose up",
			Err:     runErr,
			LogPath: logPath,
		}
	}
	return nil
}

// ComposeDown stops services via docker compose down.
// Output is suppressed (sent to the compose log file or discarded).
func ComposeDown(projectDir string, composeArgs []string, removeVolumes bool) error {
	cmdArgs := append([]string{"compose"}, composeArgs...)
	cmdArgs = append(cmdArgs, "down")
	if removeVolumes {
		cmdArgs = append(cmdArgs, "--volumes")
	}

	cmd := DockerCommand(cmdArgs...)
	cmd.Dir = projectDir

	logFile, _, err := createComposeLogFile()
	if err != nil {
		cmd.Stdout = io.Discard
		cmd.Stderr = io.Discard
	} else {
		defer logFile.Close()
		cmd.Stdout = logFile
		cmd.Stderr = logFile
	}

	return cmd.Run()
}

// ComposePS returns the output of docker compose ps.
func ComposePS(projectDir string, composeArgs []string) (string, error) {
	cmdArgs := append([]string{"compose"}, composeArgs...)
	cmdArgs = append(cmdArgs, "ps", "--format", "table")

	cmd := DockerCommand(cmdArgs...)
	cmd.Dir = projectDir
	out, err := cmd.CombinedOutput()
	return string(out), err
}

// ComposeLogs streams docker compose logs.
func ComposeLogs(projectDir string, composeArgs []string, service string, tail int, since string) error {
	cmdArgs := append([]string{"compose"}, composeArgs...)
	cmdArgs = append(cmdArgs, "logs", "-f")

	if tail > 0 {
		cmdArgs = append(cmdArgs, "--tail", fmt.Sprintf("%d", tail))
	}
	if since != "" {
		cmdArgs = append(cmdArgs, "--since", since)
	}
	if service != "" {
		cmdArgs = append(cmdArgs, service)
	}

	cmd := DockerCommand(cmdArgs...)
	cmd.Dir = projectDir
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr

	return cmd.Run()
}

// IsStackRunning checks if any Embedinator containers are currently running.
func IsStackRunning(projectDir string) bool {
	cmd := DockerCommand("compose", "ps", "--quiet")
	cmd.Dir = projectDir
	out, err := cmd.Output()
	if err != nil {
		return false
	}
	return strings.TrimSpace(string(out)) != ""
}

// ---------------------------------------------------------------------------
// ComposeError — structured error with log path for diagnostics.
// ---------------------------------------------------------------------------

// ComposeError wraps a compose command failure with the path to the full log.
type ComposeError struct {
	Op      string // e.g. "compose up"
	Err     error  // underlying exec error
	LogPath string // path to the full output log
}

func (e *ComposeError) Error() string {
	return fmt.Sprintf("%s failed: %v (full log: %s)", e.Op, e.Err, e.LogPath)
}

func (e *ComposeError) Unwrap() error {
	return e.Err
}

// ComposeLogPath returns the path to the compose log file if the error is a
// ComposeError, otherwise returns an empty string.
func ComposeLogPath(err error) string {
	var ce *ComposeError
	if errors.As(err, &ce) {
		return ce.LogPath
	}
	return ""
}

// createComposeLogFile creates a timestamped log file for compose output.
// Returns the file handle, the path, and any error.
func createComposeLogFile() (*os.File, string, error) {
	logDir := os.TempDir()
	logPath := filepath.Join(logDir, fmt.Sprintf("embedinator-compose-%d.log", time.Now().Unix()))
	f, err := os.Create(logPath)
	if err != nil {
		return nil, "", fmt.Errorf("create compose log: %w", err)
	}
	return f, logPath, nil
}
