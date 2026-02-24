from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Preformatted
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER
from reportlab.lib import colors

def create_pdf(filename):
    doc = SimpleDocTemplate(filename, pagesize=letter)
    story = []
    styles = getSampleStyleSheet()

    # Custom Styles
    title_style = styles['Title']
    heading_style = styles['Heading1']
    normal_style = styles['BodyText']
    normal_style.alignment = TA_JUSTIFY

    code_style = ParagraphStyle(
        'Code',
        parent=styles['Code'],
        fontSize=8,
        leading=10,
        fontName='Courier',
        backColor=colors.lightgrey,
        borderPadding=5
    )

    # Title
    story.append(Paragraph("AlphaStack: Autonomous Code Generation via Multi-Agent Systems with Iterative Self-Healing", title_style))
    story.append(Spacer(1, 12))
    story.append(Paragraph("AlphaStack Team", styles['Normal']))
    story.append(Spacer(1, 24))

    # Abstract
    story.append(Paragraph("Abstract", heading_style))
    abstract_text = """
    We introduce AlphaStack, a novel approach to autonomous code generation using multi-agent systems with iterative self-healing and comprehensive validation across diverse programming paradigms. By separating planning and correction concerns, AlphaStack achieves high success rates in generating production-ready codebases. Our system features an intelligent multi-agent architecture, comprehensive code generation capabilities, and a Docker-based validation framework. We evaluate AlphaStack on a custom benchmark of 40 programming challenges across CUDA, Go, Rust, and TypeScript, demonstrating its effectiveness in handling complex software engineering tasks.
    """
    story.append(Paragraph(abstract_text, normal_style))
    story.append(Spacer(1, 12))

    # Introduction
    story.append(Paragraph("Introduction", heading_style))
    intro_text = """
    The generation of complete, production-ready codebases from natural language descriptions remains a significant challenge in AI-assisted software development. While current models excel at generating code snippets, they often struggle with multi-file projects, dependency management, and build configurations.
    <br/><br/>
    AlphaStack addresses these challenges through an intelligent multi-agent architecture that includes a Planning Agent for error analysis and a Correction Agent for executing fixes. The system employs iterative self-healing to automatically detect and resolve dependency conflicts, build errors, and test failures. Furthermore, AlphaStack utilizes Docker-based validation to ensure that generated projects are not only syntactically correct but also functional in isolated environments.
    """
    story.append(Paragraph(intro_text, normal_style))
    story.append(Spacer(1, 12))

    # Methodology
    story.append(Paragraph("Methodology", heading_style))
    method_text = """
    <b>Multi-Agent Architecture</b><br/>
    AlphaStack's core innovation lies in its multi-agent system:
    <br/>- <b>Planning Agent:</b> Analyzes errors and generates comprehensive fix strategies using tool-augmented reasoning. It maintains a cache of the project structure to enable efficient planning.
    <br/>- <b>Correction Agent:</b> Executes the fixes proposed by the Planning Agent. It validates code changes before application and uses language-specific parsers to prevent syntax errors.
    <br/><br/>
    <b>Iterative Self-Healing</b><br/>
    The system operates in a loop of generation, validation, and correction. If a build or test fails, the Planning Agent analyzes the error logs, and the Correction Agent applies the necessary fixes. This process continues until the project builds and passes all tests, or a maximum number of iterations is reached.
    <br/><br/>
    <b>Docker-Based Validation</b><br/>
    To ensure reproducibility and security, all generated projects are validated within Docker containers. This provides isolated build and test environments with resource management (configurable CPU/memory limits).
    """
    story.append(Paragraph(method_text, normal_style))
    story.append(Spacer(1, 12))

    # Architecture Diagram
    story.append(Paragraph("Architecture", heading_style))
    arch_text = """
    The architecture of AlphaStack is designed to streamline the flow from natural language input to a production-ready project. The process involves blueprint generation, multi-file code generation, dependency resolution, Docker configuration, and iterative validation.
    """
    story.append(Paragraph(arch_text, normal_style))
    story.append(Spacer(1, 12))

    mermaid_code = """
graph LR
    A[Natural Language Input] --> B[AI Analysis & Blueprint]
    B --> C[Multi-File Code Generation]
    C --> D[Dependency Resolution]
    D --> E[Docker Configuration]
    E --> F[Build Validation]
    F --> G{Build Success?}
    G -->|No| H[Planning Agent]
    H --> I[Correction Agent]
    I --> F
    G -->|Yes| J[Test Execution]
    J --> K{Tests Pass?}
    K -->|No| H
    K -->|Yes| L[Production-Ready Project]
    """
    story.append(Preformatted(mermaid_code, code_style))
    story.append(Paragraph("Figure 1: AlphaStack Architecture Diagram (Mermaid Source)", styles['Normal']))
    story.append(Spacer(1, 12))

    # Results
    story.append(Paragraph("Results", heading_style))
    results_text = """
    We evaluated AlphaStack using models such as GPT-5.2, Claude Sonnet 4.6, GLM-5, and MinimaxM2.5 on two key benchmarks: HumanEval (Pass@1 %) and MDDP Score.
    """
    story.append(Paragraph(results_text, normal_style))
    story.append(Spacer(1, 12))

    # Add Image
    try:
        im = Image("results.png", width=400, height=240)
        story.append(im)
        story.append(Paragraph("Figure 2: Performance Comparison on HumanEval and MDDP", styles['Normal']))
    except Exception as e:
        story.append(Paragraph(f"Error loading image: {e}", normal_style))

    story.append(Spacer(1, 12))

    # Conclusion
    story.append(Paragraph("Conclusion", heading_style))
    conclusion_text = """
    AlphaStack presents a robust solution for autonomous project generation. By leveraging multi-agent systems and iterative self-healing, it effectively bridges the gap between natural language requirements and functional, production-ready code. Future work will focus on expanding language support and integrating more advanced reasoning capabilities into the Planning Agent.
    """
    story.append(Paragraph(conclusion_text, normal_style))

    doc.build(story)
    print(f"PDF generated: {filename}")

if __name__ == "__main__":
    create_pdf("paper.pdf")
