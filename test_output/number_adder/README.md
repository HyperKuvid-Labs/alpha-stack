# Number_Adder

![Python](https://img.shields.io/badge/python-3.x-blue.svg)

A simple command-line application to calculate the sum of two numbers.

## ✨ Features

- Accepts two numeric inputs from the command line.
- Calculates the sum of the two numbers.
- Outputs the result to the standard output.

## 🛠️ Tech Stack

- **Language:** Python 3
- **Testing:** pytest

## 📋 Prerequisites

- Python 3.8 or higher
- `pip` (Python package installer)

## 🚀 Getting Started

Follow these steps to get the project up and running on your local machine.

1.  **Clone the repository:**
    ```sh
    git clone https://github.com/your-username/Number_Adder.git
    cd Number_Adder
    ```

2.  **Create and activate a virtual environment:**
    *   On macOS/Linux:
        ```sh
        python3 -m venv venv
        source venv/bin/activate
        ```
    *   On Windows:
        ```sh
        python -m venv venv
        .\venv\Scripts\activate
        ```

3.  **Install dependencies:**
    ```sh
    pip install -r requirements.txt
    ```

## ▶️ Usage

Run the script from the root directory of the project, providing two numbers as command-line arguments.

```sh
python src/main.py <number1> <number2>
```

### Example

```sh
python src/main.py 10 25
```

**Expected Output:**

```
The sum of 10.0 and 25.0 is 35.0
```

## ✅ Running Tests

To run the automated tests for this project, use `pytest`. The tests are located in the `tests/` directory.

```sh
pytest
```

## 📂 Project Structure

The project follows a standard Python application structure:

```
number_adder/
├── README.md           # This file
├── requirements.txt    # Project dependencies
├── .gitignore          # Files to be ignored by Git
└── src/                # Source code directory
    ├── __init__.py     # Makes `src` a Python package
    ├── main.py         # Entry point of the application (handles I/O)
    └── calculator.py   # Core calculation logic (business logic)
