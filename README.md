# Nuke

AI project generator experiment — natural language in, validated codebase out.

## Setup

```bash
git clone https://github.com/AdityaKaleeswarGK/Nuke.git
cd Nuke
pip install .

# Configure API keys (interactive)
alphastack setup
```

**Optional — CubeSandbox for sandboxed validation:**

```bash
curl -sL https://github.com/tencentcloud/CubeSandbox/raw/master/deploy/one-click/online-install.sh | bash

cubemastercli tpl create-from-image \
    --image ccr.ccs.tencentyun.com/ags-image/sandbox-code:latest \
    --writable-layer-size 1G

alphastack sandbox --template-id <id>
```

If no sandbox template is configured, shell commands fall back to running on the host.

## Running

```bash
# Generate a project
alphastack generate "A Flask REST API with user authentication and JWT tokens"

# Specify output directory
alphastack generate "Python CLI tool for file processing" -o /path/to/output

# List / clean generated projects
alphastack list
alphastack clean

# Interactive mode
alphastack
```

**Go TUI:**

```bash
cd tui-go && go build -o ../bin/alphastack-tui ./cmd/alphastack-tui
./bin/alphastack-tui
```

**Tests:**

```bash
python3 -m pytest -q
```
