import pytest
from flask import Flask
import json

# Assuming the Flask app is created by a factory function in src.main
from src.main import create_app


@pytest.fixture
def app():
    app = create_app()
    app.config.update({
        "TESTING": True,
    })
    yield app


@pytest.fixture
def client(app: Flask):
    return app.test_client()


@pytest.mark.parametrize("payload, expected_sum", [
    ({"number1": 5, "number2": 3}, 8.0),
    ({"number1": -10, "number2": 10}, 0.0),
    ({"number1": 0, "number2": 0}, 0.0),
    ({"number1": 1.5, "number2": 2.5}, 4.0),
    ({"number1": -5.5, "number2": 2.0}, -3.5),
    ({"number1": 1000000000, "number2": 2000000000}, 3000000000.0),
])
def test_add_numbers_success(client, mocker, payload, expected_sum):
    mock_add = mocker.patch('src.api.routes.add_service.add', return_value=expected_sum)
    
    response = client.post('/add', json=payload)
    data = response.get_json()

    assert response.status_code == 200
    assert data['status'] == 'success'
    assert data['result'] == expected_sum
    mock_add.assert_called_once_with(float(payload['number1']), float(payload['number2']))


@pytest.mark.parametrize("payload, expected_error_message_part", [
    ({}, "'number1' and 'number2' are required"),
    ({"number1": 10}, "'number2' is a required field"),
    ({"number2": 20}, "'number1' is a required field"),
    ({"number1": "abc", "number2": 20}, "Input 'number1' must be a valid number"),
    ({"number1": 10, "number2": "xyz"}, "Input 'number2' must be a valid number"),
    ({"number1": None, "number2": 20}, "Input 'number1' cannot be null"),
    ({"number1": 10, "number2": None}, "Input 'number2' cannot be null"),
    ({"number1": [1], "number2": 2}, "Input 'number1' must be a valid number"),
    ({"number1": 1, "number2": {"a": 1}}, "Input 'number2' must be a valid number"),
])
def test_add_numbers_bad_request_validation(client, mocker, payload, expected_error_message_part):
    mock_add = mocker.patch('src.api.routes.add_service.add')
    
    response = client.post('/add', json=payload)
    data = response.get_json()

    assert response.status_code == 400
    assert data['error'] == 'Invalid input'
    assert expected_error_message_part in data['message']
    mock_add.assert_not_called()


def test_add_numbers_bad_request_not_json(client, mocker):
    mock_add = mocker.patch('src.api.routes.add_service.add')
    
    response = client.post('/add', data='this is not json', content_type='text/plain')
    data = response.get_json()

    assert response.status_code == 400
    assert data['error'] == 'Invalid input'
    assert 'Failed to decode JSON' in data['message']
    mock_add.assert_not_called()
    

def test_add_numbers_internal_server_error(client, mocker):
    mocker.patch(
        'src.api.routes.add_service.add', 
        side_effect=Exception("Database connection failed")
    )
    
    payload = {"number1": 10, "number2": 20}
    response = client.post('/add', json=payload)
    data = response.get_json()

    assert response.status_code == 500
    assert data['error'] == 'Internal Server Error'
    assert data['message'] == 'An unexpected error occurred.'


def test_add_numbers_validation_internal_error(client, mocker):
    mocker.patch(
        'src.api.routes.validate_numbers', 
        side_effect=Exception("Validator exploded")
    )
    
    payload = {"number1": 10, "number2": 20}
    response = client.post('/add', json=payload)
    data = response.get_json()

    assert response.status_code == 500
    assert data['error'] == 'Internal Server Error'
    assert data['message'] == 'An unexpected error occurred.'


@pytest.mark.parametrize("method", ["GET", "PUT", "DELETE", "PATCH"])
def test_add_numbers_method_not_allowed(client, method):
    if method == "GET":
        response = client.get('/add')
    elif method == "PUT":
        response = client.put('/add', json={})
    elif method == "DELETE":
        response = client.delete('/add')
    elif method == "PATCH":
        response = client.patch('/add', json={})
        
    assert response.status_code == 405
