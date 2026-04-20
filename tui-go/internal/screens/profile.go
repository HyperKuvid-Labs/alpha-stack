package screens

import (
	"fmt"
	"io"

	"github.com/charmbracelet/bubbles/list"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"

	"github.com/hyperkuvid-labs/alphastack/tui-go/internal/theme"
)

type profileItem struct {
	name string
	desc string
}

func (p profileItem) FilterValue() string { return p.name }
func (p profileItem) Title() string       { return p.name }
func (p profileItem) Description() string { return p.desc }

type profileDelegate struct{}

func (d profileDelegate) Height() int                             { return 1 }
func (d profileDelegate) Spacing() int                            { return 0 }
func (d profileDelegate) Update(_ tea.Msg, _ *list.Model) tea.Cmd { return nil }
func (d profileDelegate) Render(w io.Writer, m list.Model, index int, item list.Item) {
	it, ok := item.(profileItem)
	if !ok {
		return
	}
	selected := index == m.Index()
	var marker, name string
	if selected {
		marker = lipgloss.NewStyle().Foreground(theme.Primary).Render("●")
		name = theme.ListSelected.Render(it.name)
	} else {
		marker = theme.ListDim.Render("○")
		name = theme.ListUnselected.Render(it.name)
	}
	desc := theme.HintStyle.Render(it.desc)
	fmt.Fprintf(w, "  %s  %-10s  %s", marker, name, desc)
}

type ProfileScreen struct {
	list list.Model
}

func NewProfile() *ProfileScreen {
	items := []list.Item{
		profileItem{name: "others", desc: "general purpose (default)"},
		profileItem{name: "cuda", desc: "CUDA / C++ optimized"},
	}
	l := list.New(items, profileDelegate{}, 60, 6)
	l.SetShowTitle(false)
	l.SetShowStatusBar(false)
	l.SetFilteringEnabled(false)
	l.SetShowHelp(false)
	l.SetShowPagination(false)
	return &ProfileScreen{list: l}
}

func (p *ProfileScreen) Init() tea.Cmd { return nil }
func (p *ProfileScreen) Title() string { return "profile" }

func (p *ProfileScreen) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch m := msg.(type) {
	case tea.WindowSizeMsg:
		w := m.Width - 6
		if w < 30 {
			w = 30
		}
		p.list.SetSize(w, len(p.list.Items())+1)
	case tea.KeyMsg:
		switch m.String() {
		case "enter":
			it, ok := p.list.SelectedItem().(profileItem)
			if !ok {
				return p, nil
			}
			return p, tea.Sequence(
				func() tea.Msg { return SubmitProfileMsg{Profile: it.name} },
				func() tea.Msg { return TransitionMsg{Direction: Forward} },
			)
		}
	}
	var cmd tea.Cmd
	p.list, cmd = p.list.Update(msg)
	return p, cmd
}

func (p *ProfileScreen) View() string {
	body := lipgloss.JoinVertical(lipgloss.Left,
		theme.LabelStyle.Render("language profile"),
		"",
		p.list.View(),
	)
	return theme.Frame.Render(body)
}

func (p *ProfileScreen) KeyHints() [][2]string {
	return [][2]string{
		{"↑↓", "navigate"},
		{"↵", "select"},
		{"esc", "back"},
		{"ctrl+c", "quit"},
	}
}
