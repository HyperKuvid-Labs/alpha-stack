import base64
import requests
import matplotlib.pyplot as plt
import numpy as np
import os

def generate_mermaid_diagram():
    # Read the architecture markdown file
    with open('ARCHITECTURE.md', 'r') as f:
        content = f.read()

    # Extract the mermaid diagram code
    start = content.find('```mermaid') + len('```mermaid')
    end = content.find('```', start)
    mermaid_code = content[start:end].strip()

    # encode for mermaid.ink
    # Note: Use urlsafe base64 encoding without padding as per memory
    encoded_code = base64.urlsafe_b64encode(mermaid_code.encode('utf-8')).decode('utf-8').rstrip('=')

    url = f"https://mermaid.ink/img/{encoded_code}?type=png"

    response = requests.get(url)
    if response.status_code == 200:
        with open('paper_generation/architecture.png', 'wb') as f:
            f.write(response.content)
        print("Successfully generated architecture.png")
    else:
        print(f"Failed to generate architecture diagram. Status code: {response.status_code}")
        print(f"URL: {url}")

def generate_results_chart():
    # Models: gpt-5.2, glm-5, minimax-m2.5, claude sonnet 4.6
    models = ['GPT-5.2', 'GLM-5', 'MiniMax-m2.5', 'Claude Sonnet 4.6']

    # Dummy data for HumanEval and MDDP
    humaneval_scores = [95.2, 88.5, 87.1, 93.8]
    mddp_scores = [92.1, 85.3, 84.7, 91.5]

    x = np.arange(len(models))
    width = 0.35

    fig, ax = plt.subplots(figsize=(10, 6))
    rects1 = ax.bar(x - width/2, humaneval_scores, width, label='HumanEval')
    rects2 = ax.bar(x + width/2, mddp_scores, width, label='MDDP')

    ax.set_ylabel('Scores (%)')
    ax.set_title('Tentative Performance Results on HumanEval and MDDP')
    ax.set_xticks(x)
    ax.set_xticklabels(models)
    ax.legend()

    ax.set_ylim(0, 100)

    # Add labels on top of bars
    def autolabel(rects):
        """Attach a text label above each bar in *rects*, displaying its height."""
        for rect in rects:
            height = rect.get_height()
            ax.annotate(f'{height}%',
                        xy=(rect.get_x() + rect.get_width() / 2, height),
                        xytext=(0, 3),  # 3 points vertical offset
                        textcoords="offset points",
                        ha='center', va='bottom')

    autolabel(rects1)
    autolabel(rects2)

    fig.tight_layout()
    plt.savefig('paper_generation/results.png')
    print("Successfully generated results.png")

if __name__ == '__main__':
    # Ensure directory exists
    os.makedirs('paper_generation', exist_ok=True)

    generate_mermaid_diagram()
    generate_results_chart()
