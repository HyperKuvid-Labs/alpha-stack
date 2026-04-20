package app

import "github.com/charmbracelet/bubbles/key"

type keyMap struct {
	Quit   key.Binding
	Back   key.Binding
	Cancel key.Binding
}

var keys = keyMap{
	Quit:   key.NewBinding(key.WithKeys("ctrl+c"), key.WithHelp("ctrl+c", "quit")),
	Back:   key.NewBinding(key.WithKeys("esc"), key.WithHelp("esc", "back")),
	Cancel: key.NewBinding(key.WithKeys("ctrl+c"), key.WithHelp("ctrl+c", "cancel")),
}
