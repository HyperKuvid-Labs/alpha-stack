import matplotlib.pyplot as plt
import numpy as np

# Data
models = ['gpt-5.2', 'glm-5', 'minimaxm2.5', 'claude sonnet 4.6']
humaneval_scores = [95.2, 88.5, 90.1, 94.8]
mddp_scores = [92.1, 85.3, 87.6, 91.5]

x = np.arange(len(models))  # the label locations
width = 0.35  # the width of the bars

fig, ax = plt.subplots(figsize=(10, 6))
rects1 = ax.bar(x - width/2, humaneval_scores, width, label='HumanEval', color='#4A90E2')
rects2 = ax.bar(x + width/2, mddp_scores, width, label='MDDP', color='#E74C3C')

# Add some text for labels, title and custom x-axis tick labels, etc.
ax.set_ylabel('Scores')
ax.set_title('Performance on HumanEval and MDDP benchmarks')
ax.set_xticks(x)
ax.set_xticklabels(models)
ax.legend()

# ax.bar_label(rects1, padding=3)
# ax.bar_label(rects2, padding=3)

fig.tight_layout()

plt.savefig('results.png')
print("results.png generated successfully.")
