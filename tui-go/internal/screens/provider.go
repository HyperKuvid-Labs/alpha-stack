package screens

import (
	"fmt"
	"io"
	"strings"

	"github.com/charmbracelet/bubbles/list"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"

	"github.com/hyperkuvid-labs/alphastack/tui-go/internal/rpc"
	"github.com/hyperkuvid-labs/alphastack/tui-go/internal/theme"
)

type providerItem struct {
	provider rpc.Provider
}

func (p providerItem) FilterValue() string { return p.provider.Name }
func (p providerItem) Title() string       { return p.provider.Name }
func (p providerItem) Description() string { return providerStatus(p.provider) }

func providerStatus(p rpc.Provider) string {
	switch {
	case !p.NeedsAPIKey:
		return "local"
	case p.HasAPIKey:
		return "key set"
	default:
		return "key needed"
	}
}

type providerDelegate struct{}

func (d providerDelegate) Height() int                             { return 1 }
func (d providerDelegate) Spacing() int                            { return 0 }
func (d providerDelegate) Update(_ tea.Msg, _ *list.Model) tea.Cmd { return nil }
func (d providerDelegate) Render(w io.Writer, m list.Model, index int, item list.Item) {
	it, ok := item.(providerItem)
	if !ok {
		return
	}
	selected := index == m.Index()
	var marker, name string
	if selected {
		marker = lipgloss.NewStyle().Foreground(theme.Primary).Render("●")
		name = theme.ListSelected.Render(it.provider.Name)
	} else {
		marker = theme.ListDim.Render("○")
		name = theme.ListUnselected.Render(it.provider.Name)
	}

	tag := ""
	if it.provider.IsDefault {
		tag = "  " + theme.HintStyle.Render("(default)")
	}

	status := theme.HintStyle.Render(providerStatus(it.provider))
	if selected {
		switch {
		case !it.provider.NeedsAPIKey:
			status = theme.BadgeMuted.Render("local")
		case it.provider.HasAPIKey:
			status = theme.BadgeOK.Render("key set")
		default:
			status = theme.BadgeWarn.Render("key needed")
		}
	}

	line := fmt.Sprintf("  %s  %s%s", marker, name, tag)
	pad := 28 - lipgloss.Width(line)
	if pad < 1 {
		pad = 1
	}
	fmt.Fprint(w, line+strings.Repeat(" ", pad)+status)
}

type ProviderScreen struct {
	list    list.Model
	loading bool
	err     error
	width   int
	height  int
}

func NewProvider() *ProviderScreen {
	l := list.New([]list.Item{}, providerDelegate{}, 60, 14)
	l.SetShowTitle(false)
	l.SetShowStatusBar(false)
	l.SetFilteringEnabled(false)
	l.SetShowHelp(false)
	l.SetShowPagination(false)
	return &ProviderScreen{list: l, loading: true}
}

func (p *ProviderScreen) SetProviders(provs []rpc.Provider, defaultName string) {
	items := make([]list.Item, 0, len(provs))
	defaultIdx := 0
	for i, pr := range provs {
		items = append(items, providerItem{provider: pr})
		if pr.Name == defaultName {
			defaultIdx = i
		}
	}
	p.list.SetItems(items)
	p.list.Select(defaultIdx)
	w := p.list.Width()
	if w == 0 {
		w = 60
	}
	p.list.SetSize(w, len(items)+1)
	p.loading = false
}

func (p *ProviderScreen) SetError(err error) { p.err = err; p.loading = false }
func (p *ProviderScreen) Init() tea.Cmd      { return nil }

func (p *ProviderScreen) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch m := msg.(type) {
	case tea.WindowSizeMsg:
		p.width, p.height = m.Width, m.Height
		w := m.Width - 6
		if w < 30 {
			w = 30
		}
		h := len(p.list.Items()) + 1
		if h < 3 {
			h = 3
		}
		p.list.SetSize(w, h)
	case tea.KeyMsg:
		if p.loading {
			return p, nil
		}
		switch m.String() {
		case "enter":
			it, ok := p.list.SelectedItem().(providerItem)
			if !ok {
				return p, nil
			}
			return p, tea.Sequence(
				func() tea.Msg {
					return SubmitProviderMsg{
						Name:         it.provider.Name,
						HasAPIKey:    it.provider.HasAPIKey,
						NeedsKey:     it.provider.NeedsAPIKey,
						DefaultModel: it.provider.DefaultModel,
					}
				},
				func() tea.Msg { return TransitionMsg{Direction: Forward} },
			)
		}
	}
	if p.loading {
		return p, nil
	}
	var cmd tea.Cmd
	p.list, cmd = p.list.Update(msg)
	return p, cmd
}

func (p *ProviderScreen) View() string {
	if p.loading {
		return theme.Frame.Render(theme.HintStyle.Render("loading providers…"))
	}
	if p.err != nil {
		return theme.Frame.Render(theme.EventErr.Render("error: " + p.err.Error()))
	}
	body := lipgloss.JoinVertical(lipgloss.Left,
		theme.LabelStyle.Render("choose a model provider"),
		"",
		p.list.View(),
	)
	return theme.Frame.Render(body)
}

func (p *ProviderScreen) Title() string { return "provider" }

func (p *ProviderScreen) KeyHints() [][2]string {
	return [][2]string{
		{"↑↓", "navigate"},
		{"↵", "select"},
		{"esc", "back"},
		{"ctrl+c", "quit"},
	}
}
