"use client"

import { useState } from "react"

const plannedFeatures = [
  {
    title: "Inline Chat for File Editing",
    description: "Chat interface directly in the terminal for real-time code editing and AI assistance during development.",
  },
  {
    title: "Integrated Linters",
    description: "Built-in linting support for multiple languages with automatic error detection and suggestions.",
  },
  {
    title: "Vim/Neovim Support",
    description: "Native Vim and Neovim integration for file editing directly within the AlphaStack terminal interface.",
  },
]

export function RoadmapSection() {
  const [isExpanded, setIsExpanded] = useState(false)

  return (
    <section className="py-16 px-6 border-t border-white/10">
      <div className="max-w-4xl mx-auto">
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="w-full flex items-center justify-between text-left group"
        >
          <div>
            <h2 className="text-2xl md:text-3xl font-semibold text-white mb-2 tracking-tight group-hover:text-white/80 transition-colors">
              Planned Updates
            </h2>
            <p className="text-sm text-white/50">
              {isExpanded ? "Click to collapse" : "Click to see what's coming next"}
            </p>
          </div>
          <div className="text-white/50 group-hover:text-white/70 transition-all">
            <svg
              className={`w-6 h-6 transition-transform duration-300 ${isExpanded ? "rotate-180" : ""}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </div>
        </button>

        <div
          className={`overflow-hidden transition-all duration-300 ease-in-out ${
            isExpanded ? "max-h-[1000px] opacity-100 mt-8" : "max-h-0 opacity-0"
          }`}
        >
          <div className="space-y-6">
            {plannedFeatures.map((feature, index) => (
              <div key={index} className="flex gap-4 group/item">
                <div className="flex-shrink-0 mt-1">
                  <div className="w-2 h-2 rounded-full bg-white/30 group-hover/item:bg-white/50 transition-colors" />
                </div>
                <div className="flex-1">
                  <h3 className="text-base font-medium text-white mb-1 group-hover/item:text-white/80 transition-colors">
                    {feature.title}
                  </h3>
                  <p className="text-sm text-white/60 leading-relaxed">{feature.description}</p>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-8 pt-6 border-t border-white/10">
            <p className="text-xs text-white/50 text-center">
              These features are currently in development and will be released in future versions.
            </p>
          </div>
        </div>
      </div>
    </section>
  )
}

