# Python Number Adder

A simple Python script to add two numbers.

## Features

*   **Add Two Numbers**: The script defines a function that takes two numbers as arguments and returns their sum.

## Tech Stack

*   **Backend**: Python 3
*   **Testing**: unittest

## Folder Structure

```
python-number-adder/
├── README.md
├── requirements.txt
├── .gitignore
└── src/
    ├── __init__.py
    ├── main.py
    └── calculator/
        ├── __init__.py
        └── operations.py
```

## Getting Started

### Prerequisites

*   Python 3.x

### Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/python-number-adder.git
    cd python-number-adder
    ```
2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

### Usage

To run the script and add two numbers interactively:

```bash
python src/main.py
```
*(The `main.py` script will prompt you to enter two numbers.)*

## Running Tests

To run the unit tests for the project:

```bash
python -m unittest discover
```

## Contributing

Contributions are welcome! Please follow these steps:

1.  Fork the repository.
2.  Create a new branch (`git checkout -b feature/your-feature-name`).
3.  Make your changes.
4.  Commit your changes (`git commit -am 'Add new feature'`).
5.  Push to the branch (`git push origin feature/your-feature-name`).
6.  Create a new Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
