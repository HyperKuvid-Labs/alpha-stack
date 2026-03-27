import base64
import requests
import matplotlib.pyplot as plt
import numpy as np
import os

def generate_mermaid_diagram():
    # Mermaid code from ARCHITECTURE.md
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

    # encode using urlsafe base64 without padding as per memory
    encoded_code = base64.urlsafe_b64encode(mermaid_code.encode('utf-8')).decode('utf-8').rstrip('=')

    url = f"https://mermaid.ink/img/{encoded_code}"
    print(f"Fetching diagram from {url}")

    response = requests.get(url)
    if response.status_code == 200:
        with open("paper_generation/architecture.png", "wb") as f:
            f.write(response.content)
        print("Successfully downloaded architecture.png")
    else:
        print(f"Failed to fetch diagram: {response.status_code}")
        print(response.text)

def generate_results_chart():
    # Dummy results for HumanEval and MDDP
    models = ['gpt-5.2', 'glm-5', 'minimaxm2.5', 'claude sonnet 4.6']
    humaneval_scores = [92.4, 88.5, 85.2, 90.1]
    mddp_scores = [85.6, 79.2, 76.5, 83.4]

    x = np.arange(len(models))
    width = 0.35

    fig, ax = plt.subplots(figsize=(10, 6))
    rects1 = ax.bar(x - width/2, humaneval_scores, width, label='HumanEval')
    rects2 = ax.bar(x + width/2, mddp_scores, width, label='MDDP')

    ax.set_ylabel('Scores (%)')
    ax.set_title('Model Performance on HumanEval and MDDP Benchmarks')
    ax.set_xticks(x)
    ax.set_xticklabels(models)
    ax.legend()
    ax.set_ylim([0, 100])

    # Add labels on top
    def autolabel(rects):
        for rect in rects:
            height = rect.get_height()
            ax.annotate(f'{height:.1f}',
                        xy=(rect.get_x() + rect.get_width() / 2, height),
                        xytext=(0, 3),  # 3 points vertical offset
                        textcoords="offset points",
                        ha='center', va='bottom')

    autolabel(rects1)
    autolabel(rects2)

    fig.tight_layout()
    plt.savefig('paper_generation/results_chart.png', dpi=300)
    print("Successfully generated results_chart.png")

if __name__ == "__main__":
    generate_mermaid_diagram()
    generate_results_chart()
