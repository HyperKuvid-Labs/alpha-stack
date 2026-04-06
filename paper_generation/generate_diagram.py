import base64
import requests
import sys

def main():
    try:
        with open('paper_generation/mermaid_code.txt', 'r') as f:
            code = f.read().strip()
    except FileNotFoundError:
        print("Mermaid code file not found.")
        sys.exit(1)

    # Encode code using urlsafe base64 without padding as requested
    b64 = base64.urlsafe_b64encode(code.encode('utf-8')).decode('utf-8').rstrip('=')

    url = f"https://mermaid.ink/img/{b64}"

    response = requests.get(url)
    if response.status_code == 200:
        with open('paper_generation/architecture.png', 'wb') as f:
            f.write(response.content)
        print("Diagram successfully generated.")
    else:
        print(f"Failed to generate diagram. Status code: {response.status_code}")
        sys.exit(1)

if __name__ == "__main__":
    main()