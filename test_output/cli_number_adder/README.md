# CLI Number Adder

![Python](https://img.shields.io/badge/python-3-blue.svg)

A simple command-line utility to calculate the sum of two numbers provided as input.

## Features

-   The user provides two numbers as command-line arguments.
-   The application calculates the sum of the two numbers.
-   The application prints the result to the standard output.

## Prerequisites

-   Python 3.x

## Installation

1.  **Clone the repository:**
    ```sh
    git clone https://github.com/your-username/cli_number_adder.git
    cd cli_number_adder
    ```

2.  **Create and activate a virtual environment:**
    -   **macOS/Linux:**
        ```sh
        python3 -m venv venv
        source venv/bin/activate
        ```
    -   **Windows:**
        ```sh
        python -m venv venv
        venv\Scripts\activate
        ```

3.  **Install dependencies:**
    ```sh
    pip install -r requirements.txt
    ```

## Usage

Run the application from the root directory, providing two numbers as command-line arguments.

**Syntax:**
```sh
python src/main.py <number1> <number2>
```

**Examples:**

-   **Adding two integers:**
    ```sh
    python src/main.py 5 10
    ```
    **Output:**
    ```
    Result: 15.0
    ```

-   **Adding two floating-point numbers:**
    ```sh
    python src/main.py 3.14 2.71
    ```
    **Output:**
    ```
    Result: 5.85
    ```

-   **Invalid input:**
    The application will provide an error message if the arguments are not valid numbers.
    ```sh
    python src/main.py 5 five
    ```
    **Output:**
    ```
    Error: Both arguments must be valid numbers.
    ```

## Running Tests

This project uses `pytest` for testing. To run the test suite, execute the following command from the project's root directory:

```sh
pytest
```

## Project Structure

```
cli_number_adder/
├── README.md
├── requirements.txt
├── .gitignore
└── src/
    ├── __init__.py
    ├── calculator.py
    └── main.py
```

## License

This project is licensed under the MIT License.
