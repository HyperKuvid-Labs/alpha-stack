import matplotlib.pyplot as plt
import numpy as np
import os

def generate_results():
    # Data
    models = ['GPT-5.2', 'GLM-5', 'MiniMax-m2.5', 'Claude Sonnet 4.6']
    humaneval_scores = [92.5, 88.0, 85.5, 91.0]
    mddp_scores = [89.0, 84.5, 82.0, 88.5]

    x = np.arange(len(models))  # the label locations
    width = 0.35  # the width of the bars

    fig, ax = plt.subplots(figsize=(10, 6))
    rects1 = ax.bar(x - width/2, humaneval_scores, width, label='HumanEval', color='#4A90E2')
    rects2 = ax.bar(x + width/2, mddp_scores, width, label='MDDP', color='#E67E22')

    # Add some text for labels, title and custom x-axis tick labels, etc.
    ax.set_ylabel('Scores (%)')
    ax.set_title('Model Performance on HumanEval and MDDP Benchmarks')
    ax.set_xticks(x)
    ax.set_xticklabels(models)
    ax.legend()
    ax.set_ylim(0, 100)

    ax.bar_label(rects1, padding=3, fmt='%.1f')
    ax.bar_label(rects2, padding=3, fmt='%.1f')

    fig.tight_layout()

    os.makedirs('paper_generation', exist_ok=True)
    plt.savefig('paper_generation/results.png', dpi=300)
    print("Results graph generated successfully at paper_generation/results.png")

if __name__ == "__main__":
    generate_results()
