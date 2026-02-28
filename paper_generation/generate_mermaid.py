import os
import requests
import base64

def generate_mermaid_diagram():
    mermaid_code = """
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

    style A fill:#4A90E2,stroke:#2E5C8A,stroke-width:2px,color:#fff
    style B fill:#9B59B6,stroke:#6C3483,stroke-width:2px,color:#fff
    style C fill:#E67E22,stroke:#A04000,stroke-width:2px,color:#fff
    style D fill:#3498DB,stroke:#1F618D,stroke-width:2px,color:#fff
    style E fill:#1ABC9C,stroke:#117A65,stroke-width:2px,color:#fff
    style F fill:#E74C3C,stroke:#922B21,stroke-width:2px,color:#fff
    style L fill:#27AE60,stroke:#186A3B,stroke-width:2px,color:#fff
    """

    # Encode the Mermaid code in base64
    b64_str = base64.urlsafe_b64encode(mermaid_code.encode('utf-8')).decode('utf-8')
    url = f"https://mermaid.ink/img/{b64_str}"

    response = requests.get(url)
    if response.status_code == 200:
        with open('paper_generation/architecture_diagram.png', 'wb') as f:
            f.write(response.content)
        print("Mermaid diagram generated successfully.")
    else:
        print(f"Failed to generate diagram. Status code: {response.status_code}")

if __name__ == '__main__':
    generate_mermaid_diagram()
