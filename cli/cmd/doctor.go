package cmd

import (
	"encoding/json"
	"fmt"
	"path/filepath"

	"github.com/spf13/cobra"

	"github.com/Bruno-Ghiberto/The-Embedinator/cli/internal/engine"
	"github.com/Bruno-Ghiberto/The-Embedinator/cli/internal/version"
)

var (
	doctorJSON bool
	doctorFix  bool
)

var doctorCmd = &cobra.Command{
	Use:   "doctor",
	Short: "Diagnose common problems",
	Long:  "Run comprehensive diagnostics for The Embedinator installation.",
	RunE:  runDoctor,
}

func init() {
	doctorCmd.Flags().BoolVar(&doctorJSON, "json", false, "Output as JSON")
	doctorCmd.Flags().BoolVar(&doctorFix, "fix", false, "Attempt automatic fixes for common issues")
	rootCmd.AddCommand(doctorCmd)
}

type doctorReport struct {
	System       systemInfo      `json:"system"`
	Config       configStatus    `json:"config"`
	Services     []serviceStatus `json:"services"`
	Suggestions  []string        `json:"suggestions"`
	Errors       []string        `json:"errors"`
}

type systemInfo struct {
	OS          string `json:"os"`
	Docker      string `json:"docker"`
	Compose     string `json:"compose"`
	DiskSpaceGB uint64 `json:"disk_space_gb"`
	RAMGB       uint64 `json:"ram_gb"`
	CLIVersion  string `json:"cli_version"`
}

type configStatus struct {
	Found      bool   `json:"found"`
	Valid      bool   `json:"valid"`
	EnvFound   bool   `json:"env_found"`
	FernetSet  bool   `json:"fernet_set"`
	GPUProfile string `json:"gpu_profile"`
}

type serviceStatus struct {
	Name    string `json:"name"`
	Status  string `json:"status"`
	Port    int    `json:"port"`
}

func runDoctor(cmd *cobra.Command, args []string) error {
	dir, err := resolveProjectDir()
	if err != nil {
		return err
	}

	report := doctorReport{}

	// System info.
	osInfo := engine.DetectOS()
	dockerCheck := engine.CheckDocker()
	composeCheck := engine.CheckDockerCompose()
	diskCheck := engine.CheckDiskSpace(dir, 15)
	ramCheck := engine.CheckRAM(4)

	report.System = systemInfo{
		OS:         fmt.Sprintf("%s/%s", osInfo.OS, osInfo.Arch),
		Docker:     dockerCheck.Detail,
		Compose:    composeCheck.Detail,
		CLIVersion: version.Full(),
	}

	if !dockerCheck.OK {
		report.Errors = append(report.Errors, "Docker: "+dockerCheck.Error)
	}
	if !composeCheck.OK {
		report.Errors = append(report.Errors, "Compose: "+composeCheck.Error)
	}
	if !diskCheck.OK {
		report.Suggestions = append(report.Suggestions, "Low disk space: "+diskCheck.Error)
	}
	if !ramCheck.OK {
		report.Suggestions = append(report.Suggestions, "Low RAM: "+ramCheck.Error)
	}

	// Config status.
	configPath := filepath.Join(dir, "config.yaml")
	report.Config.Found = engine.ConfigExists(configPath)
	if report.Config.Found {
		cfg, err := engine.ReadConfig(configPath)
		if err == nil {
			report.Config.Valid = engine.ValidateConfig(cfg) == nil
			report.Config.GPUProfile = cfg.GPU.Profile
		}
	} else {
		report.Suggestions = append(report.Suggestions, "No config.yaml found. Run 'embedinator setup'.")
	}

	// .env status.
	envPath := filepath.Join(dir, ".env")
	if _, err := engine.ReadDotEnvValue(envPath, "EMBEDINATOR_FERNET_KEY"); err == nil {
		report.Config.EnvFound = true
		report.Config.FernetSet = true
	}

	// Service health.
	cfg := engine.DefaultConfig()
	if report.Config.Found {
		cfg, _ = engine.ReadConfig(configPath)
	}

	endpoints := engine.GetHealthEndpoints(cfg)
	for _, ep := range endpoints {
		status := "unreachable"
		if !engine.IsPortAvailable(ep.Port) {
			status = "port in use"
		}
		report.Services = append(report.Services, serviceStatus{
			Name:   ep.Name,
			Status: status,
			Port:   ep.Port,
		})
	}

	// Output.
	if doctorJSON {
		data, _ := json.MarshalIndent(report, "", "  ")
		fmt.Println(string(data))
		return nil
	}

	fmt.Println("\nThe Embedinator Doctor")
	fmt.Println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

	fmt.Println("\n  System:")
	fmt.Printf("    %-16s %s\n", "OS", report.System.OS)
	fmt.Printf("    %-16s %s\n", "Docker", report.System.Docker)
	fmt.Printf("    %-16s %s\n", "Compose", report.System.Compose)
	fmt.Printf("    %-16s %s\n", "CLI", report.System.CLIVersion)

	fmt.Println("\n  Configuration:")
	fmt.Printf("    %-16s found=%v valid=%v\n", "config.yaml", report.Config.Found, report.Config.Valid)
	fmt.Printf("    %-16s found=%v fernet=%v\n", ".env", report.Config.EnvFound, report.Config.FernetSet)
	fmt.Printf("    %-16s %s\n", "GPU", report.Config.GPUProfile)

	fmt.Println("\n  Services:")
	for _, svc := range report.Services {
		fmt.Printf("    %-16s %-12s port %d\n", svc.Name, svc.Status, svc.Port)
	}

	if len(report.Errors) > 0 {
		fmt.Println("\n  Errors:")
		for _, e := range report.Errors {
			fmt.Printf("    [!] %s\n", e)
		}
	}

	if len(report.Suggestions) > 0 {
		fmt.Println("\n  Suggestions:")
		for _, s := range report.Suggestions {
			fmt.Printf("    [?] %s\n", s)
		}
	}

	fmt.Printf("\n  Overall: %d errors, %d suggestions\n\n", len(report.Errors), len(report.Suggestions))

	return nil
}
