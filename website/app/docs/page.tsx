"use client"

import { useState, useEffect } from "react"
import dynamicImport from "next/dynamic"
import { ZoomIn, ZoomOut, Loader2, Home } from "lucide-react"
import { Button } from "@/components/ui/button"
import Link from "next/link"

// Dynamically import react-pdf components with SSR disabled
const Document = dynamicImport(
  () => import("react-pdf").then((mod) => mod.Document),
  { ssr: false }
)

const Page = dynamicImport(
  () => import("react-pdf").then((mod) => mod.Page),
  { ssr: false }
)

export default function DocsPage() {
  const [numPages, setNumPages] = useState<number>(0)
  const [scale, setScale] = useState<number>(1.0)
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    // Configure worker only on client side
    import("react-pdf").then((pdfjs) => {
      pdfjs.pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.pdfjs.version}/build/pdf.worker.min.mjs`
    })
    setMounted(true)
  }, [])

  function onDocumentLoadSuccess({ numPages }: { numPages: number }) {
    setNumPages(numPages)
  }

  if (!mounted) {
    return (
      <div className="flex items-center justify-center h-screen w-full bg-gradient-to-br from-background via-background to-muted/20">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <p className="text-muted-foreground font-medium">Loading documentation...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-screen w-full bg-gradient-to-br from-background via-background to-muted/20">
      {/* Toolbar */}
      <div className="bg-background/95 backdrop-blur-md border-b border-foreground/10 p-4 flex items-center justify-between z-10 sticky top-0 shadow-sm">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="icon"
            asChild
            className="h-9 w-9 hover:bg-foreground/10"
          >
            <Link href="/">
              <Home className="h-5 w-5" />
            </Link>
          </Button>
          <h1 className="font-bold text-xl bg-gradient-to-r from-foreground to-foreground/70 bg-clip-text text-transparent">
            Technical Documentation
          </h1>
          <span className="text-sm text-muted-foreground">
            {numPages ? `${numPages} pages` : "Loading..."}
          </span>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1 bg-foreground/5 rounded-lg p-1 border border-foreground/10">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setScale((prev) => Math.max(0.5, prev - 0.1))}
              className="h-8 w-8 hover:bg-foreground/10"
            >
              <ZoomOut className="h-4 w-4" />
            </Button>
            <span className="text-sm font-semibold w-16 text-center">{Math.round(scale * 100)}%</span>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setScale((prev) => Math.min(2.5, prev + 0.1))}
              className="h-8 w-8 hover:bg-foreground/10"
            >
              <ZoomIn className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>

      {/* PDF Viewer Container */}
      <div className="flex-1 flex items-center justify-center p-8 overflow-hidden">
        <div className="w-full max-w-5xl h-full flex flex-col">
          {/* Custom PDF Box */}
          <div className="flex-1 bg-background/50 backdrop-blur-sm rounded-2xl border-2 border-foreground/10 shadow-2xl overflow-hidden flex flex-col">
            <div className="flex-1 overflow-auto custom-scrollbar p-6">
              <div className="flex flex-col items-center gap-4">
                <Document
                  file="/alpha_stack_paper_draft2.pdf"
                  onLoadSuccess={onDocumentLoadSuccess}
                  loading={
                    <div className="flex items-center justify-center h-96 w-[600px]">
                      <div className="flex flex-col items-center gap-4">
                        <Loader2 className="h-8 w-8 animate-spin text-primary" />
                        <p className="text-muted-foreground font-medium">Loading documentation...</p>
                      </div>
                    </div>
                  }
                  error={
                    <div className="flex items-center justify-center h-96 w-[600px]">
                      <p className="text-destructive font-medium">Failed to load PDF file.</p>
                    </div>
                  }
                >
                  {Array.from(new Array(numPages), (el, index) => (
                    <Page
                      key={`page_${index + 1}`}
                      pageNumber={index + 1}
                      scale={scale}
                      renderTextLayer={true}
                      renderAnnotationLayer={true}
                      className="shadow-lg rounded-lg overflow-hidden border border-foreground/10 mb-4"
                    />
                  ))}
                </Document>
              </div>
            </div>
          </div>
        </div>
      </div>

      <style jsx global>{`
        .custom-scrollbar::-webkit-scrollbar {
          width: 14px;
          height: 14px;
        }

        .custom-scrollbar::-webkit-scrollbar-track {
          background: #1a1a1a;
          border-radius: 10px;
        }

        .custom-scrollbar::-webkit-scrollbar-thumb {
          background: #4a4a4a;
          border-radius: 10px;
          border: 3px solid #1a1a1a;
        }

        .custom-scrollbar::-webkit-scrollbar-thumb:hover {
          background: #666666;
        }

        .custom-scrollbar {
          scrollbar-width: thin;
          scrollbar-color: #4a4a4a #1a1a1a;
        }
      `}</style>
    </div>
  )
}
