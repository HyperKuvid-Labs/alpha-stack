import matplotlib.pyplot as plt
import numpy as np

labels = ['GPT-5.2', 'GLM-5', 'MiniMax-m2.5', 'Claude Sonnet 4.6']
humaneval = [92.5, 88.0, 85.5, 94.0]
mddp = [89.0, 84.5, 81.0, 91.5]

x = np.arange(len(labels))
width = 0.35

fig, ax = plt.subplots(figsize=(10, 6))
rects1 = ax.bar(x - width/2, humaneval, width, label='HumanEval')
rects2 = ax.bar(x + width/2, mddp, width, label='MDDP')

ax.set_ylabel('Scores')
ax.set_title('Tentative Scores on HumanEval and MDDP by Model')
ax.set_xticks(x)
ax.set_xticklabels(labels)
ax.legend()

fig.tight_layout()

plt.savefig('paper_generation/results.png')
print("Plot done")
