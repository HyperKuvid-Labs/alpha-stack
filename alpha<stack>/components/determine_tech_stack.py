import google.generativeai as genai
import pathlib
import os

def generate_ts(prompt: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY")

    genai.configure(api_key=api_key)
    #generate the tech stack and reqs documentation
    ts_prompt = f"""
    User Request: {prompt}
    
    You are an experienced software engineer and technical architect with expertise in generating comprehensive technical stack documentation for software projects.
    
    Based on the user's request above, generate a detailed technical stack documentation that includes:
    
    ## Technical Stack Analysis
    
    ### Core Technologies
    - Programming languages with justifications
    - Frameworks and libraries with version recommendations
    - Database systems and data storage solutions
    - Infrastructure and deployment platforms
    
    ### Architecture Overview
    - System architecture pattern (microservices, monolithic, etc.)
    - Component relationships and data flow
    - Integration patterns and APIs
    
    ## Requirements Documentation
    
    ### Functional Requirements
    - Core features and capabilities
    - User stories and use cases
    - Performance expectations
    
    ### Non-Functional Requirements
    - Scalability requirements
    - Security considerations
    - Performance benchmarks
    - Maintenance and monitoring needs
    
    ### Technical Constraints
    - Resource limitations
    - Technology restrictions
    - Timeline considerations
    
    ## Implementation Recommendations
    
    ### Development Approach
    - Recommended development methodology
    - Testing strategy
    - Deployment pipeline
    
    ### Risk Assessment
    - Technical risks and mitigation strategies
    - Alternative technology options
    
    ## Getting Started
    - Prerequisites and setup instructions
    - Initial project structure
    - Key configuration requirements
    
    Please ensure all recommendations are:
    1. Specific to the user's requirements
    2. Industry best practices compliant
    3. Scalable and maintainable
    4. Well-justified with reasoning
    
    Format the entire response in clean, well-structured markdown with proper headers, bullet points, and code blocks where appropriate.

    Return only the markdown content without any additional text or explanations. And no markdown formatting artifacts.
    """
    
    resp = genai.GenerativeModel("gemini-2.5-pro-preview-05-06").generate_content(
        contents=ts_prompt
    )
    
    return resp.text


#now i want this to be stored in md file
def gen_and_store_ts(prompt:str):
    ts = generate_ts(prompt=prompt)
    print(ts)
    #createing the directory, of i miss out to do so
    path = pathlib.Path(os.getcwd()) / "docs" / "tech_stack_reqs.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    #writing the content to the md file for other components to use
    print("Writing tech stack and requirements to:", path)
    with open(path, "w") as f:
        f.write(ts)
    print("Tech stack and requirements documentation generated successfully.")
    return 