import matplotlib.pyplot as plt
import numpy as np
import os

models = ['GPT-5.2', 'GLM-5', 'MiniMax M2.5', 'Claude Sonnet 4.6']
# Tentative dummy data based on human eval / mbpp performance estimates
humaneval_scores = [92.5, 88.3, 85.1, 91.0]
mbpp_scores = [94.0, 89.5, 87.2, 93.1]

x = np.arange(len(models))
width = 0.35

fig, ax = plt.subplots(figsize=(10, 6))
rects1 = ax.bar(x - width/2, humaneval_scores, width, label='HumanEval')
rects2 = ax.bar(x + width/2, mbpp_scores, width, label='MBPP')

ax.set_ylabel('Scores (%)')
ax.set_title('Model Performance on Code Generation Benchmarks')
ax.set_xticks(x)
ax.set_xticklabels(models)
ax.legend()
ax.set_ylim([70, 100])

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

output_path = os.path.join(os.path.dirname(__file__), "results_graph.png")
plt.savefig(output_path)
print(f"Results graph saved to {output_path}")
