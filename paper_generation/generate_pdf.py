from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

def generate_pdf():
    pdf_filename = "paper_generation/research_paper.pdf"
    doc = SimpleDocTemplate(pdf_filename, pagesize=letter)
    styles = getSampleStyleSheet()

    # Create custom styles
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=20,
        alignment=1 # Center aligned
    )
    heading_style = ParagraphStyle(
        'HeadingStyle',
        parent=styles['Heading2'],
        fontSize=18,
        spaceAfter=10,
        spaceBefore=15
    )
    body_style = ParagraphStyle(
        'BodyStyle',
        parent=styles['Normal'],
        fontSize=12,
        spaceAfter=10,
        leading=15 # Line spacing
    )

    story = []

    # Title
    story.append(Paragraph("AlphaStack: AI-powered Project Generator via Multi-Agent Systems", title_style))
    story.append(Spacer(1, 20))

    # Abstract
    story.append(Paragraph("Abstract", heading_style))
    abstract_text = """This paper presents AlphaStack, a novel approach to autonomous code generation utilizing multi-agent systems with iterative self-healing and comprehensive validation. AlphaStack transforms natural language descriptions into complete, production-ready codebases with Docker configurations and automated testing. Through a combination of a Planning Agent and a Correction Agent, the system autonomously resolves software errors without human intervention, ensuring high success rates across diverse programming paradigms. Our comprehensive evaluation demonstrates the efficacy of this approach on 40 programming challenges across four modern languages."""
    story.append(Paragraph(abstract_text, body_style))

    # Introduction
    story.append(Paragraph("Introduction", heading_style))
    intro_text = """The automation of software development has been a long-standing goal in computer science. With recent advancements in large language models (LLMs), there has been significant progress in code generation. However, generating complete, production-ready codebases from high-level natural language descriptions remains a challenging task. It requires not only generating syntactically correct code but also ensuring proper architectural design, resolving dependency conflicts, and verifying correctness through testing. AlphaStack addresses these challenges by employing a multi-agent architecture that separates planning and correction concerns, enabling iterative self-healing and robust validation in isolated environments."""
    story.append(Paragraph(intro_text, body_style))

    # Methodology
    story.append(Paragraph("Methodology", heading_style))
    method_text = """The AlphaStack methodology revolves around an intelligent multi-agent architecture consisting of a Planning Agent and a Correction Agent. The generation pipeline starts with analyzing the natural language input to create a software blueprint. This blueprint dictates the folder structure and file contents, encompassing source code, configurations, tests, and documentation. Crucially, AlphaStack integrates Docker-based validation to ensure the generated code is functional. It automatically creates Dockerfiles to sandbox build and test environments. If build or test failures occur, the Planning Agent analyzes the errors and formulates comprehensive fix strategies. The Correction Agent then executes these fixes, iteratively refining the codebase until successful validation or a maximum number of iterations is reached."""
    story.append(Paragraph(method_text, body_style))

    # Architecture Diagram
    story.append(Paragraph("Architecture Diagram", heading_style))
    try:
        diagram_img = Image("paper_generation/architecture_diagram.png", width=450, height=250)
        story.append(diagram_img)
        story.append(Paragraph("<i>Figure 1: AlphaStack Multi-Agent Generation and Validation Pipeline</i>", styles['Normal']))
    except Exception as e:
        story.append(Paragraph(f"[Architecture Diagram Image Missing: {e}]", body_style))
    story.append(Spacer(1, 10))

    # Results
    story.append(Paragraph("Results", heading_style))
    results_text = """We evaluated AlphaStack's capabilities using state-of-the-art language models on established benchmarks: HumanEval and the Multi-Domain Development Paradigm (MDDP). The models tested include GPT-5.2, GLM-5, MiniMax-M2.5, and Claude Sonnet 4.6. The results, as depicted in the graph below, highlight the strong performance of these models when integrated into the AlphaStack framework, demonstrating high success rates in generating functionally correct code."""
    story.append(Paragraph(results_text, body_style))

    try:
        graph_img = Image("paper_generation/results_graph.png", width=400, height=240)
        story.append(graph_img)
        story.append(Paragraph("<i>Figure 2: Model Performance on HumanEval and MDDP</i>", styles['Normal']))
    except Exception as e:
        story.append(Paragraph(f"[Results Graph Image Missing: {e}]", body_style))
    story.append(Spacer(1, 10))

    # Conclusion
    story.append(Paragraph("Conclusion", heading_style))
    conclusion_text = """AlphaStack introduces a highly effective methodology for autonomous code generation. By leveraging a multi-agent architecture with integrated iterative self-healing and Docker-based validation, it successfully bridges the gap between natural language intent and production-ready code. The robust evaluation demonstrates its versatility across various languages and complexities. Future work will focus on expanding language support, optimizing iteration efficiency, and integrating more advanced static analysis tools to further enhance the reliability of generated projects."""
    story.append(Paragraph(conclusion_text, body_style))

    # Supplementary Material
    story.append(Paragraph("Supplementary Material", heading_style))
    supp_text = """The source code, evaluation suite, and detailed benchmark logs for AlphaStack are available in the project repository. The evaluation suite includes 40 challenges across CUDA, Go, Rust, and TypeScript, categorized into four difficulty tiers ranging from fundamentals to production systems."""
    story.append(Paragraph(supp_text, body_style))

    # Build the PDF
    doc.build(story)
    print(f"PDF successfully generated at: {pdf_filename}")

if __name__ == "__main__":
    generate_pdf()
