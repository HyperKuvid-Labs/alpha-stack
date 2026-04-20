package rpc

// tea.Msg types delivered from the Python subprocess into the Bubbletea program.

type ProvidersLoadedMsg struct {
	Result ListProvidersResult
	Err    error
}

type ProviderStatusMsg struct {
	Result ProviderStatusResult
	Err    error
}

type APIKeySavedMsg struct {
	Result SetAPIKeyResult
	Err    error
}

type ModelPingedMsg struct {
	Result PingModelResult
	Err    error
}

type RPCEventMsg struct {
	Event Event
}

type RPCResultMsg struct {
	Event Event
}

type RPCStreamErrMsg struct {
	Err error
}

type RPCExitMsg struct {
	Code int
}
