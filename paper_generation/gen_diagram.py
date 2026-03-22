import base64
import requests

def generate_mermaid_diagram():
    # The Mermaid code for the system architecture
    mermaid_code = """
flowchart TD
    A["CLI / User Prompt"] --> B["Generator Pipeline"]
    B --> B1["Phase 1: Software Blueprint"]
    B1 --> B2["Phase 2: File Generation"]
    B2 --> B3["Phase 3: Dockerfile Generation"]
    B3 --> B4["Phase 4: Dependency Analysis"]
    B4 --> B5["Phase 5: Dep File Generation"]
    B5 --> B6["Phase 6: Dep Resolution"]
    B6 --> B7["Phase 7: Docker Testing Pipeline"]
    B7 --> C["AI Planner Agent Loop"]
    C --> D["docker_test Tool"]
    D --> E["DockerExecutor"]
    E --> F{{"Build Success?"}}
    F -- No --> G["Return error_log to Agent"]
    G --> C
    F -- Yes --> H{{"Tests Pass?"}}
    H -- No --> I["Return error_log to Agent"]
    I --> C
    H -- Yes --> J["✅ PROJECT COMPLETE"]
    """

    encoded = base64.urlsafe_b64encode(mermaid_code.encode('utf-8')).decode('utf-8').rstrip('=')

    url = f"https://mermaid.ink/img/{encoded}"

    response = requests.get(url)

    if response.status_code == 200:
        with open('architecture.png', 'wb') as f:
            f.write(response.content)
        print("Mermaid diagram saved successfully.")
    else:
        print(f"Failed to generate diagram: {response.status_code} {response.text}")

if __name__ == "__main__":
    generate_mermaid_diagram()
