# Nuke

AI project generator experiment — natural language in, validated codebase out.

## Setup

```bash
git clone https://github.com/HyperKuvid-Labs/alpha-stack.git
cd alpha-stack
pip install -e .

# Configure API keys (interactive)
alphastack setup
```

Validation runs on the host: test installs go into each generated project's local `.venv`, never your global environment.

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
