import matplotlib.pyplot as plt
import numpy as np

def generate_results():
    models = ['GPT-5.2', 'Claude Sonnet 4.6', 'GLM-5', 'MiniMaxM2.5']
    humaneval_scores = [92.5, 89.2, 85.8, 83.4]
    mddp_scores = [88.7, 86.5, 82.1, 79.9]

    x = np.arange(len(models))
    width = 0.35

    fig, ax = plt.subplots(figsize=(10, 6))
    rects1 = ax.bar(x - width/2, humaneval_scores, width, label='HumanEval', color='#4A90E2')
    rects2 = ax.bar(x + width/2, mddp_scores, width, label='MDDP', color='#27AE60')

    ax.set_ylabel('Pass Rate (%)')
    ax.set_title('Performance Comparison on Code Generation Benchmarks')
    ax.set_xticks(x)
    ax.set_xticklabels(models)
    ax.legend()
    ax.set_ylim(0, 100)

    def autolabel(rects):
        for rect in rects:
            height = rect.get_height()
            ax.annotate('{}'.format(height),
                        xy=(rect.get_x() + rect.get_width() / 2, height),
                        xytext=(0, 3),  # 3 points vertical offset
                        textcoords="offset points",
                        ha='center', va='bottom')

    autolabel(rects1)
    autolabel(rects2)

    fig.tight_layout()

    plt.savefig('paper/results.png')
    print("Results graph saved to paper/results.png")

if __name__ == "__main__":
    generate_results()
