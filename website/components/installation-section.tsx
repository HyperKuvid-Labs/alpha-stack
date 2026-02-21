"use client"

export function InstallationSection() {
  return (
    <section id="installation" className="py-24 px-6 border-t border-white/10">
      <div className="max-w-3xl mx-auto text-center">
        <h2 className="text-3xl md:text-4xl font-semibold text-white mb-4 tracking-tight">
          Installation
        </h2>
        <p className="text-base text-white/60 mb-12 max-w-2xl mx-auto leading-relaxed">
          We are putting the finishing touches on the AlphaStack CLI. Soon you&apos;ll be able to generate production-ready code with a single command.
        </p>

        <div className="rounded-lg border border-white/10 bg-white/5 p-12 backdrop-blur-sm">
          <h3 className="text-xl font-medium text-white mb-3">Coming to PyPI & Homebrew</h3>
          <p className="text-white/60 mb-8 text-sm">
            AlphaStack will be available for installation via pip and brew.
          </p>
          
          <div className="inline-block text-left bg-black/50 rounded-lg p-4 font-mono text-sm text-white/70 border border-white/10">
            <p className="whitespace-pre">
              <span className="text-white/90">$</span> pip install alphastack  <span className="text-white/40"># Coming Soon</span>
            </p>
          </div>
        </div>
      </div>
    </section>
  )
}
