// Render-only smoke utility: instantiate each screen and print its View() at
// 100x30 so we can eyeball the redesign without a TTY.
package main

import (
	"encoding/json"
	"fmt"

	tea "github.com/charmbracelet/bubbletea"

	"github.com/hyperkuvid-labs/alphastack/tui-go/internal/rpc"
	"github.com/hyperkuvid-labs/alphastack/tui-go/internal/screens"
)

const W, H = 100, 32

func size(s screens.Screen) {
	s.Update(tea.WindowSizeMsg{Width: W, Height: H})
}

func dump(label string, s screens.Screen) {
	size(s)
	fmt.Printf("\n══ %s ══\n", label)
	fmt.Println(s.View())
}

func main() {
	dump("welcome", screens.NewWelcome())

	prov := screens.NewProvider()
	prov.SetProviders([]rpc.Provider{
		{Name: "google", NeedsAPIKey: true, HasAPIKey: true},
		{Name: "openai", NeedsAPIKey: true, HasAPIKey: false},
		{Name: "vllm", NeedsAPIKey: false, HasAPIKey: true},
		{Name: "openrouter", NeedsAPIKey: true, HasAPIKey: true, IsDefault: true},
		{Name: "prime_intellect", NeedsAPIKey: true, HasAPIKey: false},
	}, "openrouter")
	dump("provider", prov)

	dump("api key", screens.NewAPIKey("openai"))
	dump("prompt", screens.NewPrompt())
	dump("output dir", screens.NewOutDir("./created_projects/my-flask-app"))
	dump("profile", screens.NewProfile())
	dump("confirm", screens.NewConfirm(screens.ConfirmSummary{
		Provider: "openrouter",
		Prompt:   "build a flask hello world app with a /health endpoint",
		OutDir:   "./created_projects/flask-hello",
		Profile:  "others",
	}))

	gen := screens.NewGenerating()
	size(gen)
	gen.HandleEvent(rpc.Event{Type: "step", Message: "analyzing structure and creating unified blueprint"})
	gen.HandleEvent(rpc.Event{Type: "log", Message: "querying openrouter/openai/gpt-5.4-mini"})
	gen.HandleEvent(rpc.Event{Type: "success", Message: "blueprint received (12 files)"})
	gen.HandleEvent(rpc.Event{Type: "step", Message: "building project tree"})
	gen.HandleEvent(rpc.Event{Type: "log", Message: "writing src/main.py"})
	gen.HandleEvent(rpc.Event{Type: "log", Message: "writing src/server.py"})
	gen.HandleEvent(rpc.Event{Type: "warning", Message: "missing requirements.txt — generating"})
	gen.HandleEvent(rpc.Event{Type: "progress", Message: "resolving dependencies"})
	dump("generating", gen)

	data, _ := json.Marshal(map[string]interface{}{"success": true, "project_path": "./created_projects/flask-hello", "elapsed_time": 142.3})
	_ = data
	dump("done (success)", screens.NewDone(true, false, "./created_projects/flask-hello", 142.3, ""))
	dump("done (cancelled)", screens.NewDone(false, true, "./created_projects/flask-hello", 13.4, ""))
	dump("done (failed)", screens.NewDone(false, false, "./created_projects/flask-hello", 87.2, "openrouter returned 401"))
}
