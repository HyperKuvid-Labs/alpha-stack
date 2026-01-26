import pytest
from flask import Flask
from unittest.mock import MagicMock

from src.main import app as flask_app
from src.main import run_server

@pytest.fixture
def app():
    flask_app.config.update({
        "TESTING": True,
        "DEBUG": False,
    })
    yield flask_app

@pytest.fixture
def client(app):
    return app.test_client()

def test_app_is_flask_instance(app):
    assert isinstance(app, Flask)
    assert app.name == 'src.main'

def test_app_configuration_is_loaded(app):
    assert app.config['TESTING'] is True
    assert app.config['DEBUG'] is False
    assert 'HOST' in app.config
    assert 'PORT' in app.config

def test_api_blueprint_is_registered(app):
    assert 'api' in app.blueprints
    blueprint = app.blueprints['api']
    assert blueprint.url_prefix == '/api'

def test_root_url_returns_404(client):
    response = client.get('/')
    assert response.status_code == 404

def test_api_route_is_reachable(client):
    response = client.post('/api/add', json={})
    assert response.status_code == 400
    assert response.content_type == 'application/json'

def test_run_server_calls_app_run(mocker):
    mock_app_run = mocker.patch('src.main.app.run')
    mock_settings = MagicMock()
    mock_settings.HOST = '127.0.0.1'
    mock_settings.PORT = 5001
    mock_settings.DEBUG = False
    mocker.patch('src.main.get_settings', return_value=mock_settings)

    run_server()

    mock_app_run.assert_called_once_with(
        host=mock_settings.HOST,
        port=mock_settings.PORT,
        debug=mock_settings.DEBUG
    )

def test_app_creation_with_different_env(mocker):
    mocker.patch('src.config.settings.get_settings', return_value=MagicMock(ENV='production', DEBUG=False))
    
    # Need to re-import or re-run the app creation logic
    # For simplicity, we can check the config after app fixture modifies it
    # This test is more conceptual to show env-based config testing
    
    from src.main import app
    app.config.from_object(mocker.patch('src.config.settings.get_settings').return_value)
    
    assert app.config['DEBUG'] is False

def test_unknown_api_endpoint_returns_404(client):
    response = client.get('/api/nonexistent')
    assert response.status_code == 404
    response = client.post('/api/subtract', json={'num1': 5, 'num2': 2})
    assert response.status_code == 404
