package screens

import (
	"github.com/charmbracelet/bubbles/textinput"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"

	"github.com/hyperkuvid-labs/alphastack/tui-go/internal/theme"
)

type APIKeyScreen struct {
	provider    string
	input       textinput.Model
	hasExisting bool
	saving      bool
	err         string
}

func NewAPIKey(provider string, hasExisting bool) *APIKeyScreen {
	in := textinput.New()
	if hasExisting {
		in.Placeholder = "paste new key to update, or ↵ to keep existing"
	} else {
		in.Placeholder = "paste key, then ↵"
	}
	in.EchoMode = textinput.EchoPassword
	in.EchoCharacter = '•'
	in.Prompt = ""
	in.TextStyle = lipgloss.NewStyle().Foreground(theme.Accent)
	in.PlaceholderStyle = lipgloss.NewStyle().Foreground(theme.Muted)
	in.CharLimit = 256
	in.Width = 60
	in.Focus()
	return &APIKeyScreen{provider: provider, input: in, hasExisting: hasExisting}
}

func (a *APIKeyScreen) MarkSaving()            { a.saving = true; a.err = "" }
func (a *APIKeyScreen) ClearSaving(err string) { a.saving = false; a.err = err }
func (a *APIKeyScreen) Init() tea.Cmd          { return textinput.Blink }
func (a *APIKeyScreen) Title() string          { return "api key" }

func (a *APIKeyScreen) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch m := msg.(type) {
	case tea.KeyMsg:
		switch m.String() {
		case "enter":
			val := a.input.Value()
			if val == "" {
				if a.hasExisting {
					// Keep the stored key — skip save, go straight to next step.
					return a, func() tea.Msg { return KeepAPIKeyMsg{} }
				}
				a.err = "api key cannot be empty"
				return a, nil
			}
			return a, func() tea.Msg { return SubmitAPIKeyMsg{APIKey: val} }
		}
	}
	var cmd tea.Cmd
	a.input, cmd = a.input.Update(msg)
	return a, cmd
}

func (a *APIKeyScreen) View() string {
	caret := theme.PromptCaret.Render("›")
	inputLine := caret + " " + a.input.View()

	title := "api key for " + a.provider
	hint := "stored locally at ~/.alphastack/config.json (chmod 0600)"
	if a.hasExisting {
		title = "api key for " + a.provider + "  " + theme.HintStyle.Render("(already set)")
		hint = "paste a new key to replace it, or just press ↵ to keep it"
	}

	body := lipgloss.JoinVertical(lipgloss.Left,
		theme.LabelStyle.Render(title),
		theme.HintStyle.Render(hint),
		"",
		inputLine,
	)
	if a.saving {
		body += "\n\n" + theme.HintStyle.Render("saving…")
	}
	if a.err != "" {
		body += "\n\n" + theme.EventErr.Render("✗ "+a.err)
	}
	return theme.Frame.Render(body)
}

func (a *APIKeyScreen) KeyHints() [][2]string {
	saveLabel := "save & continue"
	if a.hasExisting {
		saveLabel = "update / keep & continue"
	}
	return [][2]string{
		{"↵", saveLabel},
		{"esc", "back"},
		{"ctrl+c", "quit"},
	}
}
