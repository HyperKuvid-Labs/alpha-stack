import matplotlib.pyplot as plt
import numpy as np

def generate_graph():
    models = ['gpt-5.2', 'glm-5', 'minimaxm2.5', 'claude sonnet 4.6']
    humaneval_scores = [95.2, 92.1, 89.5, 96.8]
    mddp_scores = [91.4, 88.3, 85.6, 93.2]

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

    ax.set_ylim(80, 100)

    fig.tight_layout()
    plt.savefig('paper_generation/results_graph.png', dpi=300)

if __name__ == '__main__':
    generate_graph()
