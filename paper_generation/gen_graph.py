import matplotlib.pyplot as plt
import numpy as np

def generate_results_graph():
    # Models to evaluate
    models = ['gpt-5.2', 'glm-5', 'minimaxm2.5', 'claude sonnet 4.6']

    # Tentative pass@1 scores (percentages)
    mddp_scores = [60.5, 52.3, 48.7, 65.2]
    humaneval_scores = [88.2, 85.1, 80.4, 92.0]

    x = np.arange(len(models))  # the label locations
    width = 0.35  # the width of the bars

    fig, ax = plt.subplots(figsize=(10, 6))

    # Create grouped bar chart
    rects1 = ax.bar(x - width/2, mddp_scores, width, label='MDDP', color='#3498db')
    rects2 = ax.bar(x + width/2, humaneval_scores, width, label='HumanEval', color='#2ecc71')

    # Add labels, title, and custom x-axis tick labels
    ax.set_ylabel('Pass@1 Score (%)', fontsize=12)
    ax.set_title('Performance on MDDP and HumanEval Benchmarks', fontsize=14)
    ax.set_xticks(x)
    ax.set_xticklabels(models, fontsize=11)
    ax.legend(fontsize=11)

    # Auto-label the bars
    def autolabel(rects):
        """Attach a text label above each bar in *rects*, displaying its height."""
        for rect in rects:
            height = rect.get_height()
            ax.annotate(f'{height}%',
                        xy=(rect.get_x() + rect.get_width() / 2, height),
                        xytext=(0, 3),  # 3 points vertical offset
                        textcoords="offset points",
                        ha='center', va='bottom')

    autolabel(rects1)
    autolabel(rects2)

    fig.tight_layout()
    plt.savefig('results_graph.png', dpi=300)
    print("Results graph saved successfully.")

if __name__ == "__main__":
    generate_results_graph()
