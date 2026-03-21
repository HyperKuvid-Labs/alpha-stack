import matplotlib.pyplot as plt
import numpy as np

def generate_results_graph():
    # Data
    models = ['gpt-5.2', 'glm-5', 'minimaxm2.5', 'claude sonnet 4.6']
    humaneval_scores = [95.2, 88.5, 91.0, 96.8]
    mddp_scores = [92.1, 84.3, 89.5, 94.2]

    x = np.arange(len(models))  # the label locations
    width = 0.35  # the width of the bars

    fig, ax = plt.subplots(figsize=(10, 6))
    rects1 = ax.bar(x - width/2, humaneval_scores, width, label='HumanEval', color='#4C72B0')
    rects2 = ax.bar(x + width/2, mddp_scores, width, label='MDDP', color='#DD8452')

    # Add some text for labels, title and custom x-axis tick labels, etc.
    ax.set_ylabel('Score (%)')
    ax.set_title('Model Performance on HumanEval and MDDP Benchmarks')
    ax.set_xticks(x)
    ax.set_xticklabels(models)
    ax.legend()

    ax.set_ylim(0, 100)

    # Add value labels on top of bars
    def autolabel(rects):
        """Attach a text label above each bar in *rects*, displaying its height."""
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

    # Save the plot
    plt.savefig('results.png', dpi=300, bbox_inches='tight')
    print("Successfully generated results.png")

if __name__ == "__main__":
    generate_results_graph()
