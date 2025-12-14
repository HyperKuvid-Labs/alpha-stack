"use client"

import { useState } from "react"
import { Download, FileText, ExternalLink } from "lucide-react"
import { FloatingNavbar } from "@/components/floating-navbar"

export default function DocsPage() {
  const [isLoading, setIsLoading] = useState(true)

  const handleDownload = () => {
    const link = document.createElement('a')
    link.href = '/alpha_stack_paper_draft2.pdf'
    link.download = 'AlphaStack_Documentation.pdf'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  const openInNewTab = () => {
    window.open('/alpha_stack_paper_draft2.pdf', '_blank')
  }

  return (
    <div className="min-h-screen bg-background">
      <FloatingNavbar />

      <main className="container mx-auto px-4 md:px-6 py-8 max-w-6xl mt-20">
        {/* Header Section */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-8">
          <div className="flex items-center gap-3">
            <FileText className="w-6 h-6 text-muted-foreground" />
            <div>
              <h1 className="text-2xl font-semibold">AlphaStack - Technical Documentation</h1>
              <p className="text-muted-foreground">Grammar Agnostic Coding Agent</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={openInNewTab}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-muted hover:bg-muted/80 transition-colors"
            >
              {/* <ExternalLink className="w-4 h-4" /> */}
              {/* <span>Open PDF</span> */}
            </button>
            <button
              onClick={handleDownload}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
            >
              <Download className="w-4 h-4" />
              <span>Download</span>
            </button>
          </div>
        </div>

        {/* PDF Viewer Section */}
        <div className="bg-card border border-border rounded-lg overflow-hidden shadow-sm">
          <div className="bg-muted/50 px-4 py-3 border-b border-border">
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">Documentation Viewer</span>
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-red-500/60"></div>
                <div className="w-2 h-2 rounded-full bg-yellow-500/60"></div>
                <div className="w-2 h-2 rounded-full bg-green-500/60"></div>
              </div>
            </div>
          </div>

          <div className="relative min-h-[80vh] bg-white">
            {isLoading && (
              <div className="absolute inset-0 flex items-center justify-center bg-background">
                <div className="flex flex-col items-center gap-4">
                  <div className="w-8 h-8 border-2 border-muted-foreground border-t-transparent rounded-full animate-spin"></div>
                  <p className="text-muted-foreground">Loading documentation...</p>
                </div>
              </div>
            )}

            <iframe
              src="/alpha_stack_paper_draft2.pdf#toolbar=0&navpanes=0&scrollbar=1&view=FitH"
              className="w-full h-[80vh] border-0"
              title="AlphaStack Documentation"
              onLoad={() => setIsLoading(false)}
              onError={() => setIsLoading(false)}
            />
          </div>
        </div>
      </main>
    </div>
  )
}
