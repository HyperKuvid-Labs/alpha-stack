package app

import (
	"strings"

	"github.com/charmbracelet/lipgloss"

	"github.com/hyperkuvid-labs/alphastack/tui-go/internal/theme"
)

// renderHeader: "●  alphastack    crumb · screen     extra" + thin rule.
// No box, no gradient — just a single line and a hairline divider, like
// Claude Code's session header.
func renderHeader(width int, screenTitle, extra string) string {
	if width <= 0 {
		width = 80
	}
	left := theme.Wordmark()
	if screenTitle != "" {
		left += "  " + theme.HeaderCrumb.Render("›  "+screenTitle)
	}
	right := theme.HeaderTimer.Render(extra)

	pad := width - lipgloss.Width(left) - lipgloss.Width(right) - 4
	if pad < 1 {
		pad = 1
	}
	line := "  " + left + strings.Repeat(" ", pad) + right + "  "
	rule := theme.HeaderRule.Render(strings.Repeat("─", width))
	return line + "\n" + rule
}

// renderFooter: dim line of "key desc · key desc · …", indented, no box.
func renderFooter(width int, hints [][2]string) string {
	if width <= 0 {
		width = 80
	}
	rule := theme.HeaderRule.Render(strings.Repeat("─", width))
	body := "  " + theme.JoinKeyHints(hints...)
	return rule + "\n" + body
}

func compose(width, height int, header, body, footer string) string {
	if width <= 0 {
		width = 80
	}

	inner := lipgloss.JoinVertical(lipgloss.Left,
		header,
		"",
		body,
		"",
		footer,
	)

	// Outer chrome: a rounded border that breathes away from the terminal
	// edges. Width math: total width − outer margins (2+2) − border (1+1)
	// − inner padding (2+2) = width−10.
	innerWidth := width - 10
	if innerWidth < 40 {
		innerWidth = 40
	}
	frame := lipgloss.NewStyle().
		Border(lipgloss.RoundedBorder()).
		BorderForeground(theme.Faint).
		Padding(1, 2).
		Width(innerWidth)

	outer := lipgloss.NewStyle().Margin(1, 2)
	return outer.Render(frame.Render(inner))
}
