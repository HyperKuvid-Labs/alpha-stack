package rpc

import "encoding/json"

type Request struct {
	ID     string                 `json:"id"`
	Action string                 `json:"action"`
	Params map[string]interface{} `json:"params,omitempty"`
}

type Event struct {
	ID      string          `json:"id"`
	Type    string          `json:"type"`
	Message string          `json:"message"`
	Data    json.RawMessage `json:"data,omitempty"`
	TS      string          `json:"ts,omitempty"`
}

type Provider struct {
	Name         string `json:"name"`
	NeedsAPIKey  bool   `json:"needs_api_key"`
	HasAPIKey    bool   `json:"has_api_key"`
	IsDefault    bool   `json:"is_default"`
	DefaultModel string `json:"default_model"`
}

type ListProvidersResult struct {
	Providers []Provider `json:"providers"`
	Default   string     `json:"default"`
}

type ProviderStatusResult struct {
	Provider  string `json:"provider"`
	HasAPIKey bool   `json:"has_api_key"`
}

type SetAPIKeyResult struct {
	OK       bool   `json:"ok"`
	Provider string `json:"provider"`
	Error    string `json:"error,omitempty"`
}

type PingModelResult struct {
	OK       bool   `json:"ok"`
	Provider string `json:"provider"`
	Model    string `json:"model"`
	Message  string `json:"message,omitempty"`
	Error    string `json:"error,omitempty"`
}

type GenerateResult struct {
	Success      bool                   `json:"success"`
	ProjectPath  string                 `json:"project_path,omitempty"`
	ElapsedTime  float64                `json:"elapsed_time,omitempty"`
	Cancelled    bool                   `json:"cancelled,omitempty"`
	ErrorMessage string                 `json:"error,omitempty"`
	Extras       map[string]interface{} `json:"-"`
}

type LogData struct {
	Stream string `json:"stream"`
}

type ErrorData struct {
	Traceback string `json:"traceback,omitempty"`
}
