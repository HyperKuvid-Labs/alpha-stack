package screens

import (
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"github.com/charmbracelet/bubbles/spinner"
	"github.com/charmbracelet/bubbles/viewport"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"

	"github.com/hyperkuvid-labs/alphastack/tui-go/internal/rpc"
	"github.com/hyperkuvid-labs/alphastack/tui-go/internal/theme"
)

type tickMsg time.Time

func tickEvery() tea.Cmd {
	return tea.Tick(time.Second, func(t time.Time) tea.Msg { return tickMsg(t) })
}

type stats struct {
	success  int
	warning  int
	errCount int
	progress int
	phase    int
}

type Generating struct {
	viewport     viewport.Model
	spinner      spinner.Model
	stats        stats
	currentPhase string
	startedAt    time.Time
	elapsed      time.Duration
	cancelling   bool
	width        int
	height       int
	logLines     []string
	maxLines     int
}

func NewGenerating() *Generating {
	vp := viewport.New(80, 18)
	vp.Style = lipgloss.NewStyle()

	sp := spinner.New()
	sp.Spinner = spinner.MiniDot
	sp.Style = lipgloss.NewStyle().Foreground(theme.Primary)

	return &Generating{
		viewport:     vp,
		spinner:      sp,
		startedAt:    time.Now(),
		currentPhase: "preparing pipeline",
		maxLines:     500,
	}
}

func (g *Generating) Init() tea.Cmd {
	return tea.Batch(g.spinner.Tick, tickEvery())
}

func (g *Generating) Title() string    { return "generating" }
func (g *Generating) Cancelling() bool { return g.cancelling }
func (g *Generating) MarkCancelling()  { g.cancelling = true }

func (g *Generating) HandleEvent(ev rpc.Event) {
	ts := time.Now().Format("15:04:05")
	switch ev.Type {
	case "step":
		g.stats.phase++
		g.currentPhase = fmt.Sprintf("%d. %s", g.stats.phase, ev.Message)
		// Section break in the transcript — blank gutter row, then a bold
		// "phase N" header that visually separates the coming log lines.
		g.appendLine("")
		g.appendLine(
			"  " + theme.EventStep.Render("▍") +
				" " + theme.EventStep.Render(fmt.Sprintf("phase %d", g.stats.phase)) +
				" " + theme.HintStyle.Render("·") +
				" " + theme.LabelStyle.Render(ev.Message),
		)
	case "success":
		g.stats.success++
		g.appendLine(g.formatStructured(ts, "ok", theme.EventOK, "✓", ev.Message))
	case "warning":
		g.stats.warning++
		g.appendLine(g.formatStructured(ts, "warn", theme.EventWarn, "⚠", ev.Message))
	case "error":
		g.stats.errCount++
		g.appendLine(g.formatStructured(ts, "err", theme.EventErr, "✗", ev.Message))
		var ed rpc.ErrorData
		if len(ev.Data) > 0 {
			_ = json.Unmarshal(ev.Data, &ed)
			if ed.Traceback != "" {
				lines := strings.Split(strings.TrimRight(ed.Traceback, "\n"), "\n")
				start := 0
				if len(lines) > 8 {
					start = len(lines) - 8
				}
				for _, l := range lines[start:] {
					g.appendLine("        " + theme.EventErr.Render("│ ") + theme.HintStyle.Render(l))
				}
			}
		}
	case "log":
		g.appendLine(g.formatStructured(ts, "log", theme.EventLogDim, "⎿", ev.Message))
	case "progress":
		g.stats.progress++
		g.appendLine(g.formatStructured(ts, "info", theme.EventLogDim, "·", ev.Message))
	}
}

func (g *Generating) appendLine(line string) {
	g.logLines = append(g.logLines, line)
	if len(g.logLines) > g.maxLines {
		g.logLines = g.logLines[len(g.logLines)-g.maxLines:]
	}
	wasAtBottom := g.viewport.AtBottom()
	g.viewport.SetContent(strings.Join(g.logLines, "\n"))
	if wasAtBottom {
		g.viewport.GotoBottom()
	}
}

func (g *Generating) formatLine(ts, marker, msg string) string {
	return "  " + theme.Timestamp.Render(ts) + "  " + marker + " " + msg
}

// formatStructured renders a log line with aligned columns:
//
//	  15:04:05  │  OK    │ message body here
//
// Level is padded to 4 chars so ✓/⚠/✗/· icons all line up. The pipe
// separators are faint so they read as visual scaffolding, not data.
func (g *Generating) formatStructured(ts, level string, style lipgloss.Style, icon, msg string) string {
	levelCell := style.Render(padRight(strings.ToUpper(level), 4))
	iconCell := style.Render(icon)
	pipe := theme.Divider.Render("│")
	return "  " +
		theme.Timestamp.Render(ts) + "  " +
		pipe + " " + iconCell + " " + levelCell + " " +
		pipe + " " + theme.EventLog.Render(msg)
}

func padRight(s string, n int) string {
	if len(s) >= n {
		return s
	}
	return s + strings.Repeat(" ", n-len(s))
}

func (g *Generating) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	var cmds []tea.Cmd

	switch m := msg.(type) {
	case tea.WindowSizeMsg:
		g.width, g.height = m.Width, m.Height
		// Compensate for outer frame chrome added by compose():
		// margin(2) + border(1) + padding(2) = 5 per side (10 horiz, 6 vert),
		// plus header/footer/gutters (~8 vert) and status rows (~4).
		w := m.Width - 12
		h := m.Height - 18
		if w < 40 {
			w = 40
		}
		if h < 6 {
			h = 6
		}
		g.viewport.Width = w
		g.viewport.Height = h
	case tickMsg:
		g.elapsed = time.Since(g.startedAt)
		cmds = append(cmds, tickEvery())
	case spinner.TickMsg:
		var c tea.Cmd
		g.spinner, c = g.spinner.Update(msg)
		cmds = append(cmds, c)
	}

	var c tea.Cmd
	g.viewport, c = g.viewport.Update(msg)
	cmds = append(cmds, c)

	return g, tea.Batch(cmds...)
}

func (g *Generating) View() string {
	mins := int(g.elapsed.Minutes())
	secs := int(g.elapsed.Seconds()) % 60
	timer := theme.HeaderTimer.Render(fmt.Sprintf("%02d:%02d", mins, secs))

	statusLine := theme.EventStep.Render("● ") + theme.LabelStyle.Render(g.currentPhase) +
		"  " + g.spinner.View() + " " + theme.HintStyle.Render("working") +
		"   " + timer
	if g.cancelling {
		statusLine = theme.EventWarn.Render("⚠ cancelling…  waiting for python to clean up   ") + timer
	}

	statsLine := strings.Join([]string{
		theme.HintStyle.Render(fmt.Sprintf("%d phases", g.stats.phase)),
		theme.BadgeOK.Render(fmt.Sprintf("✓ %d", g.stats.success)),
		theme.BadgeWarn.Render(fmt.Sprintf("⚠ %d", g.stats.warning)),
		theme.BadgeMuted.Render(fmt.Sprintf("✗ %d", g.stats.errCount)),
		theme.BadgeMuted.Render(fmt.Sprintf("· %d", g.stats.progress)),
	}, theme.FooterSep.Render(" · "))
	if g.stats.errCount > 0 {
		// re-render error stat bright
		statsLine = strings.Join([]string{
			theme.HintStyle.Render(fmt.Sprintf("%d phases", g.stats.phase)),
			theme.BadgeOK.Render(fmt.Sprintf("✓ %d", g.stats.success)),
			theme.BadgeWarn.Render(fmt.Sprintf("⚠ %d", g.stats.warning)),
			theme.EventErr.Render(fmt.Sprintf("✗ %d", g.stats.errCount)),
			theme.BadgeMuted.Render(fmt.Sprintf("· %d", g.stats.progress)),
		}, theme.FooterSep.Render(" · "))
	}

	body := lipgloss.JoinVertical(lipgloss.Left,
		"  "+statusLine,
		"",
		g.viewport.View(),
		"",
		"  "+statsLine,
	)
	return body
}

func (g *Generating) KeyHints() [][2]string {
	return [][2]string{
		{"↑↓", "scroll"},
		{"pgup/pgdn", "page"},
		{"ctrl+c", "cancel"},
	}
}
