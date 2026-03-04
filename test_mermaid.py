import base64
import requests

graph_def = """graph LR
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
    K -->|Yes| L[Production-Ready Project]"""

encoded_graph = base64.b64encode(graph_def.encode('utf-8')).decode('utf-8')
url = f"https://mermaid.ink/img/{encoded_graph}"

response = requests.get(url)
print(response.status_code)
if response.status_code == 200:
    with open("paper_generation/architecture.png", "wb") as f:
        f.write(response.content)
    print("Success")
else:
    print(response.text)
