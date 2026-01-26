import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'a-very-secret-key-for-dev-only'
    DEBUG = os.environ.get('DEBUG', 'False') == 'True'
