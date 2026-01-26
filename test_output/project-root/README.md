# Number_Adder_API

A simple backend API that adds two numbers together and returns their sum.

## Features

- **Number Addition Endpoint**
  - Accepts two numbers as input parameters
  - Validates that both inputs are numeric values
  - Computes the sum of the two numbers
  - Returns the result as a JSON response

## Tech Stack

- **Backend**: Python / Flask
- **API Design**: RESTful
- **API Documentation**: Swagger UI
- **Testing Framework**: Pytest

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd Number_Adder_API
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Running the Application

Run the Flask application:

```bash
python src/main.py
```

The API will be available at `http://127.0.0.1:5000` (or as configured in `configs/settings.yaml`).

## API Documentation

Swagger UI documentation is available at `http://127.0.0.1:5000/swagger` after starting the application.

## Testing

Run the tests:

```bash
pytest
```

## Project Structure

```
project-root/
├── README.md
├── requirements.txt
├── .gitignore
├── src/
│   ├── __init__.py
│   ├── main.py
│   ├── app.py
│   ├── services/
│   │   ├── __init__.py
│   │   └── math_service.py
│   └── utils/
│       └── helpers.py
└── configs/
    └── settings.yaml
