import matplotlib.pyplot as plt
import numpy as np

# Data
models = ['GPT-5.2', 'Claude Sonnet 4.6', 'GLM-5', 'MinimaxM2.5']
humaneval_scores = [92.5, 88.4, 85.1, 82.3]
mddp_scores = [88.7, 85.2, 80.5, 78.9]

x = np.arange(len(models))
width = 0.35

fig, ax = plt.subplots(figsize=(10, 6))
rects1 = ax.bar(x - width/2, humaneval_scores, width, label='HumanEval (Pass@1 %)')
rects2 = ax.bar(x + width/2, mddp_scores, width, label='MDDP Score')

# Add some text for labels, title and custom x-axis tick labels, etc.
ax.set_ylabel('Score')
ax.set_title('Performance Comparison on HumanEval and MDDP')
ax.set_xticks(x)
ax.set_xticklabels(models)
ax.legend()

# Add value labels
def autolabel(rects):
    """Attach a text label above each bar in *rects*, displaying its height."""
    for rect in rects:
        height = rect.get_height()
        ax.annotate('{}'.format(height),
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 3),  # 3 points vertical offset
                    textcoords="offset points",
                    ha='center', va='bottom')

autolabel(rects1)
autolabel(rects2)

fig.tight_layout()

plt.savefig('results.png')
print("Graph saved to results.png")
