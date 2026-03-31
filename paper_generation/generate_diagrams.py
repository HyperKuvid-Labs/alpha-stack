import base64
import requests
import matplotlib.pyplot as plt
import numpy as np

# 1. Generate Architecture Diagram using Mermaid
mermaid_code = """graph LR
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
    style L fill:#27AE60,stroke:#186A3B,stroke-width:2px,color:#fff"""

encoded_mermaid = base64.urlsafe_b64encode(mermaid_code.encode('utf-8')).decode('utf-8').rstrip('=')
url = f"https://mermaid.ink/img/{encoded_mermaid}"

response = requests.get(url)
if response.status_code == 200:
    with open("paper_generation/architecture.png", "wb") as f:
        f.write(response.content)
    print("Architecture diagram saved as architecture.png")
else:
    print(f"Failed to generate architecture diagram. Status code: {response.status_code}")


# 2. Generate Results Graph using Matplotlib
labels = ['HumanEval', 'MDDP']
gpt52_means = [88.5, 82.1]
glm5_means = [84.2, 78.5]
minimaxm25_means = [81.0, 75.3]
claude_sonnet46_means = [89.1, 84.4]

x = np.arange(len(labels))  # the label locations
width = 0.2  # the width of the bars

fig, ax = plt.subplots(figsize=(8, 6))
rects1 = ax.bar(x - width*1.5, gpt52_means, width, label='GPT-5.2')
rects2 = ax.bar(x - width*0.5, glm5_means, width, label='GLM-5')
rects3 = ax.bar(x + width*0.5, minimaxm25_means, width, label='MiniMax M2.5')
rects4 = ax.bar(x + width*1.5, claude_sonnet46_means, width, label='Claude Sonnet 4.6')

# Add some text for labels, title and custom x-axis tick labels, etc.
ax.set_ylabel('Success Rate (%)')
ax.set_title('Evaluation Results on HumanEval and MDDP')
ax.set_xticks(x)
ax.set_xticklabels(labels)
ax.set_ylim(0, 100)
ax.legend()

def autolabel(rects):
    """Attach a text label above each bar in *rects*, displaying its height."""
    for rect in rects:
        height = rect.get_height()
        ax.annotate(f'{height}',
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 3),  # 3 points vertical offset
                    textcoords="offset points",
                    ha='center', va='bottom', fontsize=8)

autolabel(rects1)
autolabel(rects2)
autolabel(rects3)
autolabel(rects4)

fig.tight_layout()

plt.savefig('paper_generation/results.png', dpi=300)
print("Results graph saved as results.png")
