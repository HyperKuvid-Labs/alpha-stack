import base64
import requests
import matplotlib.pyplot as plt
import numpy as np
import os

# Create paper_generation directory if it doesn't exist
os.makedirs("paper_generation", exist_ok=True)

# 1. Fetch Architecture Diagram from mermaid.ink
mermaid_diagram = """graph LR
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

# Encode mermaid string to base64
encoded_diagram = base64.b64encode(mermaid_diagram.encode('utf-8')).decode('utf-8')
url = f"https://mermaid.ink/img/{encoded_diagram}"

print(f"Fetching diagram from: {url}")
response = requests.get(url)
if response.status_code == 200:
    with open("paper_generation/architecture.png", "wb") as f:
        f.write(response.content)
    print("Successfully saved architecture.png")
else:
    print(f"Failed to fetch diagram: {response.status_code} - {response.text}")

# 2. Generate Results Graph using matplotlib
models = ['gpt-5.2', 'glm-5', 'minimaxm2.5', 'claude sonnet 4.6']
humaneval_scores = [92.4, 88.5, 85.1, 90.2]
mddp_scores = [85.6, 81.2, 79.5, 83.8]

x = np.arange(len(models))  # the label locations
width = 0.35  # the width of the bars

fig, ax = plt.subplots(figsize=(10, 6))
rects1 = ax.bar(x - width/2, humaneval_scores, width, label='HumanEval', color='#4A90E2')
rects2 = ax.bar(x + width/2, mddp_scores, width, label='MDDP', color='#E67E22')

# Add some text for labels, title and custom x-axis tick labels, etc.
ax.set_ylabel('Scores (%)')
ax.set_title('Performance of AlphaStack Multi-Agent Framework across Models')
ax.set_xticks(x)
ax.set_xticklabels(models)
ax.legend()

ax.bar_label(rects1, padding=3)
ax.bar_label(rects2, padding=3)

fig.tight_layout()

plt.savefig("paper_generation/results_graph.png", dpi=300)
print("Successfully saved results_graph.png")
