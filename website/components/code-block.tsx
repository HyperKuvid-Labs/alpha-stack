"use client"

import { useState } from "react"
import { Check, Copy } from "lucide-react"
import { cn } from "@/lib/utils"

export function CodeBlock({
  code,
  language = "bash",
  className,
}: {
  code: string
  language?: string
  className?: string
}) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    await navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div
      className={cn("relative group rounded-lg border border-foreground/20 bg-background overflow-hidden", className)}
    >
      <div className="flex items-center justify-between px-4 py-2 border-b border-foreground/20">
        <span className="text-xs text-foreground/50 font-mono">{language}</span>
        <button
          onClick={handleCopy}
          className="p-1 rounded hover:bg-foreground/10 transition-colors"
          aria-label="Copy code"
        >
          {copied ? <Check className="w-4 h-4 text-foreground" /> : <Copy className="w-4 h-4 text-foreground/50" />}
        </button>
      </div>
      <pre className="p-4 overflow-x-auto">
        <code className="text-sm font-mono text-foreground">{code}</code>
      </pre>
    </div>
  )
}
