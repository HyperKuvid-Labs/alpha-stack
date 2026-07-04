package app

import (
	"encoding/json"
	"fmt"
	"path/filepath"
	"time"

	tea "github.com/charmbracelet/bubbletea"

	"github.com/hyperkuvid-labs/alphastack/tui-go/internal/rpc"
	"github.com/hyperkuvid-labs/alphastack/tui-go/internal/screens"
)

type State int

const (
	StateWelcome State = iota
	StateProvider
	StateAPIKey
	StateModel
	StatePrompt
	StateOutputDir
	StateConfirm
	StateGenerating
	StateDone
)

type selection struct {
	provider     string
	providerNeed bool
	providerKey  bool
	defaultModel string
	apiKey       string
	model        string
	prompt       string
	outDir       string
}

type App struct {
	client *rpc.Client

	state    State
	sub      screens.Screen
	width    int
	height   int
	selected selection

	pendingProviders *rpc.ProvidersLoadedMsg
	providersInfo    *rpc.ProvidersLoadedMsg

	currentReqID string
	cancelTimer  time.Time

	exitCode int
}

func New(client *rpc.Client) *App {
	a := &App{client: client}
	a.sub = screens.NewWelcome()
	return a
}

func (a *App) ExitCode() int { return a.exitCode }

func (a *App) Init() tea.Cmd {
	return tea.Batch(
		tea.EnterAltScreen,
		a.sub.Init(),
		a.requestProvidersCmd(),
	)
}

func (a *App) requestProvidersCmd() tea.Cmd {
	return func() tea.Msg {
		_ = a.client.Send(rpc.Request{ID: newID(), Action: "list_providers"})
		return nil
	}
}

func (a *App) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch m := msg.(type) {
	case tea.WindowSizeMsg:
		a.width, a.height = m.Width, m.Height
		// fall through; sub may want it too
	case tea.KeyMsg:
		s := m.String()
		if s == "ctrl+c" {
			if a.state == StateGenerating {
				return a, a.handleCancel()
			}
			return a, tea.Quit
		}
		if s == "esc" && a.state != StateWelcome && a.state != StateGenerating && a.state != StateDone {
			return a, a.goBack()
		}
	case rpc.ProvidersLoadedMsg:
		msgKeep := m
		a.providersInfo = &msgKeep
		if ps, ok := a.sub.(*screens.ProviderScreen); ok {
			if m.Err != nil {
				ps.SetError(m.Err)
			} else {
				ps.SetProviders(m.Result.Providers, m.Result.Default)
			}
		} else {
			msgCopy := m
			a.pendingProviders = &msgCopy
		}
		return a, nil
	case rpc.APIKeySavedMsg:
		if ak, ok := a.sub.(*screens.APIKeyScreen); ok {
			if m.Err != nil {
				ak.ClearSaving(m.Err.Error())
				return a, nil
			}
			if !m.Result.OK {
				err := m.Result.Error
				if err == "" {
					err = "failed to save api key"
				}
				ak.ClearSaving(err)
				return a, nil
			}
			a.selected.providerKey = true
			return a, a.advance()
		}
	case screens.SubmitProviderMsg:
		a.selected.provider = m.Name
		a.selected.providerNeed = m.NeedsKey
		a.selected.providerKey = m.HasAPIKey
		a.selected.defaultModel = m.DefaultModel
		return a, nil
	case screens.SubmitAPIKeyMsg:
		a.selected.apiKey = m.APIKey
		if ak, ok := a.sub.(*screens.APIKeyScreen); ok {
			ak.MarkSaving()
		}
		return a, a.sendSetAPIKeyCmd(a.selected.provider, m.APIKey)
	case screens.KeepAPIKeyMsg:
		// User pressed ↵ with empty input while a key was already stored.
		// Advance without re-saving.
		return a, a.advance()
	case screens.SubmitModelMsg:
		a.selected.model = m.Model
		if ms, ok := a.sub.(*screens.ModelScreen); ok {
			ms.MarkPinging()
		}
		return a, a.sendPingModelCmd(m.Provider, m.Model, a.selected.apiKey)
	case rpc.ModelPingedMsg:
		if ms, ok := a.sub.(*screens.ModelScreen); ok {
			if m.Err != nil {
				ms.ClearPinging(m.Err.Error())
				return a, nil
			}
			if !m.Result.OK {
				errStr := m.Result.Error
				if errStr == "" {
					errStr = "model ping failed"
				}
				ms.ClearPinging(errStr)
				return a, nil
			}
			ms.MarkOK(m.Result.Message)
			a.selected.model = m.Result.Model
			return a, a.advance()
		}
		return a, nil
	case screens.SubmitPromptMsg:
		a.selected.prompt = m.Prompt
		return a, nil
	case screens.SubmitOutDirMsg:
		a.selected.outDir = m.OutDir
		return a, nil
	case screens.OpenSettingsMsg:
		return a, a.gotoProviderScreen()
	case screens.NewProjectMsg:
		a.selected.prompt = ""
		a.selected.outDir = ""
		a.state = StatePrompt
		a.sub = screens.NewPrompt()
		return a, tea.Batch(a.sub.Init(), a.windowResizeCmd())
	case screens.ConfirmStartMsg:
		return a, a.startGenerationCmd()
	case screens.QuitFromDoneMsg:
		return a, tea.Quit
	case screens.TransitionMsg:
		return a, a.advance()

	case rpc.RPCEventMsg:
		if g, ok := a.sub.(*screens.Generating); ok {
			g.HandleEvent(m.Event)
		}
		return a, nil
	case rpc.RPCResultMsg:
		return a, a.handleGenerateResult(m.Event)
	case rpc.RPCStreamErrMsg:
		if g, ok := a.sub.(*screens.Generating); ok {
			g.HandleEvent(rpc.Event{Type: "error", Message: "rpc stream error: " + m.Err.Error()})
		}
		return a, nil
	case rpc.RPCExitMsg:
		// only quit if not yet shown done screen
		if a.state != StateDone && a.state != StateGenerating {
			return a, tea.Quit
		}
		return a, nil
	}

	var cmd tea.Cmd
	a.sub, cmd = updateScreen(a.sub, msg)
	return a, cmd
}

func (a *App) View() string {
	extra := ""
	if a.selected.provider != "" {
		extra = a.selected.provider
	}
	header := renderHeader(a.width, a.sub.Title(), extra)
	footer := renderFooter(a.width, a.sub.KeyHints())
	return compose(a.width, a.height, header, a.sub.View(), footer)
}

// advance moves to the next state and instantiates the matching screen.
func (a *App) advance() tea.Cmd {
	switch a.state {
	case StateWelcome:
		// Quick start: when the default provider already has a saved key,
		// jump straight to the prompt with its default model. 's' on the
		// welcome screen still opens the full wizard.
		if info := a.providersInfo; info != nil && info.Err == nil {
			for _, p := range info.Result.Providers {
				if p.Name != info.Result.Default {
					continue
				}
				if !p.NeedsAPIKey || p.HasAPIKey {
					a.selected.provider = p.Name
					a.selected.providerNeed = p.NeedsAPIKey
					a.selected.providerKey = p.HasAPIKey
					a.selected.defaultModel = p.DefaultModel
					a.selected.model = p.DefaultModel
					a.state = StatePrompt
					a.sub = screens.NewPrompt()
					return tea.Batch(a.sub.Init(), a.windowResizeCmd())
				}
			}
		}
		return a.gotoProviderScreen()
	case StateProvider:
		if a.selected.providerNeed {
			a.state = StateAPIKey
			a.sub = screens.NewAPIKey(a.selected.provider, a.selected.providerKey)
			return tea.Batch(a.sub.Init(), a.windowResizeCmd())
		}
		fallthrough
	case StateAPIKey:
		a.state = StateModel
		a.sub = screens.NewModel(a.selected.provider, a.selected.defaultModel)
		return tea.Batch(a.sub.Init(), a.windowResizeCmd())
	case StateModel:
		a.state = StatePrompt
		a.sub = screens.NewPrompt()
		return tea.Batch(a.sub.Init(), a.windowResizeCmd())
	case StatePrompt:
		a.state = StateOutputDir
		def := defaultOutDir(a.selected.prompt)
		a.sub = screens.NewOutDir(def)
		return tea.Batch(a.sub.Init(), a.windowResizeCmd())
	case StateOutputDir:
		a.state = StateConfirm
		a.sub = screens.NewConfirm(screens.ConfirmSummary{
			Provider: a.selected.provider,
			Model:    a.selected.model,
			Prompt:   a.selected.prompt,
			OutDir:   a.selected.outDir,
		})
		return tea.Batch(a.sub.Init(), a.windowResizeCmd())
	case StateConfirm:
		a.state = StateGenerating
		a.sub = screens.NewGenerating()
		return tea.Batch(a.sub.Init(), a.windowResizeCmd())
	}
	return nil
}

func (a *App) gotoProviderScreen() tea.Cmd {
	a.state = StateProvider
	ps := screens.NewProvider()
	a.sub = ps
	if a.providersInfo != nil {
		if a.providersInfo.Err != nil {
			ps.SetError(a.providersInfo.Err)
		} else {
			ps.SetProviders(a.providersInfo.Result.Providers, a.providersInfo.Result.Default)
		}
	}
	a.pendingProviders = nil
	return tea.Batch(ps.Init(), a.windowResizeCmd())
}

func (a *App) goBack() tea.Cmd {
	switch a.state {
	case StateAPIKey:
		a.state = StateProvider
		ps := screens.NewProvider()
		a.sub = ps
		return tea.Batch(ps.Init(), a.windowResizeCmd(), a.requestProvidersCmd())
	case StateModel:
		if a.selected.providerNeed {
			a.state = StateAPIKey
			a.sub = screens.NewAPIKey(a.selected.provider, a.selected.providerKey)
		} else {
			a.state = StateProvider
			ps := screens.NewProvider()
			a.sub = ps
			return tea.Batch(ps.Init(), a.windowResizeCmd(), a.requestProvidersCmd())
		}
		return tea.Batch(a.sub.Init(), a.windowResizeCmd())
	case StatePrompt:
		a.state = StateModel
		a.sub = screens.NewModel(a.selected.provider, a.selected.model)
		return tea.Batch(a.sub.Init(), a.windowResizeCmd())
	case StateOutputDir:
		a.state = StatePrompt
		a.sub = screens.NewPrompt()
		return tea.Batch(a.sub.Init(), a.windowResizeCmd())
	case StateConfirm:
		a.state = StateOutputDir
		a.sub = screens.NewOutDir(defaultOutDir(a.selected.prompt))
		return tea.Batch(a.sub.Init(), a.windowResizeCmd())
	}
	return nil
}

func (a *App) windowResizeCmd() tea.Cmd {
	w, h := a.width, a.height
	if w == 0 {
		return nil
	}
	return func() tea.Msg { return tea.WindowSizeMsg{Width: w, Height: h} }
}

func (a *App) sendSetAPIKeyCmd(provider, key string) tea.Cmd {
	return func() tea.Msg {
		_ = a.client.Send(rpc.Request{
			ID:     newID(),
			Action: "set_api_key",
			Params: map[string]interface{}{"provider": provider, "api_key": key},
		})
		return nil
	}
}

func (a *App) sendPingModelCmd(provider, model, apiKey string) tea.Cmd {
	return func() tea.Msg {
		params := map[string]interface{}{"provider": provider, "model": model}
		if apiKey != "" {
			params["api_key"] = apiKey
		}
		_ = a.client.Send(rpc.Request{
			ID:     newID(),
			Action: "ping_model",
			Params: params,
		})
		return nil
	}
}

func (a *App) startGenerationCmd() tea.Cmd {
	return func() tea.Msg {
		id := newID()
		a.currentReqID = id
		_ = a.client.Send(rpc.Request{
			ID:     id,
			Action: "generate",
			Params: map[string]interface{}{
				"prompt":     a.selected.prompt,
				"output_dir": a.selected.outDir,
				"provider":   a.selected.provider,
				"model":      a.selected.model,
			},
		})
		return nil
	}
}

func (a *App) handleCancel() tea.Cmd {
	now := time.Now()
	if !a.cancelTimer.IsZero() && now.Sub(a.cancelTimer) < 2*time.Second {
		a.client.Terminate()
		return nil
	}
	a.cancelTimer = now
	if g, ok := a.sub.(*screens.Generating); ok {
		g.MarkCancelling()
	}
	_ = a.client.Cancel()
	return nil
}

func (a *App) handleGenerateResult(ev rpc.Event) tea.Cmd {
	var data map[string]interface{}
	if len(ev.Data) > 0 {
		_ = json.Unmarshal(ev.Data, &data)
	}
	success, _ := data["success"].(bool)
	cancelled, _ := data["cancelled"].(bool)
	projectPath, _ := data["project_path"].(string)
	elapsedF, _ := data["elapsed_time"].(float64)
	errMsg, _ := data["error"].(string)
	if success {
		a.exitCode = 0
	} else {
		a.exitCode = 1
	}
	a.state = StateDone
	a.sub = screens.NewDone(success, cancelled, projectPath, elapsedF, errMsg)
	return tea.Batch(a.sub.Init(), a.windowResizeCmd())
}

func defaultOutDir(prompt string) string {
	slug := slugify(prompt)
	if slug == "" {
		slug = "alphastack-project"
	}
	return filepath.Join("./created_projects", slug)
}

func slugify(s string) string {
	out := make([]byte, 0, len(s))
	dash := false
	for i := 0; i < len(s) && len(out) < 32; i++ {
		c := s[i]
		switch {
		case c >= 'a' && c <= 'z', c >= '0' && c <= '9':
			out = append(out, c)
			dash = false
		case c >= 'A' && c <= 'Z':
			out = append(out, c+32)
			dash = false
		default:
			if !dash && len(out) > 0 {
				out = append(out, '-')
				dash = true
			}
		}
	}
	for len(out) > 0 && out[len(out)-1] == '-' {
		out = out[:len(out)-1]
	}
	return string(out)
}

func newID() string {
	return fmt.Sprintf("r-%d", time.Now().UnixNano())
}

// updateScreen forwards a message to a Screen and reinterprets the returned
// tea.Model as the same Screen interface.
func updateScreen(s screens.Screen, msg tea.Msg) (screens.Screen, tea.Cmd) {
	model, cmd := s.Update(msg)
	if next, ok := model.(screens.Screen); ok {
		return next, cmd
	}
	return s, cmd
}
