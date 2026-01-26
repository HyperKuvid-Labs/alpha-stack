# Number Adder CLI

A simple command-line tool that takes two numbers as input and outputs their sum.

## Features

-   Accepts two numbers as command-line arguments.
-   Calculates the sum of the two numbers.
-   Prints the result to the standard output.
-   Includes basic error handling for invalid or missing inputs.

## Requirements

-   Python 3.8+

## Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/Number_Adder_CLI.git
    cd Number_Adder_CLI
    ```

2.  **Create and activate a virtual environment (recommended):**
    ```bash
    # For Linux/macOS
    python3 -m venv venv
    source venv/bin/activate

    # For Windows
    python -m venv venv
    .\venv\Scripts\activate
    ```

3.  **Install development dependencies (for testing):**
    The project has no external runtime dependencies, but `pytest` is used for testing.
    ```bash
    pip install -r requirements.txt
    ```

## Usage

Run the tool from the root directory of the project, providing two numbers as arguments.

```bash
python -m number_adder_cli <number1> <number2>
```

### Example

```bash
python -m number_adder_cli 10 5
```

**Output:**
```
15
```

### Error Handling

If incorrect arguments are provided, the tool will display an error message.

**Example (Invalid Input):**
```bash
python -m number_adder_cli 10 hello
```

**Output:**
```
Error: Both arguments must be valid numbers.
```

**Example (Incorrect number of arguments):**
```bash
python -m number_adder_cli 5
```

**Output:**
```
Usage: python -m number_adder_cli <number1> <number2>
```

## Testing

This project uses `pytest`. To run the test suite, execute the following command from the root directory:

```bash
pytest
