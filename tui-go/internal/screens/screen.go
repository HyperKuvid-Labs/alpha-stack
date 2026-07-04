package screens

import tea "github.com/charmbracelet/bubbletea"

// Screen is the contract every sub-screen implements. The root App owns the
// chrome (header/footer) and embeds the active Screen's View().
type Screen interface {
	tea.Model
	Title() string
	KeyHints() [][2]string
}

// TransitionMsg signals "advance to the next state". The root App listens for
// this and instantiates the next Screen.
type TransitionMsg struct {
	Direction Dir // Forward or Back
}

type Dir int

const (
	Forward Dir = iota
	Back
)

// SubmitProviderMsg is sent by the provider screen to record the choice.
type SubmitProviderMsg struct {
	Name         string
	HasAPIKey    bool
	NeedsKey     bool
	DefaultModel string
}

// SubmitAPIKeyMsg is sent by the API key screen with the entered key.
type SubmitAPIKeyMsg struct {
	APIKey string
}

// KeepAPIKeyMsg is sent by the API key screen when the user presses ↵ on
// an empty input while a key is already stored. The App advances without
// touching the stored key.
type KeepAPIKeyMsg struct{}

// SubmitModelMsg is sent by the model screen with the chosen model name.
// The root App responds by issuing a ping_model RPC.
type SubmitModelMsg struct {
	Provider string
	Model    string
}

// SubmitPromptMsg is sent by the prompt screen.
type SubmitPromptMsg struct {
	Prompt string
}

// SubmitOutDirMsg is sent by the output dir screen.
type SubmitOutDirMsg struct {
	OutDir string
}

// NewProjectMsg is sent from the done screen to start another generation
// without quitting (provider/model are kept).
type NewProjectMsg struct{}

// OpenSettingsMsg is sent from the welcome screen to walk the full
// provider/key/model wizard instead of quick-starting with saved defaults.
type OpenSettingsMsg struct{}

// ConfirmStartMsg is sent when the user confirms generation start.
type ConfirmStartMsg struct{}

// QuitFromDoneMsg is sent when the user quits the done screen.
type QuitFromDoneMsg struct{}
