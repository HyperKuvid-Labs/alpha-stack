# RustCalc

A command-line interface calculator written in Rust, designed to parse and evaluate mathematical expressions instantly within the terminal.

## Features

- **Basic Arithmetic**: Parse and compute addition, subtraction, multiplication, and division.
- **Operator Precedence**: Full support for standard mathematical order of operations and parentheses.
- **Command-Line Arguments**: Accept calculations as direct arguments for quick evaluations.
- **Interactive Mode**: A built-in REPL (Read-Eval-Print Loop) for multi-step calculations.

## Installation

### Prerequisites

- Rust (latest stable version)
- Cargo (comes with Rust)

### Build from Source

Clone the repository and build the project using Cargo:

```bash
git clone <repository-url>
cd RustCalc
cargo build --release
```

The binary will be available at `target/release/rustcalc`.

### Docker

A minimal Docker image is available based on Alpine Linux.

```bash
docker build -t rustcalc .
docker run -it --rm rustcalc
```

## Usage

### Single Expression

Evaluate a mathematical expression directly from the command line:

```bash
rustcalc "2 * (3 + 4)"
```

Output:

```
14
```

### Interactive Mode

Launch the calculator in interactive mode to perform multiple calculations:

```bash
rustcalc -i
# or
rustcalc --interactive
```

Once in the REPL, enter expressions and press Enter to see the result. Type `exit` or press `Ctrl+C` to quit.

Example REPL session:

```text
> 10 + 5
15
> (10 + 5) / 3
5
> exit
```

## Development

### Running Tests

The project uses the built-in Rust testing framework.

```bash
cargo test
```

### Generating Documentation

Generate and open the documentation locally:

```bash
cargo doc --open
```

## Project Structure

```
RustCalc/
├── .gitignore
├── Cargo.toml
├── README.md
└── src/
    ├── main.rs
    ├── cli.rs
    └── parser.rs
