package theme

import "github.com/charmbracelet/lipgloss"

// Subtle, whitespace-first styles modeled after Claude Code & opencode.
// No heavy panels: chrome is conveyed by color and spacing, not borders.

var (
	// Subtle container used only when we need a soft enclosure (e.g. textarea).
	Subtle = lipgloss.NewStyle().
		Border(lipgloss.NormalBorder(), false, false, false, true).
		BorderForeground(Faint).
		PaddingLeft(1)

	// Borderless container — most screens use this.
	Frame = lipgloss.NewStyle().Padding(0, 2)

	HeaderDot   = lipgloss.NewStyle().Foreground(Primary).Bold(true)
	HeaderTitle = lipgloss.NewStyle().Foreground(Accent).Bold(true)
	HeaderCrumb = lipgloss.NewStyle().Foreground(Muted)
	HeaderTimer = lipgloss.NewStyle().Foreground(Muted)
	HeaderRule  = lipgloss.NewStyle().Foreground(Faint)

	FooterKey  = lipgloss.NewStyle().Foreground(Accent)
	FooterDesc = lipgloss.NewStyle().Foreground(Muted)
	FooterSep  = lipgloss.NewStyle().Foreground(Faint)

	LabelStyle = lipgloss.NewStyle().Foreground(Accent).Bold(true)
	HintStyle  = lipgloss.NewStyle().Foreground(Muted)
	ValueStyle = lipgloss.NewStyle().Foreground(Accent)
	DimValue   = lipgloss.NewStyle().Foreground(Muted)

	PromptCaret = lipgloss.NewStyle().Foreground(Primary).Bold(true)

	EventStep   = lipgloss.NewStyle().Foreground(Primary).Bold(true)
	EventOK     = lipgloss.NewStyle().Foreground(Success)
	EventWarn   = lipgloss.NewStyle().Foreground(Warning)
	EventErr    = lipgloss.NewStyle().Foreground(Error)
	EventLog    = lipgloss.NewStyle().Foreground(Accent)
	EventLogDim = lipgloss.NewStyle().Foreground(Muted)
	Timestamp   = lipgloss.NewStyle().Foreground(Faint)

	ListSelected   = lipgloss.NewStyle().Foreground(Primary).Bold(true)
	ListUnselected = lipgloss.NewStyle().Foreground(Accent)
	ListDim        = lipgloss.NewStyle().Foreground(Muted)

	BadgeOK    = lipgloss.NewStyle().Foreground(Success)
	BadgeWarn  = lipgloss.NewStyle().Foreground(Warning)
	BadgeMuted = lipgloss.NewStyle().Foreground(Muted)

	BannerSubtitle = lipgloss.NewStyle().Foreground(Muted)
	Divider        = lipgloss.NewStyle().Foreground(Faint)
)

// Wordmark renders the bullet + name used in the top-left header.
func Wordmark() string {
	return HeaderDot.Render("●") + " " + HeaderTitle.Render("alphastack")
}

// JoinKeyHints builds a footer line: "key  desc · key  desc · …" with subtle
// separators. Each pair is (key, description).
func JoinKeyHints(pairs ...[2]string) string {
	out := ""
	for i, p := range pairs {
		if i > 0 {
			out += FooterSep.Render("  ·  ")
		}
		out += FooterKey.Render(p[0]) + " " + FooterDesc.Render(p[1])
	}
	return out
}
