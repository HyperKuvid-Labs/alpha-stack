import os
import subprocess

latex_template = r"""
\documentclass[10pt,twocolumn,letterpaper]{article}

\usepackage{graphicx}
\usepackage{amsmath}
\usepackage{amssymb}
\usepackage{booktabs}
\usepackage{hyperref}

\title{AlphaStack: Autonomous Code Generation via Iterative Self-Healing Multi-Agent Systems}

\author{AlphaStack Team\\
HyperKuvid Labs\\
{\tt\small research@hyperkuvid.com}
}

\begin{document}

\maketitle

\begin{abstract}
We introduce AlphaStack, a novel AI-powered project generator that transforms natural language descriptions into complete, production-ready codebases. Our approach utilizes a multi-agent system comprising a Planning Agent and a Correction Agent to achieve iterative self-healing. By comprehensively validating generated code across diverse programming paradigms using isolated Docker environments, AlphaStack significantly improves the reliability and correctness of autonomous code generation. We evaluate AlphaStack on a custom suite of 40 programming challenges across CUDA, Go, Rust, and TypeScript, demonstrating its efficacy across varying levels of difficulty.
\end{abstract}

\section{Introduction}
Autonomous code generation has seen rapid advancements, yet generating complete, production-ready, and error-free codebases remains a significant challenge. Existing approaches often struggle with dependency resolution, complex architectures, and iterative debugging. To address these issues, we present AlphaStack, an end-to-end multi-agent framework designed to autonomously generate, test, and self-heal software projects.

Our system distinguishes itself by coupling code generation with rigorous Docker-based validation. When a build or test fails, a Planning Agent analyzes the errors and formulates a strategic fix, which is then executed by a Correction Agent. This iterative process continues until the generated project is fully functional.

\section{Methodology}
AlphaStack operates through a structured seven-phase pipeline:
\begin{enumerate}
    \item \textbf{Software Blueprint Generation:} Analyzes natural language input to design a comprehensive project structure.
    \item \textbf{File Generation:} Generates source code, configurations, and tests.
    \item \textbf{Dockerfile Generation:} Creates an appropriate Dockerfile for isolated validation.
    \item \textbf{Dependency Analysis:} Analyzes import graphs to identify required dependencies.
    \item \textbf{Dependency File Generation:} Produces package manifests (e.g., \texttt{requirements.txt}, \texttt{package.json}).
    \item \textbf{Dependency Resolution:} Validates and resolves dependency conflicts.
    \item \textbf{Docker Testing Pipeline:} Sandboxed build and test execution.
\end{enumerate}

When errors occur during the testing phase, the system enters an autonomous self-healing loop. The Planning Agent utilizes tool-augmented reasoning to analyze logs and devise a correction strategy, which is executed by the Correction Agent. This loop iterates until all tests pass or a maximum iteration limit is reached.

\section{Architecture}
The architecture of AlphaStack is designed to support scalable and robust code generation. The multi-agent interaction is critical for resolving complex compilation and runtime errors autonomously.

\begin{figure}[ht]
    \centering
    \includegraphics[width=\linewidth]{architecture.png}
    \caption{The AlphaStack System Architecture. The iterative loop between the Planning Agent and Correction Agent enables autonomous self-healing.}
    \label{fig:architecture}
\end{figure}

\section{Results}
We evaluated AlphaStack on established benchmarks, including HumanEval and a custom Multi-Domain Development Project (MDDP) benchmark. We compared the performance of several state-of-the-art models within our framework: GPT-5.2, GLM-5, MiniMax-m2.5, and Claude Sonnet 4.6.

\begin{figure}[ht]
    \centering
    \includegraphics[width=\linewidth]{results.png}
    \caption{Performance comparison of various models on HumanEval and MDDP benchmarks using the AlphaStack framework.}
    \label{fig:results}
\end{figure}

The results demonstrate that integrating advanced models with AlphaStack's self-healing loop yields exceptionally high success rates, with GPT-5.2 and Claude Sonnet 4.6 achieving state-of-the-art performance on both benchmarks.

\section{Conclusion}
AlphaStack represents a significant step forward in autonomous software development. By combining multi-agent self-healing with rigorous, isolated testing environments, our framework consistently produces reliable, production-ready code from natural language prompts. Future work will focus on expanding language support and optimizing the iterative correction loop for even greater efficiency.

\section*{Supplementary Material}
Additional details regarding the evaluation framework, including the full suite of 40 programming challenges and Docker configurations, can be found in the AlphaStack repository: \url{https://github.com/HyperKuvid-Labs/alpha-stack}.

\end{document}
"""

def generate_paper():
    os.makedirs('paper_generation', exist_ok=True)

    tex_path = 'paper_generation/paper.tex'
    with open(tex_path, 'w') as f:
        f.write(latex_template)

    print(f"LaTeX file written to {tex_path}")

    # Run pdflatex twice for references/formatting
    for _ in range(2):
        process = subprocess.run(
            ['pdflatex', '-interaction=nonstopmode', 'paper.tex'],
            cwd='paper_generation',
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if process.returncode != 0:
            print("LaTeX compilation encountered errors/warnings:")
            print(process.stdout)
            # Don't exit early, as nonstopmode will often return non-zero for minor warnings

    if os.path.exists('paper_generation/paper.pdf'):
        print("Paper compiled successfully: paper_generation/paper.pdf")
    else:
        print("Failed to compile PDF.")

if __name__ == "__main__":
    generate_paper()
