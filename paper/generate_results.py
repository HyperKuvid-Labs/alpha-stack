import matplotlib.pyplot as plt
import numpy as np
import os

def generate_results_chart():
    # Models and Benchmarks
    models = ['GPT-5.2', 'GLM-5', 'MiniMax M2.5', 'Claude Sonnet 4.6']
    benchmarks = ['HumanEval', 'MDDP']

    # Dummy Data (scores out of 100)
    # Making up some plausible numbers for "state of the art" models
    human_eval_scores = [92.5, 88.0, 85.5, 89.2]
    mddp_scores = [85.0, 78.5, 76.0, 82.3]

    x = np.arange(len(models))  # the label locations
    width = 0.35  # the width of the bars

    fig, ax = plt.subplots(figsize=(10, 6))
    rects1 = ax.bar(x - width/2, human_eval_scores, width, label='HumanEval', color='skyblue')
    rects2 = ax.bar(x + width/2, mddp_scores, width, label='MDDP', color='lightcoral')

    # Add some text for labels, title and custom x-axis tick labels, etc.
    ax.set_ylabel('Pass Rate (%)')
    ax.set_title('Model Performance on HumanEval and MDDP Benchmarks')
    ax.set_xticks(x)
    ax.set_xticklabels(models)
    ax.legend()

    ax.set_ylim(0, 100)

    # Label with value
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

    output_path = os.path.join(os.path.dirname(__file__), 'results.png')
    plt.savefig(output_path, dpi=300)
    print(f"Results chart saved to {output_path}")

if __name__ == '__main__':
    generate_results_chart()
