package screens

import (
	"strings"

	"github.com/charmbracelet/bubbles/textinput"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"

	"github.com/hyperkuvid-labs/alphastack/tui-go/internal/theme"
)

type OutDirScreen struct {
	input      textinput.Model
	defaultVal string
	err        string
}

func NewOutDir(defaultPath string) *OutDirScreen {
	in := textinput.New()
	in.Placeholder = defaultPath
	in.Prompt = ""
	in.TextStyle = lipgloss.NewStyle().Foreground(theme.Accent)
	in.PlaceholderStyle = lipgloss.NewStyle().Foreground(theme.Muted)
	in.CharLimit = 1024
	in.Width = 70
	in.Focus()
	return &OutDirScreen{input: in, defaultVal: defaultPath}
}

func (o *OutDirScreen) Init() tea.Cmd { return textinput.Blink }
func (o *OutDirScreen) Title() string { return "output" }

func (o *OutDirScreen) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch m := msg.(type) {
	case tea.KeyMsg:
		switch m.String() {
		case "enter":
			val := strings.TrimSpace(o.input.Value())
			if val == "" {
				val = o.defaultVal
			}
			if val == "" {
				o.err = "output directory cannot be empty"
				return o, nil
			}
			return o, tea.Sequence(
				func() tea.Msg { return SubmitOutDirMsg{OutDir: val} },
				func() tea.Msg { return TransitionMsg{Direction: Forward} },
			)
		}
	}
	var cmd tea.Cmd
	o.input, cmd = o.input.Update(msg)
	return o, cmd
}

func (o *OutDirScreen) View() string {
	caret := theme.PromptCaret.Render("›")
	body := lipgloss.JoinVertical(lipgloss.Left,
		theme.LabelStyle.Render("output directory"),
		theme.HintStyle.Render("press ↵ to accept the suggested path, or type your own"),
		"",
		caret+" "+o.input.View(),
	)
	if o.err != "" {
		body += "\n\n" + theme.EventErr.Render("✗ "+o.err)
	}
	return theme.Frame.Render(body)
}

func (o *OutDirScreen) KeyHints() [][2]string {
	return [][2]string{
		{"↵", "accept/continue"},
		{"esc", "back"},
		{"ctrl+c", "quit"},
	}
}
