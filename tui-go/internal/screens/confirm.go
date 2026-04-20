package screens

import (
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"

	"github.com/hyperkuvid-labs/alphastack/tui-go/internal/theme"
)

type ConfirmSummary struct {
	Provider string
	Model    string
	Prompt   string
	OutDir   string
	Profile  string
}

type ConfirmScreen struct {
	summary ConfirmSummary
}

func NewConfirm(s ConfirmSummary) *ConfirmScreen { return &ConfirmScreen{summary: s} }
func (c *ConfirmScreen) Init() tea.Cmd            { return nil }
func (c *ConfirmScreen) Title() string            { return "confirm" }

func (c *ConfirmScreen) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	if m, ok := msg.(tea.KeyMsg); ok {
		switch m.String() {
		case "enter":
			return c, tea.Sequence(
				func() tea.Msg { return ConfirmStartMsg{} },
				func() tea.Msg { return TransitionMsg{Direction: Forward} },
			)
		}
	}
	return c, nil
}

func (c *ConfirmScreen) View() string {
	row := func(label, value string) string {
		return theme.HintStyle.Render(label) + "  " + theme.ValueStyle.Render(value)
	}
	body := lipgloss.JoinVertical(lipgloss.Left,
		theme.LabelStyle.Render("review"),
		theme.HintStyle.Render("ready to start project generation"),
		"",
		row("provider", c.summary.Provider),
		row("model   ", c.summary.Model),
		row("profile ", c.summary.Profile),
		row("output  ", c.summary.OutDir),
		"",
		theme.HintStyle.Render("prompt"),
		lipgloss.NewStyle().Foreground(theme.Accent).Width(70).Render(c.summary.Prompt),
		"",
		theme.PromptCaret.Render("›")+" "+theme.HintStyle.Render("press ↵ to launch · esc to step back"),
	)
	return theme.Frame.Render(body)
}

func (c *ConfirmScreen) KeyHints() [][2]string {
	return [][2]string{
		{"↵", "start"},
		{"esc", "back"},
		{"ctrl+c", "quit"},
	}
}
