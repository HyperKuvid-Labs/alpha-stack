import matplotlib.pyplot as plt
import numpy as np

models = ['gpt-5.2', 'glm-5', 'minimaxm2.5', 'claude sonnet 4.6']
humaneval_scores = [92.5, 88.0, 85.5, 94.0]
mddp_scores = [89.0, 84.5, 82.0, 91.5]

x = np.arange(len(models))
width = 0.35

fig, ax = plt.subplots(figsize=(10, 6))
rects1 = ax.bar(x - width/2, humaneval_scores, width, label='HumanEval')
rects2 = ax.bar(x + width/2, mddp_scores, width, label='MDDP')

ax.set_ylabel('Scores (%)')
ax.set_title('Performance Comparison on HumanEval and MDDP')
ax.set_xticks(x)
ax.set_xticklabels(models)
ax.legend()
ax.set_ylim(0, 100)

for rect in rects1 + rects2:
    height = rect.get_height()
    ax.annotate(f'{height:.1f}',
                xy=(rect.get_x() + rect.get_width() / 2, height),
                xytext=(0, 3),  # 3 points vertical offset
                textcoords="offset points",
                ha='center', va='bottom')

plt.tight_layout()
plt.savefig('paper_generation/results.png')
print("Results graph generated successfully.")
