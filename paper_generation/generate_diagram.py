import base64
import requests

graph = """
graph LR
    A[Natural Language Input] --> B[AI Analysis & Blueprint]
    B --> C[Multi-File Code Generation]
    C --> D[Dependency Resolution]
    D --> E[Docker Configuration]
    E --> F[Build Validation]
    F --> G{Build Success?}
    G -->|No| H[Planning Agent]
    H --> I[Correction Agent]
    I --> F
    G -->|Yes| J[Test Execution]
    J --> K{Tests Pass?}
    K -->|No| H
    K -->|Yes| L[Production-Ready Project]
"""

graphbytes = graph.encode("utf-8")
base64_bytes = base64.b64encode(graphbytes)
base64_string = base64_bytes.decode("utf-8")
url = f"https://mermaid.ink/img/{base64_string}"

response = requests.get(url)
if response.status_code == 200:
    with open("paper_generation/architecture.png", "wb") as f:
        f.write(response.content)
    print("Architecture diagram generated successfully.")
else:
    print(f"Failed to generate diagram: {response.status_code}")
