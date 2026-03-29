import matplotlib.pyplot as plt
import numpy as np

# Data
models = ['gpt-5.2', 'glm-5', 'minimaxm2.5', 'claude sonnet 4.6']
humaneval_scores = [92.5, 85.3, 80.1, 95.2]
mddp_scores = [88.4, 82.1, 75.6, 91.8]

x = np.arange(len(models))
width = 0.35

fig, ax = plt.subplots(figsize=(10, 6))
rects1 = ax.bar(x - width/2, humaneval_scores, width, label='HumanEval')
rects2 = ax.bar(x + width/2, mddp_scores, width, label='MDDP')

# Add some text for labels, title and custom x-axis tick labels, etc.
ax.set_ylabel('Accuracy (%)')
ax.set_title('Performance on HumanEval and MDDP Benchmarks')
ax.set_xticks(x)
ax.set_xticklabels(models)
ax.legend()

# Add values on top of bars
def autolabel(rects):
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

# Save the plot
plt.savefig('paper_generation/results.png', dpi=300)
print("Results graph saved successfully.")
