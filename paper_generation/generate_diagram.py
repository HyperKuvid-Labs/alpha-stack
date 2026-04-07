import urllib.request
import base64
import json

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

graphbytes = graph.encode("utf8")
base64_bytes = base64.urlsafe_b64encode(graphbytes)
base64_string = base64_bytes.decode("ascii").rstrip("=")

url = f"https://mermaid.ink/img/{base64_string}"

req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req) as response, open("paper_generation/architecture.png", 'wb') as out_file:
    data = response.read()
    out_file.write(data)
print("Done")
