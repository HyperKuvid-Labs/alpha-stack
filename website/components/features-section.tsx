"use client"

const features = [
  {
    title: "AI Blueprint Creation",
    description:
      "Analyzes your prompt and creates a detailed project specification with optimal directory structure and coding standards.",
  },
  {
    title: "Complete Code Generation",
    description:
      "Generates all source files, dependencies, and configurations using multi-agent orchestration with planners and correctors.",
  },
  {
    title: "Docker Integration",
    description:
      "Automatically creates Dockerfiles and docker-compose configurations, with comprehensive testing to validate project functionality.",
  },
  {
    title: "Dependency Resolution",
    description: "Intelligent dependency analysis and automatic fixes using DAG-based tracking and iterative error correction.",
  },
  {
    title: "Interactive TUI",
    description: "Beautiful terminal user interface for guided project configuration with real-time progress updates and status tracking.",
  },
  {
    title: "Multi-Language Support",
    description: "Grammar-agnostic architecture supports Python, TypeScript, Go, Rust, and more with idiomatic code patterns.",
  },
]

export function FeaturesSection() {
  return (
    <section id="features" className="py-24 px-6 border-t border-white/10">
      <div className="max-w-5xl mx-auto">
        {/* Features Section */}
        <div className="mb-24">
          <h2 className="text-3xl md:text-4xl font-semibold text-white mb-4 tracking-tight">
            Features
          </h2>
          <p className="text-base text-white/60 mb-12 max-w-3xl leading-relaxed">
            Everything you need to go from idea to production-ready code. AlphaStack handles project structure, 
            code generation, testing, and deployment configuration automatically.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            {features.map((feature) => (
              <div key={feature.title} className="group">
                <h3 className="text-lg font-medium text-white mb-2 group-hover:text-white/80 transition-colors">
                  {feature.title}
                </h3>
                <p className="text-sm text-white/60 leading-relaxed">{feature.description}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Benchmarks Section */}
        <div>
          <h2 className="text-3xl md:text-4xl font-semibold text-white mb-4 tracking-tight">
            Benchmarks
          </h2>
          <p className="text-base text-white/60 mb-12 max-w-3xl leading-relaxed">
            Comprehensive benchmark results comparing AlphaStack against MetaGPT and ChatDev on HumanEval, MBPP, 
            and complex multi-file project generation tasks.
          </p>

          <div className="text-center py-12 px-6 border border-white/10 rounded-lg">
            <div className="text-2xl md:text-3xl font-semibold text-white mb-3">Coming Soon</div>
            <div className="text-sm text-white/60">
              Benchmark results will be published shortly
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
