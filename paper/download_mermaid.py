import base64
import requests
import sys
import os

def generate_mermaid_image(mmd_path, output_path):
    with open(mmd_path, 'r') as f:
        mermaid_code = f.read()

    graphbytes = mermaid_code.encode("utf8")
    base64_bytes = base64.b64encode(graphbytes)
    base64_string = base64_bytes.decode("ascii")

    url = "https://mermaid.ink/img/" + base64_string

    print(f"Downloading from {url}")
    response = requests.get(url)
    if response.status_code == 200:
        with open(output_path, 'wb') as f:
            f.write(response.content)
        print(f"Successfully downloaded mermaid image to {output_path}")
    else:
        print(f"Failed to download image. Status code: {response.status_code}")
        print(response.text)
        sys.exit(1)

if __name__ == "__main__":
    generate_mermaid_image('paper/architecture.mmd', 'paper/architecture.png')
