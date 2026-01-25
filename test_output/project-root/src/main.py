from flask import Flask
from .config.settings import Config
from .api.routes import api_bp

app = Flask(__name__)
app.config.from_object(Config)
app.register_blueprint(api_bp)

def run():
    app.run()
