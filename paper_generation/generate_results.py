import matplotlib.pyplot as plt
import numpy as np

# Data
models = ['GPT-5.2', 'GLM-5', 'MiniMax-m2.5', 'Claude Sonnet 4.6']
humaneval_scores = [92.5, 88.0, 89.5, 94.2]
mddp_scores = [85.0, 78.5, 82.0, 89.1]

x = np.arange(len(models))  # the label locations
width = 0.35  # the width of the bars

fig, ax = plt.subplots(figsize=(10, 6))
rects1 = ax.bar(x - width/2, humaneval_scores, width, label='HumanEval', color='#4A90E2')
rects2 = ax.bar(x + width/2, mddp_scores, width, label='MDDP', color='#E74C3C')

# Add some text for labels, title and custom x-axis tick labels, etc.
ax.set_ylabel('Scores (%)', fontsize=12)
ax.set_title('Performance Comparison on HumanEval and MDDP Benchmarks', fontsize=14)
ax.set_xticks(x)
ax.set_xticklabels(models, fontsize=11)
ax.legend()

# Auto-label bars
def autolabel(rects):
    """Attach a text label above each bar in *rects*, displaying its height."""
    for rect in rects:
        height = rect.get_height()
        ax.annotate(f'{height}%',
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 3),  # 3 points vertical offset
                    textcoords="offset points",
                    ha='center', va='bottom', fontsize=10)

autolabel(rects1)
autolabel(rects2)

fig.tight_layout()

# Save the plot
plt.savefig('paper_generation/results.png', dpi=300)
print("Successfully generated results.png")
