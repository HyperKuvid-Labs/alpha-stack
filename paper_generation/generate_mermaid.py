import base64
import requests

def generate_mermaid_image(mermaid_code, output_path):
    # Encode the mermaid code to urlsafe base64 without padding (per memory instructions)
    encoded = base64.urlsafe_b64encode(mermaid_code.encode('utf-8')).decode('utf-8').rstrip('=')
    url = f"https://mermaid.ink/img/{encoded}"

    response = requests.get(url)
    if response.status_code == 200:
        with open(output_path, 'wb') as f:
            f.write(response.content)
        print(f"Successfully generated {output_path}")
    else:
        print(f"Failed to generate image. Status code: {response.status_code}")
        print(response.text)

mermaid_code = """graph TD
    A[User Prompt] --> B(Phase 1: Blueprint)
    B --> C(Phase 2: Code Generation)
    C --> D(Phase 3: Dockerfile Gen)
    D --> E(Phase 4: Dep Analysis)
    E --> F(Phase 5: Dep Files)
    F --> G(Phase 6: Dep Resolution)
    G --> H(Phase 7: Docker Testing Pipeline)
    H --> I{Tests Pass?}
    I -- Yes --> J[Done]
    I -- No --> K[Planner Agent Loop]
    K --> L[Tools / Correction]
    L --> H
"""

generate_mermaid_image(mermaid_code, 'paper_generation/architecture.png')
