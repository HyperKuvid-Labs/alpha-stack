package screens

import (
	"fmt"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"

	"github.com/hyperkuvid-labs/alphastack/tui-go/internal/theme"
)

type DoneScreen struct {
	success     bool
	cancelled   bool
	projectPath string
	elapsed     float64
	errMsg      string
}

func NewDone(success, cancelled bool, projectPath string, elapsed float64, errMsg string) *DoneScreen {
	return &DoneScreen{
		success:     success,
		cancelled:   cancelled,
		projectPath: projectPath,
		elapsed:     elapsed,
		errMsg:      errMsg,
	}
}

func (d *DoneScreen) Init() tea.Cmd { return nil }
func (d *DoneScreen) Title() string { return "done" }

func (d *DoneScreen) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	if m, ok := msg.(tea.KeyMsg); ok {
		switch m.String() {
		case "n":
			return d, func() tea.Msg { return NewProjectMsg{} }
		case "enter", "q", "esc":
			return d, func() tea.Msg { return QuitFromDoneMsg{} }
		}
	}
	return d, nil
}

func (d *DoneScreen) View() string {
	var headline string
	switch {
	case d.cancelled:
		headline = theme.EventWarn.Render("⚠ ") + theme.LabelStyle.Render("generation cancelled")
	case d.success:
		headline = theme.EventOK.Render("✓ ") + theme.LabelStyle.Render("generation complete")
	default:
		headline = theme.EventErr.Render("✗ ") + theme.LabelStyle.Render("generation failed")
	}

	row := func(label, value string) string {
		return theme.HintStyle.Render(label) + "  " + theme.ValueStyle.Render(value)
	}

	body := lipgloss.JoinVertical(lipgloss.Left,
		headline,
		"",
		row("project ", d.projectPath),
		row("elapsed ", fmt.Sprintf("%.2fs", d.elapsed)),
	)
	if d.errMsg != "" {
		body += "\n\n" + theme.EventErr.Render("error: "+d.errMsg)
	}
	body += "\n\n" + theme.PromptCaret.Render("›") + " " + theme.HintStyle.Render("press n for a new project · ↵ or q to exit")
	return theme.Frame.Render(body)
}

func (d *DoneScreen) KeyHints() [][2]string {
	return [][2]string{
		{"n", "new project"},
		{"↵/q", "exit"},
	}
}
