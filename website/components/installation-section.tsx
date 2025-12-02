"use client"

import { CodeBlock } from "./code-block"
import { AnimatedTabs } from "./animated-tabs"

const installMethods = [
  {
    id: "pip",
    label: "pip",
    content: (
      <CodeBlock
        code={`# Install via pip (recommended)
pip install alphastack

# Or install with optional dependencies
pip install alphastack[all]`}
        language="bash"
      />
    ),
  },
  {
    id: "homebrew",
    label: "Homebrew",
    content: (
      <CodeBlock
        code={`# Add the tap
brew tap alphastack/tap

# Install AlphaStack
brew install alphastack`}
        language="bash"
      />
    ),
  },
  {
    id: "manual",
    label: "Manual",
    content: (
      <CodeBlock
        code={`# Clone the repository
git clone https://github.com/alphastack/alphastack.git
cd alphastack

# Install dependencies
pip install -e .

# Verify installation
alphastack --version`}
        language="bash"
      />
    ),
  },
]

export function InstallationSection() {
  return (
    <section id="installation" className="py-24 px-6 bg-background border-t border-foreground/10">
      <div className="max-w-3xl mx-auto">
        <div className="text-center mb-12">
          <h2 className="text-4xl md:text-5xl font-bold text-foreground mb-4">Installation</h2>
          <p className="text-lg text-foreground/60">Get up and running in seconds</p>
        </div>

        <AnimatedTabs tabs={installMethods} />
      </div>
    </section>
  )
}
