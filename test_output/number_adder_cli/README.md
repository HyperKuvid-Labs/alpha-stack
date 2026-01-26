# Number Adder CLI

![Python 3](https://img.shields.io/badge/python-3-blue.svg)

A command-line tool that accepts two numbers as input and outputs their sum.

## Features

-   **Sum Calculation**: The user provides two numbers as command-line arguments.
-   **Argument Parsing**: The tool parses the arguments and calculates the sum.
-   **Standard Output**: The result is printed to the standard output.

## Requirements

-   Python 3

## Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/Number_Adder_CLI.git
    cd Number_Adder_CLI
    ```

2.  **(Recommended) Create and activate a virtual environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    # On Windows, use `venv\Scripts\activate`
    ```

3.  **Install dependencies:**
    The project currently has no external dependencies, but if it did, you would install them using:
    ```bash
    pip install -r requirements.txt
    ```

## Usage

Run the main script from the project's root directory, providing two numbers as arguments.

### Syntax
```bash
python -m src.number_adder_cli.main <number1> <number2>
```

### Example
```bash
python -m src.number_adder_cli.main 15 30.5
```

### Expected Output
```
The sum of 15.0 and 30.5 is: 45.5
```

## Project Structure

```
number_adder_cli/
├── .gitignore
├── README.md
├── requirements.txt
└── src/
    └── number_adder_cli/
        ├── __init__.py       # Initializes the Python package
        ├── calculator.py     # Contains the core addition logic
        └── main.py           # Entry point for the CLI
