import base64
import requests
import matplotlib.pyplot as plt
import numpy as np
import os

def generate_architecture_diagram():
    mermaid_code = """flowchart TD
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
    H -- Yes --> J["✅ PROJECT COMPLETE"]"""

    # URL safe base64 encoding without padding
    encoded_code = base64.urlsafe_b64encode(mermaid_code.encode('utf-8')).decode('utf-8').rstrip('=')
    url = f"https://mermaid.ink/img/{encoded_code}"

    response = requests.get(url)
    if response.status_code == 200:
        with open('paper_generation/architecture.png', 'wb') as f:
            f.write(response.content)
        print("Successfully generated architecture.png")
    else:
        print(f"Failed to generate architecture diagram. Status code: {response.status_code}")

def generate_results_chart():
    models = ['GPT-5.2', 'GLM-5', 'MiniMax-2.5', 'Claude 4.6']
    humaneval_scores = [92.5, 88.0, 85.5, 94.0] # Dummy values
    mddp_scores = [85.0, 81.5, 78.0, 87.5] # Dummy values

    x = np.arange(len(models))
    width = 0.35

    fig, ax = plt.subplots(figsize=(10, 6))
    rects1 = ax.bar(x - width/2, humaneval_scores, width, label='HumanEval')
    rects2 = ax.bar(x + width/2, mddp_scores, width, label='MDDP')

    ax.set_ylabel('Scores (%)')
    ax.set_title('Model Performance on HumanEval and MDDP')
    ax.set_xticks(x)
    ax.set_xticklabels(models)
    ax.legend()

    ax.bar_label(rects1, padding=3)
    ax.bar_label(rects2, padding=3)

    fig.tight_layout()
    plt.savefig('paper_generation/results.png')
    print("Successfully generated results.png")

if __name__ == '__main__':
    generate_architecture_diagram()
    generate_results_chart()
