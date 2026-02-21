"use client"

const steps = [
  {
    number: "01",
    title: "Software Blueprint Creation",
    description: "AI analyzes your prompt and creates a detailed project specification with architecture decisions and requirements.",
  },
  {
    number: "02",
    title: "Folder Structure Generation",
    description: "Creates the optimal directory hierarchy and project structure based on best practices for your tech stack.",
  },
  {
    number: "03",
    title: "File Format Contracts",
    description: "Determines file formats, coding standards, and establishes contracts for consistent code generation.",
  },
  {
    number: "04",
    title: "Code Generation",
    description: "Generates all source files with appropriate content using multi-agent orchestration and context propagation.",
  },
  {
    number: "05",
    title: "Dependency Analysis",
    description: "Analyzes and resolves project dependencies using DAG-based tracking with incremental updates.",
  },
  {
    number: "06",
    title: "Docker Configuration",
    description: "Creates Dockerfile and docker-compose files automatically tailored to your project requirements.",
  },
  {
    number: "07",
    title: "Testing",
    description: "Runs Docker builds and comprehensive tests to validate project functionality and integration.",
  },
  {
    number: "08",
    title: "Error Correction",
    description: "Automatically detects and fixes common errors using diagnostic and repair agents with topological ordering.",
  },
]

export function UsageSection() {
  return (
    <section id="usage" className="py-24 px-6 border-t border-white/10">
      <div className="max-w-4xl mx-auto">
        <h2 className="text-3xl md:text-4xl font-semibold text-white mb-4 tracking-tight">
          How It Works
        </h2>
        <p className="text-base text-white/60 mb-12 leading-relaxed">
          Describe your project in natural language, and AlphaStack orchestrates multiple agents to generate production-ready code through an iterative, dependency-aware process.
        </p>

        {/* Command Example */}
        <div className="mb-16">
          <div className="rounded-lg border border-white/10 bg-black/50 p-4 font-mono text-sm mb-4">
            <p className="text-white/70">
              <span className="text-white/90">$</span> alphastack generate <span className="text-white/90">&quot;A Flask web app for managing tasks with user authentication&quot;</span>
            </p>
          </div>
          <p className="text-sm text-white/50 text-center">
            The multi-agent system begins its orchestrated workflow
          </p>
        </div>

        {/* Process Steps */}
        <div className="space-y-8">
          {steps.map((step) => (
            <div key={step.number} className="flex gap-6 group">
              <div className="flex-shrink-0">
                <div className="text-2xl font-semibold text-white/30 group-hover:text-white/50 transition-colors">
                  {step.number}
                </div>
              </div>
              <div className="flex-1 pt-1">
                <h3 className="text-base font-medium text-white mb-2">
                  {step.title}
                </h3>
                <p className="text-sm text-white/60 leading-relaxed">
                  {step.description}
                </p>
              </div>
            </div>
          ))}
        </div>

        {/* Output Info */}
        <div className="mt-16 pt-8 border-t border-white/10">
          <h3 className="text-lg font-medium text-white mb-4">Output</h3>
          <p className="text-sm text-white/60 leading-relaxed mb-4">
            Generated projects include complete source code, Docker configuration files, test suites, and project metadata—all ready for immediate use.
          </p>
          <div className="flex flex-wrap gap-3">
            <span className="px-3 py-1 border border-white/10 rounded-full text-xs text-white/60">Complete Source Code</span>
            <span className="px-3 py-1 border border-white/10 rounded-full text-xs text-white/60">Docker Configs</span>
            <span className="px-3 py-1 border border-white/10 rounded-full text-xs text-white/60">Test Files</span>
            <span className="px-3 py-1 border border-white/10 rounded-full text-xs text-white/60">Dependencies Resolved</span>
          </div>
        </div>
      </div>
    </section>
  )
}
