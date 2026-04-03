import matplotlib.pyplot as plt
import numpy as np

def generate_results_graph():
    models = ['GPT-5.2', 'GLM-5', 'MiniMax-m2.5', 'Claude 4.6']
    humaneval_scores = [92.5, 88.3, 85.1, 94.2]
    mddp_scores = [89.1, 84.5, 81.2, 91.8]

    x = np.arange(len(models))
    width = 0.35

    fig, ax = plt.subplots(figsize=(10, 6))
    rects1 = ax.bar(x - width/2, humaneval_scores, width, label='HumanEval', color='#4A90E2')
    rects2 = ax.bar(x + width/2, mddp_scores, width, label='MDDP', color='#E67E22')

    ax.set_ylabel('Scores (%)')
    ax.set_title('Performance Comparison on HumanEval and MDDP Benchmarks')
    ax.set_xticks(x)
    ax.set_xticklabels(models)
    ax.legend()

    ax.bar_label(rects1, padding=3)
    ax.bar_label(rects2, padding=3)

    fig.tight_layout()
    plt.savefig('paper_generation/results_graph.png')
    print("Results graph generated successfully!")

if __name__ == "__main__":
    generate_results_graph()
