package theme

import (
	"strings"

	"github.com/charmbracelet/lipgloss"
)

// Big ASCII wordmark shown on the welcome screen. Uses half-block characters
// so every pane looks crisp in common terminal fonts. Keep under 60 columns
// wide so it fits inside the outer frame on an 80-col terminal.
const bigLogo = `
 █▀█ █   █▀█ █ █ █▀█ █▀ ▀█▀ ▄▀█ █▀▀ █ █
 █▀█ █▄▄ █▀▀ █▀█ █▀█ ▄█  █  █▀█ █▄▄ █▀▄
 ▀ ▀ ▀▀▀ ▀   ▀ ▀ ▀ ▀ ▀   ▀  ▀ ▀ ▀▀▀ ▀ ▀
`

// BigLogo renders the wordmark in the primary accent with a muted subtitle
// beneath. Used on the welcome screen.
func BigLogo(subtitle string) string {
	logoStyle := lipgloss.NewStyle().Foreground(Primary).Bold(true)
	subStyle := lipgloss.NewStyle().Foreground(Muted)

	trimmed := strings.Trim(bigLogo, "\n")
	rendered := logoStyle.Render(trimmed)

	if subtitle == "" {
		return rendered
	}
	return lipgloss.JoinVertical(lipgloss.Left,
		rendered,
		"",
		subStyle.Render(subtitle),
	)
}

// CompactLogo is the one-line header wordmark: "● alphastack".
// Already exposed as Wordmark() — kept here for discoverability.
func CompactLogo() string { return Wordmark() }
