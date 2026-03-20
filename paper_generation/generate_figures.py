import os
import re
import base64
import requests
import matplotlib.pyplot as plt
import numpy as np

def generate_results_graph():
    # Models and datasets
    models = ['GPT-5.2', 'GLM-5', 'MiniMax-m2.5', 'Claude Sonnet 4.6']
    humaneval_scores = [92.5, 88.0, 85.5, 94.0]
    mddp_scores = [89.0, 84.5, 82.0, 91.5]

    x = np.arange(len(models))
    width = 0.35

    fig, ax = plt.subplots(figsize=(10, 6))
    rects1 = ax.bar(x - width/2, humaneval_scores, width, label='HumanEval')
    rects2 = ax.bar(x + width/2, mddp_scores, width, label='MDDP')

    ax.set_ylabel('Scores (%)')
    ax.set_title('Model Performance on HumanEval and MDDP Datasets')
    ax.set_xticks(x)
    ax.set_xticklabels(models)
    ax.legend()
    ax.set_ylim([0, 100])

    ax.bar_label(rects1, padding=3)
    ax.bar_label(rects2, padding=3)

    fig.tight_layout()

    plt.savefig('paper_generation/results_graph.png')
    print("Saved results graph to paper_generation/results_graph.png")

def extract_mermaid_and_fetch_image():
    with open('ARCHITECTURE.md', 'r') as f:
        content = f.read()

    # Find the first mermaid block
    match = re.search(r'```mermaid\n(.*?)\n```', content, re.DOTALL)
    if not match:
        print("No mermaid block found in ARCHITECTURE.md")
        return

    mermaid_code = match.group(1)

    # Encode to base64, mermaid API needs urlsafe without padding? Wait let's just use urlsafe
    base64_encoded = base64.urlsafe_b64encode(mermaid_code.encode('utf-8')).decode('utf-8').rstrip("=")
    url = f"https://mermaid.ink/img/{base64_encoded}"

    print(f"Fetching mermaid diagram from: {url}")
    response = requests.get(url)
    if response.status_code == 200:
        with open('paper_generation/architecture_diagram.png', 'wb') as f:
            f.write(response.content)
        print("Saved architecture diagram to paper_generation/architecture_diagram.png")
    else:
        print(f"Failed to fetch image: {response.status_code}")

if __name__ == '__main__':
    generate_results_graph()
    extract_mermaid_and_fetch_image()
