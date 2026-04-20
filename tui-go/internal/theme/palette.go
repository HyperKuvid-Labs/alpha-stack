package theme

import "github.com/charmbracelet/lipgloss"

// Palette inspired by Claude Code & opencode: near-black background, a single
// warm accent (Claude coral), and otherwise muted neutrals.
var (
	Primary = lipgloss.Color("#D97757") // Claude coral / signature accent
	Accent  = lipgloss.Color("#E8E8E6") // off-white body text
	Info    = lipgloss.Color("#82A1FF") // soft blue, used sparingly
	Success = lipgloss.Color("#9ECE6A")
	Warning = lipgloss.Color("#E0AF68")
	Error   = lipgloss.Color("#F7768E")
	Muted   = lipgloss.Color("#6B7280")
	Faint   = lipgloss.Color("#3F4147")
	Bg      = lipgloss.Color("#0F0F10")
	BgPanel = lipgloss.Color("#161618")
	Fg      = lipgloss.Color("#E8E8E6")
)
