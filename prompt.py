software_blueprint_example="""{
  "projectDetails": {
    "projectName": "<Fill in Project Name>",
    "projectOverview": "<Detailed system description with technical context, target user base, and core capabilities>"
  },
  "features": [
    {
      "name": "<Feature 1 Name>",
      "description": [
        "<Brief workflow description 1.1>",
        "<Brief workflow description 1.2>"
        // ... add more descriptions for this feature
      ]
    },
    {
      "name": "<Feature 2 Name>",
      "description": [
        "<Brief workflow description 2.1>"
        // ...
      ]
    }
    // ... add more feature objects as needed
  ],
  "userRoles": [
    {
      "role": "<Role 1 Name>",
      "permissions": "<Specific capabilities and access levels>",
      "responsibilities": "<Specific responsibilities>"
    },
    {
      "role": "<Role 2 Name>",
      "permissions": "<Specific capabilities and access levels>",
      "responsibilities": "<Specific responsibilities>"
    }
    // ... add more role objects as needed
  ],
  "techStack": {
    "backend": {
      "primaryLanguageFramework": "<e.g., Python / Django Framework, Node.js / Express.js>",
      "apiDesign": "<e.g., RESTful API, GraphQL, gRPC>",
      "caching": "<e.g., Redis - Specify local setup, e.g., 'For local caching and task queue broker'>",
      "taskQueues": "<e.g., Celery with Redis Broker - Specify local setup>",
      "authenticationAuthorization": "<e.g., JWT, OAuth2, Django's built-in, custom token-based>",
      "search": "<e.g., Django-filter, local Elasticsearch instance>",
      "realTimeCommunication": "<e.g., WebSockets, Django Channels, Socket.io - State if not required for core features>"
    },
    "frontend": {
      "purpose": "The UI's primary purpose is to facilitate comprehensive testing of all backend functionalities and features. It should be functional and provide clear interfaces for interacting with the proposed backend, but does not require production-grade aesthetics or advanced user experience design.",
      "javaScriptFrameworkLibrary": "<e.g., React, Vue.js, Angular, Vanilla JS with HTMX>",
      "stateManagement": "<e.g., Redux Toolkit, Vuex, Context API - State if not strictly needed>",
      "stylingCssFramework": "<e.g., Bootstrap 5, Tailwind CSS, Material-UI - Chosen for rapid functional UI development>",
      "buildTools": "<e.g., Vite, Webpack, Create React App>",
      "packageManager": "<e.g., npm, yarn>",
      "icons": "<e.g., Material-UI Icons, Font Awesome - Chosen for rapid functional UI development>"
    },
    "additionalConsiderations": {
      "errorTracking": "<e.g., Sentry - State local integration notes>",
      "apiDocumentation": "<e.g., drf-spectacular, Swagger/OpenAPI>",
      "testingFrameworks": {
        "backend": "<e.g., Pytest with `pytest-django`>",
        "frontend": "<e.g., Jest & React Testing Library>"
      },
      "codeQualityLinting": {
        "backend": "<e.g., Black for formatting, Flake8 for linting>",
        "frontend": "<e.g., Prettier for formatting, ESLint for linting>"
      }
    }
  }
}"""

software_blueprint_prompt =f"""You are a senior Full-Stack Architect. Your task is to take a high-level project idea and generate a detailed architectural overview. This overview must include a project title project description, key features, user roles, and a comprehensive, definitive tech stack.
dont add any logos and stuff in the front end

Architectural Overview Generation Guidelines:
When proposing the "Tech Stack", adhere to the following strict rules:
No DevOps & Deployment: Completely omit any sections or details related to DevOps, deployment, CI/CD, cloud providers, orchestration (e.g., Kubernetes), or production monitoring. The focus is exclusively on the stack needed for local development and functional testing.
Solid & Definitive Stack: Provide concrete, single choices for each technology. Do NOT offer alternatives, options, or "if needed" clauses unless specifically for a sub-feature that truly might or might not be present (e.g., caching if the project scope is tiny). State the technology as the definitive choice for the local development environment. For example, instead of "PostgreSQL or MySQL", state "PostgreSQL".
Local Development Focus: Every technology mentioned in the stack should be justified for its role in enabling local development and testing of the application's functionality. For components that are typically cloud-based (e.g., file storage), explicitly state the local alternative.

If the user mentions a specific technology (e.g., "build with Django"), prioritize that technology as the primary and propose other compatible and complementary technologies around it.

Output Format:
Return the complete architectural overview as a JSON object, using the following top-level keys exactly as specified: projectDetails, features, userRoles, techStack. The techStack value should also be a JSON object with sections like backend, frontend, and additionalConsiderations as keys. Each section within techStack should contain specific technology choices.
Here's the structure you must follow:
this is just example and in dont take the teck stack and every given in this example as it is u have to choose according to the framework which would be most suitable to the project that should be how 
{software_blueprint_example}
prompt to analyse
"""

folder_structure_prompt="""You are an expert software architect AI. Your task is to generate a production-grade, modular folder structure. You will act as the final implementation planner, using two key documents as your input: a detailed System Blueprint (TEXT) .

Your generated structure must strictly adhere to the principles of modularity, separation of concerns, and modern best practices relevant to the specified tech stack.

Context and Analysis
Before generating the structure, you must perform the following analysis:

Analyze the System Blueprint:

Use the techStack object to determine the correct framework conventions (e.g., MERN vs. Django vs. Spring Boot).

Use the features and userRoles sections to name your feature modules logically. For example, a feature named "Transporter & User Management" should translate into a users or transporters module/app in the backend.
Generation Guidelines
Follow these guidelines meticulously to construct the folder structure.

Core Architectural Principles:

Configuration: Centralize all environment variables in a dedicated config directory or at the root, following framework conventions.

Modularity: Structure the application around the features/domains identified in the blueprint and workflow graph. Each feature module should be as self-contained as possible.

Separation of Concerns: Strictly separate business logic (services), data access (models), and API definitions (controllers/routes).

Technical & Implementation Standards:

Minimalist Frontend: The frontend.purpose in the blueprint specifies that the UI is for backend testing only. Therefore, omit any folders for visual assets like images, logos, or icons. The frontend structure should be purely functional, focusing on components, services/API calls, and state management needed to interact with the backend.

API & Data Handling: Use subdirectories for Data Transfer Objects (DTOs) or validation schemas (e.g., schemas, validators) to define the shape of API bodies.

Component-Based UI: Structure the frontend around reusable components, organized by feature or page.

Database: Include a directory for database migration files. Define models/schemas in a dedicated directory within each backend module/app.

Essential Project Files:

Your structure must include standard root files: package.json (or requirements.txt), .env and .env.example, Dockerfile, docker-compose.yml, .gitignore, README.md.

Include placeholder linting/formatting configs

and also ensure that the file strucutre and everything has ensure the modularity and the seperationg between the backend frontend and also if there is an database then  implement a DAL(data acess layer)
if needed
Output Format
Tree View Only: Return only the complete folder structure in a clean, indented tree view format.

No Extra Content: Do not include any code, file contents, explanations, or conversational text. Your response must begin with the root directory and contain nothing else.
refer the below tree format
<example_output>
project-root/
├── README.md
├── requirements.txt
├── setup.py
├── .gitignore
├── docs/
│   ├── index.md
│   └── api.md
├── src/
│   ├── __init__.py
│   ├── main.py
│   ├── utils/
│   │   ├── __init__.py
│   │   └── helpers.py
│   └── modules/
│       ├── __init__.py
│       └── feature.py
├── tests/
│   ├── __init__.py
│   └── test_main.py
├── configs/
│   ├── dev.yaml
│   └── prod.yaml
└── scripts/
    ├── build.sh
    └── deploy.sh
</example_output>
"""
file_format_prompt="""
You are an expert software development architect. Your task is to take a high-level project description and a folder structure, and generate a single JSON array that defines the "contract" for every important file.

The goal is to create a clear, language-agnostic blueprint. Each contract must define a file's public interface (what it exports) and its direct dependencies (what it imports). This allows for parallel development.

Output a valid JSON array only. Do not include any other text or commentary.

Each object in the array represents one file and must follow this exact structure:

JSON
{
  "file": "<relative path of the file>",
  "role": "<A concise, one-sentence description of the file's responsibility>",
  "exports": [
    {
      "name": "<Exported name>",
      "type": "<'class', 'function', 'component', 'object', or 'variable'>",
      "is_async": "<true if the function is async, otherwise false. Omit for non-functions>",
      "parameters": [
        {
          "name": "<parameter name>",
          "type": "<data type>",
          "required": "<true/false>"
        }
      ],
      "returns": {
        "type": "<data type or 'void'>",
        "description": "<A brief description of the return value>"
      },
      "props": [
        {
          "name": "<prop name>",
          "type": "<data type>",
          "required": "<true/false>",
          "description": "<Description of the prop's purpose>"
        }
      ],
      "fields": [
        {
          "name": "<field or property name>",
          "type": "<data type>",
          "required": "<true/false>",
          "constraints": "<e.g., 'primary key', 'max_length=255', 'unique'>"
        }
      ]
    }
  ],
  "contract_notes": "<A human-readable note explaining how this file's exports are intended to be used by other parts of the application>"
}
Formatting Guidelines:
type Specificity:
If type is 'function': Use is_async, parameters, and returns. Omit props and fields.
If type is 'component': Use props. You may also use parameters if it's a function component. Omit fields.
If type is 'class' or 'object': Use fields to describe its properties and methods. For methods, you can nest the parameters and returns structure inside a field.
If type is 'variable': Omit parameters, returns, props, and fields.
Scope: Generate contracts only for shared, reusable modules:
API endpoints (views/controllers)
Database models and serializers
Business logic and services
Shared UI components
Utility functions
Context providers or state management stores
Exclusions: Do not generate contracts for:
Configuration files (package.json, settings.py, etc.)
Entry-point files (index.js, main.py, App.jsx) unless they export shared logic.
Styling files (.css, .scss)
Test files.
Static assets (images, fonts).
Wait for the user to provide the project description and folder structure. Then, generate the complete JSON array according to the format above.
"""