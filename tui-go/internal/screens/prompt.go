package screens

import (
	"strings"

	"github.com/charmbracelet/bubbles/textarea"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"

	"github.com/hyperkuvid-labs/alphastack/tui-go/internal/theme"
)

type PromptScreen struct {
	area textarea.Model
	err  string
}

func NewPrompt() *PromptScreen {
	t := textarea.New()
	t.Placeholder = "describe the project you want to build…"
	t.Prompt = ""
	t.ShowLineNumbers = false
	t.SetWidth(70)
	t.SetHeight(8)
	t.CharLimit = 4000
	t.FocusedStyle.CursorLine = lipgloss.NewStyle()
	t.FocusedStyle.Text = lipgloss.NewStyle().Foreground(theme.Accent)
	t.FocusedStyle.Placeholder = lipgloss.NewStyle().Foreground(theme.Muted)
	t.FocusedStyle.Prompt = lipgloss.NewStyle()
	t.BlurredStyle.Prompt = lipgloss.NewStyle()
	t.Focus()
	return &PromptScreen{area: t}
}

func (p *PromptScreen) Init() tea.Cmd { return textarea.Blink }
func (p *PromptScreen) Title() string { return "prompt" }

func (p *PromptScreen) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch m := msg.(type) {
	case tea.WindowSizeMsg:
		w := m.Width - 8
		if w < 30 {
			w = 30
		}
		p.area.SetWidth(w)
	case tea.KeyMsg:
		switch m.String() {
		case "ctrl+s":
			val := strings.TrimSpace(p.area.Value())
			if val == "" {
				p.err = "prompt cannot be empty"
				return p, nil
			}
			return p, tea.Sequence(
				func() tea.Msg { return SubmitPromptMsg{Prompt: val} },
				func() tea.Msg { return TransitionMsg{Direction: Forward} },
			)
		}
	}
	var cmd tea.Cmd
	p.area, cmd = p.area.Update(msg)
	return p, cmd
}

func (p *PromptScreen) View() string {
	caret := theme.PromptCaret.Render("›")
	indented := indentBlock(p.area.View(), "  ")
	body := lipgloss.JoinVertical(lipgloss.Left,
		theme.LabelStyle.Render("describe what to build"),
		theme.HintStyle.Render("ctrl+s to continue · ↵ inserts a newline"),
		"",
		caret+" "+theme.HintStyle.Render("prompt"),
		indented,
	)
	if p.err != "" {
		body += "\n" + theme.EventErr.Render("✗ "+p.err)
	}
	return theme.Frame.Render(body)
}

// indentBlock prepends `pad` to every line of `s`.
func indentBlock(s, pad string) string {
	lines := strings.Split(s, "\n")
	for i, l := range lines {
		lines[i] = pad + l
	}
	return strings.Join(lines, "\n")
}

func (p *PromptScreen) KeyHints() [][2]string {
	return [][2]string{
		{"ctrl+s", "save & continue"},
		{"esc", "back"},
		{"ctrl+c", "quit"},
	}
}
