package rpc

import (
	"path/filepath"
	"testing"
	"time"

	tea "github.com/charmbracelet/bubbletea"
)

type chanSender struct{ ch chan tea.Msg }

func (c chanSender) Send(msg tea.Msg) { c.ch <- msg }

func TestRPCListProviders(t *testing.T) {
	cwd, err := filepath.Abs("../../..")
	if err != nil {
		t.Fatal(err)
	}

	c := New("python3")
	sink := chanSender{ch: make(chan tea.Msg, 32)}
	c.Attach(sink)

	if err := c.Start(cwd); err != nil {
		t.Fatalf("start: %v", err)
	}
	defer c.Close()

	if err := c.Send(Request{ID: "t1", Action: "list_providers"}); err != nil {
		t.Fatalf("send: %v", err)
	}

	deadline := time.After(8 * time.Second)
	for {
		select {
		case msg := <-sink.ch:
			switch m := msg.(type) {
			case ProvidersLoadedMsg:
				if m.Err != nil {
					t.Fatalf("loaded with err: %v", m.Err)
				}
				if len(m.Result.Providers) == 0 {
					t.Fatal("expected at least one provider")
				}
				if m.Result.Default == "" {
					t.Fatal("expected default provider name")
				}
				return
			case RPCStreamErrMsg:
				t.Fatalf("stream err: %v", m.Err)
			case RPCExitMsg:
				t.Fatalf("python exited (code=%d) before result", m.Code)
			}
		case <-deadline:
			t.Fatal("timeout waiting for ProvidersLoadedMsg")
		}
	}
}
