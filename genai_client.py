import os
from google import genai
from dotenv import load_dotenv

load_dotenv(dotenv_path='.env')

_client = None

def get_client():
    """Return a singleton Google AI client instance."""
    global _client
    if _client is None:
        _client = genai.Client()
    return _client
