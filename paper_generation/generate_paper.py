import os
import subprocess

def generate_latex(output_path):
    latex_content = r"""\documentclass{article}
\usepackage[utf8]{inputenc}
\usepackage{graphicx}
\usepackage{hyperref}
\usepackage{geometry}
\geometry{a4paper, margin=1in}

\title{AlphaStack: Autonomous Code Generation using Multi-Agent Systems}
\author{HyperKuvid Labs}
\date{ICML 2026 Submission}

\begin{document}

\maketitle

\begin{abstract}
This paper presents AlphaStack, a novel approach to autonomous code generation using a multi-agent system designed for iterative self-healing and comprehensive validation. AlphaStack bridges the gap between natural language descriptions and production-ready codebases by employing specialized Planning and Correction agents. Through automated Docker-based validation and testing across diverse programming paradigms (CUDA, Go, Rust, TypeScript), the system achieves state-of-the-art results in creating robust software artifacts. Our empirical evaluation across four difficulty tiers demonstrates high success rates, proving the viability of autonomous programming agents in real-world scenarios.
\end{abstract}

\section{Introduction}
Software development requires translating abstract concepts into functional, syntax-correct, and logically sound code. Traditional code generation tools often fail at maintaining complex project structures and resolving dependency conflicts. AlphaStack introduces an intelligent multi-agent architecture capable of generating multi-file project structures, resolving dependency conflicts, and automatically validating the built codebase in sandboxed Docker environments. We demonstrate AlphaStack's capabilities through extensive evaluation against 40 challenging programming tasks ranging from simple utility scripts to complex concurrent and GPU-optimized systems.

\section{Methodology}
The core generation pipeline of AlphaStack is driven by a specialized multi-agent architecture:
\begin{itemize}
    \item \textbf{Planning Agent:} Analyzes structural requirements and execution errors, generating comprehensive fix strategies using tool-augmented reasoning.
    \item \textbf{Correction Agent:} Executes planned fixes while maintaining context-aware code understanding.
\end{itemize}

The system employs an iterative self-healing process. Once code is generated, a sandboxed Docker container builds and executes tests. Build errors or test failures trigger the Planning Agent to diagnose the issue and formulate a fix plan. The Correction Agent applies the necessary code modifications. This feedback loop continues until all tests pass or a maximum iteration limit is reached.

\section{Architecture Diagram}
The following diagram illustrates AlphaStack's end-to-end processing pipeline, transitioning from natural language input to a validated, production-ready project.

\begin{figure}[h]
    \centering
    \includegraphics[width=0.8\textwidth]{architecture.png}
    \caption{AlphaStack Generation Pipeline}
    \label{fig:architecture}
\end{figure}

\section{Results}
AlphaStack was evaluated against several frontier foundation models, including gpt-5.2, glm-5, minimaxm2.5, and claude sonnet 4.6, on standard benchmarks like HumanEval and MDDP. The evaluation demonstrates consistent and state-of-the-art performance, highlighting the effectiveness of the iterative multi-agent framework.

\begin{figure}[h]
    \centering
    \includegraphics[width=0.8\textwidth]{results.png}
    \caption{Model Performance on HumanEval and MDDP Benchmarks}
    \label{fig:results}
\end{figure}

\section{Conclusion}
We have introduced AlphaStack, an autonomous multi-agent code generation system. Through iterative self-healing, advanced context management, and Docker-based testing, AlphaStack significantly advances the capabilities of AI-driven software engineering. Future work will expand language support and address more complex, distributed system evaluations.

\section*{Supplementary Material}
Additional artifacts, full evaluation metrics, and the source code repository are available at the AlphaStack GitHub repository: \url{https://github.com/HyperKuvid-Labs/alpha-stack}.

\end{document}
"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(latex_content)
    print(f"Successfully saved LaTeX file to {output_path}")

def compile_latex(tex_path):
    directory = os.path.dirname(tex_path)
    filename = os.path.basename(tex_path)
    print(f"Compiling {filename} in {directory}...")

    # Run pdflatex twice to ensure references and formatting are fully resolved
    try:
        subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", filename],
            cwd=directory,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        print("First pass compilation successful.")

        subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", filename],
            cwd=directory,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        print("Second pass compilation successful. PDF generated.")
    except subprocess.CalledProcessError as e:
        print("Failed to compile LaTeX to PDF.")
        print(e.stdout.decode('utf-8'))
        print(e.stderr.decode('utf-8'))

if __name__ == "__main__":
    tex_path = os.path.join(os.path.dirname(__file__), "paper.tex")
    generate_latex(tex_path)
    compile_latex(tex_path)
