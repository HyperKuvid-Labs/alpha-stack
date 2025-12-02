"use client"

import { CodeBlock } from "./code-block"
import { AnimatedTabs } from "./animated-tabs"

const usageExamples = [
  {
    id: "basic",
    label: "Basic Usage",
    content: (
      <div className="space-y-4">
        <CodeBlock
          code={`# Generate a new project from a description
alphastack create "A FastAPI backend with PostgreSQL, 
Redis caching, and JWT authentication"

# AlphaStack will:
# ✓ Analyze your requirements
# ✓ Generate project structure
# ✓ Create all necessary files
# ✓ Set up Docker configuration
# ✓ Add comprehensive tests`}
          language="bash"
        />
      </div>
    ),
  },
  {
    id: "interactive",
    label: "Interactive Mode",
    content: (
      <div className="space-y-4">
        <CodeBlock
          code={`# Launch interactive TUI
alphastack create --interactive

# Use arrow keys to navigate options:
# → Select language (Python, TypeScript, Go, Rust)
# → Choose framework (FastAPI, Express, Gin, Axum)
# → Pick database (PostgreSQL, MySQL, MongoDB)
# → Add optional features (Auth, Docker, Tests)`}
          language="bash"
        />
      </div>
    ),
  },
  {
    id: "config",
    label: "Config File",
    content: (
      <div className="space-y-4">
        <CodeBlock
          code={`# Use a configuration file
alphastack create --config project.yaml

# Example project.yaml:
name: my-api
language: python
framework: fastapi
database: postgresql
features:
  - docker
  - authentication
  - testing
  - ci-cd`}
          language="bash"
        />
      </div>
    ),
  },
  {
    id: "advanced",
    label: "Advanced",
    content: (
      <div className="space-y-4">
        <CodeBlock
          code={`# Generate with specific options
alphastack create "REST API" \\
  --lang python \\
  --framework fastapi \\
  --db postgres \\
  --auth jwt \\
  --docker \\
  --tests \\
  --output ./my-project

# Add features to existing project
alphastack add authentication --type oauth2
alphastack add database --type mongodb`}
          language="bash"
        />
      </div>
    ),
  },
]

export function UsageSection() {
  return (
    <section id="usage" className="py-24 px-6 bg-background border-t border-foreground/10">
      <div className="max-w-4xl mx-auto">
        <div className="text-center mb-12">
          <h2 className="text-4xl md:text-5xl font-bold text-foreground mb-4">CLI Demo</h2>
          <p className="text-lg text-foreground/60">See AlphaStack in action</p>
        </div>

        <AnimatedTabs tabs={usageExamples} />
      </div>
    </section>
  )
}
