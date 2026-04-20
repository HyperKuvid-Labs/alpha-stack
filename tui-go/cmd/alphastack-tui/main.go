package main

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"

	tea "github.com/charmbracelet/bubbletea"

	"github.com/hyperkuvid-labs/alphastack/tui-go/internal/app"
	"github.com/hyperkuvid-labs/alphastack/tui-go/internal/rpc"
)

func main() {
	pythonBin := resolvePython()
	cwd := resolveRepoRoot()

	client := rpc.New(pythonBin)
	model := app.New(client)
	program := tea.NewProgram(model, tea.WithAltScreen())
	client.Attach(program)

	if err := client.Start(cwd); err != nil {
		fmt.Fprintf(os.Stderr, "alphastack-tui: failed to start python (%s): %v\n", pythonBin, err)
		os.Exit(2)
	}

	if _, err := program.Run(); err != nil {
		fmt.Fprintf(os.Stderr, "alphastack-tui: %v\n", err)
		os.Exit(2)
	}

	_ = client.Close()
	os.Exit(model.ExitCode())
}

func resolvePython() string {
	if v := os.Getenv("ALPHASTACK_PYTHON"); v != "" {
		return v
	}
	for _, name := range []string{"python3", "python"} {
		if p, err := exec.LookPath(name); err == nil {
			return p
		}
	}
	return "python3"
}

func resolveRepoRoot() string {
	if v := os.Getenv("ALPHASTACK_REPO"); v != "" {
		return v
	}
	exe, err := os.Executable()
	if err == nil {
		exe, _ = filepath.EvalSymlinks(exe)
		dir := filepath.Dir(exe)
		// dir is .../bin; repo root is one level up
		root := filepath.Dir(dir)
		if _, err := os.Stat(filepath.Join(root, "src", "cli.py")); err == nil {
			return root
		}
	}
	wd, err := os.Getwd()
	if err == nil {
		return wd
	}
	return "."
}
