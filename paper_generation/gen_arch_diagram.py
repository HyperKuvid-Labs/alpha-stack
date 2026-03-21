import base64
import requests
import re
import os

def generate_architecture_diagram():
    # Read ARCHITECTURE.md
    with open('../ARCHITECTURE.md', 'r') as f:
        content = f.read()

    # Extract mermaid code
    match = re.search(r'```mermaid\n(.*?)```', content, re.DOTALL)
    if not match:
        print("Mermaid diagram not found in ARCHITECTURE.md")
        return

    mermaid_code = match.group(1).strip()

    # URL safe base64 encode without padding
    graph_base64 = base64.urlsafe_b64encode(mermaid_code.encode('utf-8')).decode('utf-8').rstrip('=')

    url = f"https://mermaid.ink/img/{graph_base64}"

    print(f"Fetching diagram from {url}")
    response = requests.get(url)

    if response.status_code == 200:
        with open('architecture.png', 'wb') as f:
            f.write(response.content)
        print("Successfully generated architecture.png")
    else:
        print(f"Failed to generate diagram. Status code: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    generate_architecture_diagram()
