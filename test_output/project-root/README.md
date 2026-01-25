# Number Addition API

A simple RESTful API that accepts two numbers via a POST request, validates the input, and returns the sum in a JSON response.

## Features

- **Addition Endpoint**: Validates numeric input and returns the sum of two numbers.
- **Input Validation**: Ensures provided inputs are valid numeric values.
- **JSON Response**: Returns structured response with sum and status.
- **Documentation**: OpenAPI/Swagger documentation available at `/apidocs` when running.

## API Documentation

### Endpoint: `POST /add`

**Request Body**
```json
{
  "num1": 5,
  "num2": 3
}
```

**Success Response (200 OK)**
```json
{
  "sum": 8,
  "status": "success"
}
```

**Error Response (400 Bad Request)**
```json
{
  "error": "Invalid input: Both num1 and num2 must be valid numbers",
  "status": "error"
}
```

## Quick Start

### Prerequisites
- Python 3.8+
- Docker (optional)

### Without Docker
1. Clone the repository:
   ```bash
   git clone https://github.com/your-repo/number-addition-api
   cd number-addition-api
   ```
2. Create virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the application:
   ```bash
   python src/main.py
   ```
5. Access the API at `http://localhost:5000` and documentation at `http://localhost:5000/apidocs`.

### With Docker
1. Build the image:
   ```bash
   docker build -t number-addition-api .
   ```
2. Run the container:
   ```bash
   docker run -p 5000:5000 number-addition-api
   ```

## Project Structure
```
project-root/
├── README.md
├── requirements.txt
├── .env.example
├── src/
│   ├── main.py          # Flask app initialization
│   ├── api/
│   │   ├── routes.py    # API route definitions
│   │   └── models.py    # Request/response models
│   ├── services/
│   │   └── addition_service.py  # Business logic
│   ├── utils/
│   │   └── validators.py  # Input validation
│   └── config/
│       └── settings.py  # Configuration settings
```

## Testing
Run tests with pytest:
```bash
pytest src/tests/
```

## Contributing
1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
