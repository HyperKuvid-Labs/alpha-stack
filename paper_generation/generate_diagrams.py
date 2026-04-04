import base64
import requests
import matplotlib.pyplot as plt
import numpy as np
import os

# 1. Mermaid diagram
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

encoded = base64.urlsafe_b64encode(mermaid_code.encode('utf-8')).decode('utf-8').rstrip('=')
url = f"https://mermaid.ink/img/{encoded}"

response = requests.get(url)
if response.status_code == 200:
    with open("paper_generation/architecture.png", "wb") as f:
        f.write(response.content)
    print("Mermaid diagram saved.")
else:
    print(f"Failed to fetch diagram: {response.status_code}")

# 2. Results graph
models = ['GPT-5.2', 'GLM-5', 'MiniMax-m2.5', 'Claude Sonnet 4.6']
humaneval_scores = [92.5, 85.0, 81.2, 90.1]
mddp_scores = [88.0, 79.5, 75.0, 86.4]

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
ax.set_ylim(0, 100)

for p in ax.patches:
    ax.annotate(f'{p.get_height()}', (p.get_x() + p.get_width() / 2., p.get_height()), ha='center', va='center', xytext=(0, 5), textcoords='offset points')

plt.tight_layout()
plt.savefig('paper_generation/results_graph.png')
print("Results graph saved.")
