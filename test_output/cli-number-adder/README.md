# CLI Number Adder

![Python 3](https://img.shields.io/badge/python-3-blue.svg)

A command-line tool that accepts two numbers as arguments and prints their sum to the console.

## Features

- User executes the script from the terminal, passing two numbers as command-line arguments.
- The script validates that the inputs are valid numbers.
- The script calculates the sum of the two numbers.
- The result is printed to the standard output.

## Prerequisites

- Python 3.8 or higher

## Installation

1.  **Clone the repository:**
    ```sh
    git clone https://github.com/your-username/cli-number-adder.git
    cd cli-number-adder
    ```

2.  **Create and activate a virtual environment (recommended):**
    ```sh
    # For macOS/Linux
    python3 -m venv venv
    source venv/bin/activate

    # For Windows
    python -m venv venv
    .\venv\Scripts\activate
    ```

3.  **Install dependencies:**
    This project has no external dependencies, but if it did, you would install them using:
    ```sh
    pip install -r requirements.txt
    ```

## Usage

Run the tool from the root directory of the project, passing two numbers as arguments.

**Syntax:**
```sh
python -m number_adder <number1> <number2>
```

**Example:**
```sh
python -m number_adder 10 25
```

**Output:**
```
35.0
```

### Error Handling

If non-numeric arguments are provided, the script will print an error message.

**Example:**
```sh
python -m number_adder 5 apple
```

**Output:**
```
Error: Both arguments must be valid numbers.
```

## Running Tests

To run the automated tests for this project, use the `unittest` module's discovery feature:

```sh
python -m unittest discover
```

## Project Structure

```
cli-number-adder/
├── README.md
├── .gitignore
├── requirements.txt
└── number_adder/
    ├── __init__.py      # Makes number_adder a Python package
    ├── __main__.py      # Main entry point for `python -m number_adder`
    └── calculator.py    # Core logic for calculation
