import matplotlib.pyplot as plt
import numpy as np

# Data
models = ['gpt-5.2', 'glm-5', 'minimaxm2.5', 'claude sonnet 4.6']
humaneval_scores = [88.5, 85.2, 82.1, 92.0]
mddp_scores = [76.4, 72.8, 70.5, 81.3]

x = np.arange(len(models))
width = 0.35

fig, ax = plt.subplots(figsize=(10, 6))
rects1 = ax.bar(x - width/2, humaneval_scores, width, label='HumanEval')
rects2 = ax.bar(x + width/2, mddp_scores, width, label='MDDP')

ax.set_ylabel('Scores')
ax.set_title('Model Performance on HumanEval and MDDP')
ax.set_xticks(x)
ax.set_xticklabels(models)
ax.legend()

# Add labels on top of bars
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
plt.savefig('paper_generation/results.png', dpi=300)
print("Successfully generated paper_generation/results.png")
