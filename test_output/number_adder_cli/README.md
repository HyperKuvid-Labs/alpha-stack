# Number_Adder_CLI

![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)

A command-line tool that accepts two numbers as input and outputs their sum.

## Overview

This is a simple yet robust command-line interface (CLI) application built with Python. It takes two numerical arguments from the user, calculates their sum, and prints the result to the standard output. The project is structured to separate core logic from the command-line interface, making it clean, testable, and maintainable.

## Features

-   **Sum Calculation**: Accepts two numbers (integers or decimals) as command-line arguments.
-   **Core Logic**: Performs the addition.
-   **Standard Output**: Prints the calculated sum directly to the console.

## Prerequisites

-   Python 3.8 or newer
-   pip (Python package installer)

## Installation

1.  **Clone the repository:**
    ```sh
    git clone <repository_url>
    cd number_adder_cli
    ```

2.  **Create and activate a virtual environment (recommended):**
    ```sh
    python3 -m venv venv
    source venv/bin/activate
    # On Windows, use: venv\Scripts\activate
    ```

3.  **Install dependencies:**
    The project currently has no external dependencies, but if it did, you would install them using:
    ```sh
    pip install -r requirements.txt
    ```

## Usage

Run the application from the root directory of the project using the `python -m` command, which executes the package as a script. Provide two numbers as arguments.

**Syntax:**
```sh
python -m number_adder_cli <number1> <number2>
```

**Example:**
```sh
python -m number_adder_cli 10 25.5
```

**Expected Output:**
```
The sum of 10.0 and 25.5 is: 35.5
```

## Running Tests

This project uses `pytest` for testing. To run the test suite, ensure you have `pytest` installed (`pip install pytest`) and then execute the following command from the project's root directory:

```sh
pytest
```

## Project Structure

The project follows a standard Python application structure:

```
number_adder_cli/
├── .gitignore          # Git ignore file
├── README.md           # Project documentation
├── requirements.txt    # Project dependencies
└── src/
    └── number_adder_cli/
        ├── __init__.py     # Makes the directory a Python package
        ├── __main__.py     # CLI entry point for `python -m`
        └── core.py         # Core business logic for calculations
```

-   `src/number_adder_cli/core.py`: Contains pure functions for calculations, free of side effects. This is where the `add_numbers` function resides.
-   `src/number_adder_cli/__main__.py`: Serves as the command-line entry point. It handles argument parsing, calls the core logic, and prints the output.

## License

This project is licensed under the MIT License.
