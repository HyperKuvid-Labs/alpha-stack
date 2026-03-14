import os
import re
import base64
import requests

def extract_mermaid(readme_path):
    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()
    match = re.search(r"```mermaid\n(.*?)\n```", content, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None

def generate_diagram(mermaid_code, output_path):
    encoded_graph = base64.b64encode(mermaid_code.encode("utf-8")).decode("utf-8")
    url = f"https://mermaid.ink/img/{encoded_graph}"
    print(f"Fetching diagram from: {url}")
    response = requests.get(url)
    if response.status_code == 200:
        with open(output_path, "wb") as f:
            f.write(response.content)
        print(f"Successfully saved architecture diagram to {output_path}")
    else:
        print(f"Failed to fetch diagram. Status code: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    readme_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "README.md")
    output_path = os.path.join(os.path.dirname(__file__), "architecture.png")

    mermaid_code = extract_mermaid(readme_path)
    if mermaid_code:
        generate_diagram(mermaid_code, output_path)
    else:
        print("Mermaid diagram not found in README.md")
