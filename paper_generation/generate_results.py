import matplotlib.pyplot as plt
import numpy as np

def generate_results_graph():
    # Models
    models = ['gpt-5.2', 'glm-5', 'minimaxm2.5', 'claude sonnet 4.6']

    # Dummy data
    humaneval_scores = [94.5, 88.2, 85.0, 93.8]
    mddp_scores = [91.2, 84.5, 82.1, 90.5]

    x = np.arange(len(models))
    width = 0.35  # the width of the bars

    fig, ax = plt.subplots(figsize=(10, 6))
    rects1 = ax.bar(x - width/2, humaneval_scores, width, label='HumanEval')
    rects2 = ax.bar(x + width/2, mddp_scores, width, label='MDDP')

    # Add some text for labels, title and custom x-axis tick labels, etc.
    ax.set_ylabel('Scores (%)')
    ax.set_title('Performance by Model and Dataset')
    ax.set_xticks(x)
    ax.set_xticklabels(models)
    ax.legend()

    # Label with values
    ax.bar_label(rects1, padding=3)
    ax.bar_label(rects2, padding=3)

    fig.tight_layout()

    plt.savefig('paper_generation/results.png', dpi=300)
    print("Results graph successfully generated and saved to paper_generation/results.png")

if __name__ == '__main__':
    generate_results_graph()
