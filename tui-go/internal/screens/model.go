package screens

import (
	"github.com/charmbracelet/bubbles/textinput"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"

	"github.com/hyperkuvid-labs/alphastack/tui-go/internal/theme"
)

// ModelScreen asks the user for the model name to use for the selected
// provider, then pings it (via the python backend) before letting them
// proceed. If the ping fails, the error is rendered on this screen and
// the user can type a different name.
type ModelScreen struct {
	provider string
	input    textinput.Model
	pinging  bool
	err      string
	ok       string
}

func NewModel(provider, defaultModel string) *ModelScreen {
	in := textinput.New()
	in.Placeholder = "e.g. google/gemini-2.5-pro"
	in.Prompt = ""
	in.TextStyle = lipgloss.NewStyle().Foreground(theme.Accent)
	in.PlaceholderStyle = lipgloss.NewStyle().Foreground(theme.Muted)
	in.CharLimit = 200
	in.Width = 60
	if defaultModel != "" {
		in.SetValue(defaultModel)
		in.CursorEnd()
	}
	in.Focus()
	return &ModelScreen{provider: provider, input: in}
}

func (m *ModelScreen) MarkPinging()           { m.pinging = true; m.err = ""; m.ok = "" }
func (m *ModelScreen) ClearPinging(err string) { m.pinging = false; m.err = err; m.ok = "" }
func (m *ModelScreen) MarkOK(msg string)      { m.pinging = false; m.err = ""; m.ok = msg }
func (m *ModelScreen) Init() tea.Cmd           { return textinput.Blink }
func (m *ModelScreen) Title() string           { return "model" }

func (m *ModelScreen) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch mm := msg.(type) {
	case tea.KeyMsg:
		if m.pinging {
			// Ignore keystrokes while a ping is in flight.
			return m, nil
		}
		switch mm.String() {
		case "enter":
			val := m.input.Value()
			if val == "" {
				m.err = "model cannot be empty"
				return m, nil
			}
			return m, func() tea.Msg {
				return SubmitModelMsg{Provider: m.provider, Model: val}
			}
		}
	}
	var cmd tea.Cmd
	m.input, cmd = m.input.Update(msg)
	return m, cmd
}

func (m *ModelScreen) View() string {
	caret := theme.PromptCaret.Render("›")
	inputLine := caret + " " + m.input.View()

	body := lipgloss.JoinVertical(lipgloss.Left,
		theme.LabelStyle.Render("model for "+m.provider),
		theme.HintStyle.Render("edit or accept; we'll ping it to make sure the key + model work"),
		"",
		inputLine,
	)
	if m.pinging {
		body += "\n\n" + theme.HintStyle.Render("pinging model…")
	}
	if m.err != "" {
		body += "\n\n" + theme.EventErr.Render("✗ "+m.err)
		body += "\n" + theme.HintStyle.Render("type a different model name, or press esc to change provider")
	}
	if m.ok != "" {
		body += "\n\n" + theme.EventOK.Render("✓ model reachable: "+m.ok)
	}
	return theme.Frame.Render(body)
}

func (m *ModelScreen) KeyHints() [][2]string {
	return [][2]string{
		{"↵", "ping & continue"},
		{"esc", "back"},
		{"ctrl+c", "quit"},
	}
}
