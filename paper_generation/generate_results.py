import os
import matplotlib.pyplot as plt
import numpy as np

def generate_results_graph(output_path):
    # Models to evaluate based on task description
    models = ['gpt-5.2', 'glm-5', 'minimaxm2.5', 'claude sonnet 4.6']

    # Dummy results for HumanEval and MDDP
    # (Since these are dummy results as requested, we invent realistic-looking scores)
    humaneval_scores = [95.2, 92.4, 91.8, 94.7]
    mddp_scores = [91.5, 88.3, 89.0, 92.1]

    # Set up the bar chart
    x = np.arange(len(models))
    width = 0.35  # width of the bars

    fig, ax = plt.subplots(figsize=(10, 6))

    rects1 = ax.bar(x - width/2, humaneval_scores, width, label='HumanEval', color='#4A90E2')
    rects2 = ax.bar(x + width/2, mddp_scores, width, label='MDDP', color='#E74C3C')

    # Add text for labels, title and custom x-axis tick labels, etc.
    ax.set_ylabel('Score (%)')
    ax.set_title('Model Performance on HumanEval and MDDP Benchmarks')
    ax.set_xticks(x)
    ax.set_xticklabels(models)
    ax.legend(loc='lower right')

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

    # Save the figure
    plt.savefig(output_path, dpi=300)
    print(f"Successfully saved results graph to {output_path}")

if __name__ == "__main__":
    output_path = os.path.join(os.path.dirname(__file__), "results.png")
    generate_results_graph(output_path)
