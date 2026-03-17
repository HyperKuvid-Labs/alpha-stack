import matplotlib.pyplot as plt
import numpy as np

def generate_results_graph():
    models = ['gpt-5.2', 'glm-5', 'minimaxm2.5', 'claude sonnet 4.6']

    # Dummy data
    humaneval_scores = [85.2, 82.1, 79.5, 88.4]
    mddp_scores = [76.5, 71.2, 68.9, 81.3]

    x = np.arange(len(models))
    width = 0.35

    fig, ax = plt.subplots(figsize=(10, 6))
    rects1 = ax.bar(x - width/2, humaneval_scores, width, label='HumanEval')
    rects2 = ax.bar(x + width/2, mddp_scores, width, label='MDDP')

    ax.set_ylabel('Success Rate (%)')
    ax.set_title('Model Performance on Code Generation Benchmarks')
    ax.set_xticks(x)
    ax.set_xticklabels(models)
    ax.legend()

    ax.bar_label(rects1, padding=3, fmt='%.1f')
    ax.bar_label(rects2, padding=3, fmt='%.1f')

    fig.tight_layout()
    plt.savefig('paper_generation/results.png', dpi=300)
    print("Successfully generated results graph.")

if __name__ == '__main__':
    generate_results_graph()
