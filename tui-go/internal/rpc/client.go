package rpc

import (
	"bufio"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"os/exec"
	"sync"
	"syscall"
	"time"

	tea "github.com/charmbracelet/bubbletea"
)

// Sender is anything that can deliver tea.Msg values into the program.
// *tea.Program satisfies this; tests can use a channel-based fake.
type Sender interface {
	Send(msg tea.Msg)
}

type Client struct {
	pythonBin string
	args      []string

	cmd    *exec.Cmd
	stdin  io.WriteCloser
	stdout io.ReadCloser
	stderr io.ReadCloser

	sender Sender

	mu       sync.Mutex
	pending  map[string]string // request_id -> action (so result events can be typed)
	exitOnce sync.Once
}

// New constructs a Client that will spawn `pythonBin -u -m src.cli --json-rpc`.
func New(pythonBin string) *Client {
	return &Client{
		pythonBin: pythonBin,
		args:      []string{"-u", "-m", "src.cli", "--json-rpc"},
		pending:   make(map[string]string),
	}
}

// Attach binds the message sink (typically *tea.Program).
func (c *Client) Attach(s Sender) { c.sender = s }

func (c *Client) Start(cwd string) error {
	c.cmd = exec.Command(c.pythonBin, c.args...)
	c.cmd.Dir = cwd
	c.cmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}
	c.cmd.Env = append(os.Environ(), "PYTHONUNBUFFERED=1")

	var err error
	if c.stdin, err = c.cmd.StdinPipe(); err != nil {
		return err
	}
	if c.stdout, err = c.cmd.StdoutPipe(); err != nil {
		return err
	}
	if c.stderr, err = c.cmd.StderrPipe(); err != nil {
		return err
	}
	if err := c.cmd.Start(); err != nil {
		return fmt.Errorf("start python: %w", err)
	}

	go c.readStdout()
	go c.readStderr()
	go c.waitChild()
	return nil
}

func (c *Client) Send(req Request) error {
	if req.Action != "" {
		c.mu.Lock()
		c.pending[req.ID] = req.Action
		c.mu.Unlock()
	}
	buf, err := json.Marshal(req)
	if err != nil {
		return err
	}
	buf = append(buf, '\n')
	_, err = c.stdin.Write(buf)
	return err
}

// Cancel sends SIGINT to the child process group (current generation).
func (c *Client) Cancel() error {
	if c.cmd == nil || c.cmd.Process == nil {
		return nil
	}
	return syscall.Kill(-c.cmd.Process.Pid, syscall.SIGINT)
}

// Terminate escalates: SIGTERM, then SIGKILL after grace.
func (c *Client) Terminate() {
	if c.cmd == nil || c.cmd.Process == nil {
		return
	}
	_ = syscall.Kill(-c.cmd.Process.Pid, syscall.SIGTERM)
	go func() {
		time.Sleep(1 * time.Second)
		_ = syscall.Kill(-c.cmd.Process.Pid, syscall.SIGKILL)
	}()
}

func (c *Client) Close() error {
	if c.stdin != nil {
		_ = c.stdin.Close()
	}
	if c.cmd != nil {
		return c.cmd.Wait()
	}
	return nil
}

func (c *Client) takeAction(id string) string {
	c.mu.Lock()
	defer c.mu.Unlock()
	a := c.pending[id]
	delete(c.pending, id)
	return a
}

func (c *Client) peekAction(id string) string {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.pending[id]
}

func (c *Client) send(msg tea.Msg) {
	if c.sender != nil {
		c.sender.Send(msg)
	}
}

func (c *Client) readStdout() {
	scanner := bufio.NewScanner(c.stdout)
	scanner.Buffer(make([]byte, 1<<20), 8<<20)
	for scanner.Scan() {
		raw := scanner.Bytes()
		var ev Event
		if err := json.Unmarshal(raw, &ev); err != nil {
			c.send(RPCStreamErrMsg{Err: fmt.Errorf("decode: %w (%s)", err, string(raw))})
			continue
		}
		c.dispatch(ev)
	}
	if err := scanner.Err(); err != nil {
		c.send(RPCStreamErrMsg{Err: err})
	}
}

func (c *Client) readStderr() {
	scanner := bufio.NewScanner(c.stderr)
	scanner.Buffer(make([]byte, 1<<20), 8<<20)
	for scanner.Scan() {
		line := scanner.Text()
		ev := Event{
			Type:    "log",
			Message: line,
		}
		c.send(RPCEventMsg{Event: ev})
	}
}

func (c *Client) waitChild() {
	c.exitOnce.Do(func() {
		if c.cmd == nil {
			return
		}
		_ = c.cmd.Wait()
		code := 0
		if c.cmd.ProcessState != nil {
			code = c.cmd.ProcessState.ExitCode()
		}
		c.send(RPCExitMsg{Code: code})
	})
}

func (c *Client) dispatch(ev Event) {
	if ev.Type == "result" {
		action := c.takeAction(ev.ID)
		switch action {
		case "list_providers":
			var r ListProvidersResult
			if err := json.Unmarshal(ev.Data, &r); err != nil {
				c.send(ProvidersLoadedMsg{Err: err})
				return
			}
			c.send(ProvidersLoadedMsg{Result: r})
			return
		case "get_provider_status":
			var r ProviderStatusResult
			if err := json.Unmarshal(ev.Data, &r); err != nil {
				c.send(ProviderStatusMsg{Err: err})
				return
			}
			c.send(ProviderStatusMsg{Result: r})
			return
		case "set_api_key":
			var r SetAPIKeyResult
			if err := json.Unmarshal(ev.Data, &r); err != nil {
				c.send(APIKeySavedMsg{Err: err})
				return
			}
			c.send(APIKeySavedMsg{Result: r})
			return
		case "ping_model":
			var r PingModelResult
			if err := json.Unmarshal(ev.Data, &r); err != nil {
				c.send(ModelPingedMsg{Err: err})
				return
			}
			c.send(ModelPingedMsg{Result: r})
			return
		case "generate", "":
			c.send(RPCResultMsg{Event: ev})
			return
		}
	}

	// streaming event for the active generate request
	if c.peekAction(ev.ID) == "generate" || ev.ID == "" {
		c.send(RPCEventMsg{Event: ev})
		return
	}
	c.send(RPCEventMsg{Event: ev})
}
