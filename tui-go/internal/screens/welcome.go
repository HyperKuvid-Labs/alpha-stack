package screens

import (
	"github.com/charmbracelet/bubbles/spinner"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"

	"github.com/hyperkuvid-labs/alphastack/tui-go/internal/theme"
)

type Welcome struct {
	spinner spinner.Model
}

func NewWelcome() *Welcome {
	s := spinner.New()
	s.Spinner = spinner.MiniDot
	s.Style = lipgloss.NewStyle().Foreground(theme.Primary)
	return &Welcome{spinner: s}
}

func (w *Welcome) Init() tea.Cmd { return w.spinner.Tick }

func (w *Welcome) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch m := msg.(type) {
	case tea.KeyMsg:
		switch m.String() {
		case "enter", " ":
			return w, func() tea.Msg { return TransitionMsg{Direction: Forward} }
		}
	case spinner.TickMsg:
		var cmd tea.Cmd
		w.spinner, cmd = w.spinner.Update(msg)
		return w, cmd
	}
	return w, nil
}

func (w *Welcome) View() string {
	logo := theme.BigLogo("ai-powered project generator · build · validate · ship")
	body := lipgloss.JoinVertical(lipgloss.Left,
		logo,
		"",
		theme.HintStyle.Render(w.spinner.View()+"  ready when you are"),
		"",
		theme.PromptCaret.Render("›")+" "+theme.HintStyle.Render("press ↵ to begin"),
	)
	return theme.Frame.Render(body)
}

func (w *Welcome) Title() string { return "welcome" }

func (w *Welcome) KeyHints() [][2]string {
	return [][2]string{
		{"↵", "begin"},
		{"ctrl+c", "quit"},
	}
}
