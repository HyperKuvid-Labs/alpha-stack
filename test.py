from google.genai import types
import re
import json
import os
import time
from src.utils.helpers import get_client, retry_api_call, get_system_info, clean_agent_output, GENERATABLE_FILES, GENERATABLE_FILENAMES, MODEL_NAME_FLASH
client = get_client()
chat = retry_api_call(
        client.chats.create,
        model='models/gemini-2.5-pro',
        config=types.GenerateContentConfig(systemInstruction="great the user")
    )
response = retry_api_call(chat.send_message, "vanakam da mapula")
print("hi") 