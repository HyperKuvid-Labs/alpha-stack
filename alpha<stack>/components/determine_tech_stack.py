import google.generativeai as genai
import pathlib
import os

def generate_ts(prompt: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY")

    genai.configure(api_key="AIzaSyAb56f8gsiKgrg7ry3UWcuiDbGQsLMFJj0")
    #generate the tech stack and reqs documentation
    ts_prompt = f"""
    User Request: {prompt}

    You are an experienced software engineer and technical architect with expertise in generating comprehensive technical stack documentation tailored for software projects.

    Based on the user's request above, generate a detailed and well-structured technical documentation that includes:

    ## Technical Stack Documentation

    ### Project Title
    - Determine a relevant, concise, and professional project title based on the user's use case.

    ### Core Technologies  
    - **Programming Languages**  
    - Include chosen languages with clear justifications for each  
    - **Frameworks & Libraries**  
    - Recommend major frameworks and libraries with suggested versions  
    - Explain why each is suitable for this project  

    - **Databases & Storage**  
    - Relational, NoSQL, or distributed storage  
    - Rationale for choice including scalability and consistency needs  

    - **Infrastructure & Deployment**  
    - Cloud providers, virtualization/containerization tools  
    - CI/CD pipelines and deployment workflow  

    ### Architecture Overview  
    - **System Design Pattern**  
    - Indicate architectural style (monolith, microservices, event-driven, etc.)  
    - **Components & Data Flow**  
    - Describe key system components and how they interact  
    - **Integration & APIs**  
    - External/internal API integrations and protocols (REST, GraphQL, gRPC, etc.)

    ## Requirements Documentation

    ### Functional Requirements  
    - Highlight major features with technical implications  
    - Include at least 3–5 sample user stories  
    - Expected system behaviors, inputs/outputs  

    ### Non-Functional Requirements  
    - Performance goals (e.g., response time, throughput)  
    - Security measures (OWASP, access control, encryption)  
    - Scalability & reliability expectations  
    - Monitoring and alerting mechanisms  

    ### Technical Constraints  
    - Budget or resource limitations  
    - Mandatory technology/tool use  
    - Time-to-market or delivery timelines  

    ## Implementation Recommendations

    ### Development Approach  
    - Suggested software development methodology (Agile, Scrum, Kanban, etc.)  
    - Testing practices (unit, integration, e2e, CI testing)  
    - CI/CD design, preferred tools (GitHub Actions, GitLab CI, Jenkins)  

    ### Risk Assessment  
    - Identify potential bottlenecks or technical uncertainties  
    - Propose mitigation strategies  
    - List alternate technologies with pros and cons  

    ## Getting Started  

    ### Prerequisites  
    - Developer machine setup  
    - Required tools and skillsets  

    ### Project Structure  
    - Suggested folder/file structure  
    - Initial scaffold or boilerplate setup info  

    ### Configuration  
    - Environment variables  
    - Database connections and secrets handling  

    **Ensure that all recommendations are:**  
    1. Tailored to the user’s context and project scope  
    2. Based on current industry best practices  
    3. Scalable, maintainable, and secure  
    4. Fully justified and explained  

    **Deliver the entire response as structured markdown content with appropriate headers, bullet points, and inline code blocks where necessary. Do not include any surrounding explanations. Only output the markdown body.**
    """
    
    resp = genai.GenerativeModel("gemini-2.5-pro-preview-05-06").generate_content(
        contents=ts_prompt
    )
    
    return resp.text

def get_project_name(ts: str) -> str:
    genai.configure(api_key="AIzaSyAb56f8gsiKgrg7ry3UWcuiDbGQsLMFJj0")

    prompt = f"""
    Extract the project name from the following technical stack documentation:

    {ts}

    return only the project name, no additional text or explanations.
    """
    resp = genai.GenerativeModel("gemini-2.5-pro-preview-05-06").generate_content(
        contents=prompt
    )
    return resp.text

#now i want this to be stored in md file
def gen_and_store_ts(prompt:str):
    ts = generate_ts(prompt=prompt)
    print(ts)
    project_name = get_project_name(ts)
    #createing the directory, of i miss out to do so
    path = pathlib.Path(os.getcwd()) / "docs" / "tech_stack_reqs.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    #writing the content to the md file for other components to use
    print("Writing tech stack and requirements to:", path)
    with open(path, "w") as f:
        f.write(ts)
    print("Tech stack and requirements documentation generated successfully.")
    return project_name