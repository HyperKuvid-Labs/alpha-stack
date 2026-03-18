"use client"

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { Terminal } from "xterm"
import { FitAddon } from "xterm-addon-fit"
import "xterm/css/xterm.css"

type JobPayload = {
  status?: string
  success?: boolean
  error?: string
}

const DEFAULT_BACKEND = "http://127.0.0.1:8765"

export function ClaudeTerminal() {
  const terminalRootRef = useRef<HTMLDivElement | null>(null)
  const terminalRef = useRef<Terminal | null>(null)
  const fitAddonRef = useRef<FitAddon | null>(null)
  const frameRef = useRef<number | null>(null)
  const queueRef = useRef<string[]>([])
  const eventSourceRef = useRef<EventSource | null>(null)

  const [prompt, setPrompt] = useState("")
  const [outputDir, setOutputDir] = useState("./created_projects")
  const [provider, setProvider] = useState("openrouter")
  const [language, setLanguage] = useState<"cuda" | "others">("others")
  const [isRunning, setIsRunning] = useState(false)
  const [isConnected, setIsConnected] = useState(false)
  const [statusLine, setStatusLine] = useState("Waiting for backend")

  const backendUrl = useMemo(
    () => process.env.NEXT_PUBLIC_TERMINAL_BACKEND_URL || DEFAULT_BACKEND,
    [],
  )

  const enqueue = useCallback((chunk: string) => {
    if (!chunk) {
      return
    }
    queueRef.current.push(chunk)
  }, [])

  const startFrameLoop = useCallback(() => {
    const flush = () => {
      const term = terminalRef.current
      if (term && queueRef.current.length > 0) {
        const joined = queueRef.current.join("")
        queueRef.current = []
        term.write(joined)
      }
      frameRef.current = window.requestAnimationFrame(flush)
    }

    frameRef.current = window.requestAnimationFrame(flush)
  }, [])

  const stopFrameLoop = useCallback(() => {
    if (frameRef.current != null) {
      window.cancelAnimationFrame(frameRef.current)
      frameRef.current = null
    }
  }, [])

  useEffect(() => {
    const term = new Terminal({
      fontFamily: "Geist Mono, Menlo, Monaco, 'Courier New', monospace",
      fontSize: 14,
      lineHeight: 1.35,
      convertEol: true,
      cursorBlink: false,
      disableStdin: true,
      theme: {
        background: "#000000",
        foreground: "#f5f5f5",
        cursor: "#ffffff",
      },
    })

    const fitAddon = new FitAddon()
    term.loadAddon(fitAddon)

    if (terminalRootRef.current) {
      term.open(terminalRootRef.current)
      fitAddon.fit()
      term.writeln("AlphaStack Claude-style terminal")
      term.writeln("Connects to ANSI stream backend from src/tui.py")
      term.writeln("")
    }

    terminalRef.current = term
    fitAddonRef.current = fitAddon

    const onResize = () => {
      fitAddonRef.current?.fit()
    }

    window.addEventListener("resize", onResize)
    startFrameLoop()

    return () => {
      stopFrameLoop()
      window.removeEventListener("resize", onResize)
      eventSourceRef.current?.close()
      terminalRef.current?.dispose()
      terminalRef.current = null
      fitAddonRef.current = null
    }
  }, [startFrameLoop, stopFrameLoop])

  useEffect(() => {
    const streamUrl = `${backendUrl}/stream`
    const source = new EventSource(streamUrl)
    eventSourceRef.current = source

    source.onopen = () => {
      setIsConnected(true)
      setStatusLine("Connected")
    }

    source.onerror = () => {
      setIsConnected(false)
      setStatusLine("Disconnected")
    }

    source.addEventListener("terminal", (event) => {
      try {
        const payload = JSON.parse((event as MessageEvent<string>).data) as {
          data?: string
        }
        if (payload?.data) {
          enqueue(payload.data)
        }
      } catch {
        return
      }
    })

    source.addEventListener("job", (event) => {
      try {
        const payload = JSON.parse((event as MessageEvent<string>).data) as JobPayload
        if (payload.status === "started") {
          setIsRunning(true)
          setStatusLine("Running")
        } else if (payload.status === "finished") {
          setIsRunning(false)
          setStatusLine(payload.success ? "Finished successfully" : "Finished with issues")
        } else if (payload.status === "failed") {
          setIsRunning(false)
          setStatusLine(payload.error ? `Failed: ${payload.error}` : "Failed")
        }
      } catch {
        return
      }
    })

    return () => {
      source.close()
    }
  }, [backendUrl, enqueue])

  const runPrompt = useCallback(async () => {
    const cleanPrompt = prompt.trim()
    if (!cleanPrompt || isRunning) {
      return
    }

    setStatusLine("Submitting job")

    const response = await fetch(`${backendUrl}/run`, {
      method: "POST",
      headers: {
        "content-type": "application/json",
      },
      body: JSON.stringify({
        prompt: cleanPrompt,
        output_dir: outputDir,
        provider,
        language,
      }),
    })

    if (!response.ok) {
      const errorPayload = await response.json().catch(() => ({ error: "Request failed" }))
      setStatusLine(errorPayload.error || "Request failed")
      return
    }

    setPrompt("")
  }, [backendUrl, isRunning, language, outputDir, prompt, provider])

  return (
    <div className="mx-auto flex h-screen w-full max-w-6xl flex-col px-4 py-4">
      <div className="border-border mb-3 border-b pb-3 text-sm">
        <div className="text-foreground font-semibold">Claude Code v0.24.0</div>
        <div className="text-muted-foreground">AlphaStack terminal session</div>
        <div className="text-muted-foreground">{backendUrl}</div>
      </div>

      <div className="border-border bg-background min-h-0 flex-1 overflow-hidden rounded-md border">
        <div ref={terminalRootRef} className="h-full w-full" />
      </div>

      <div className="border-border mt-3 border-t pt-3">
        <div className="text-muted-foreground mb-2 text-xs">● {statusLine}</div>
        <div className="grid grid-cols-1 gap-2 md:grid-cols-4">
          <input
            value={outputDir}
            onChange={(e) => setOutputDir(e.target.value)}
            className="border-input bg-background text-foreground rounded border px-2 py-1 text-sm"
            placeholder="Output directory"
          />
          <input
            value={provider}
            onChange={(e) => setProvider(e.target.value)}
            className="border-input bg-background text-foreground rounded border px-2 py-1 text-sm"
            placeholder="Provider"
          />
          <select
            value={language}
            onChange={(e) => setLanguage((e.target.value as "cuda" | "others") || "others")}
            className="border-input bg-background text-foreground rounded border px-2 py-1 text-sm"
          >
            <option value="others">others</option>
            <option value="cuda">cuda</option>
          </select>
          <button
            type="button"
            onClick={runPrompt}
            disabled={!isConnected || isRunning || !prompt.trim()}
            className="border-input bg-background text-foreground disabled:text-muted-foreground rounded border px-2 py-1 text-sm"
          >
            {isRunning ? "Running" : "Run"}
          </button>
        </div>

        <div className="mt-2 flex items-center gap-2 text-sm">
          <span className="text-muted-foreground">&gt;</span>
          <input
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                void runPrompt()
              }
            }}
            className="border-input bg-background text-foreground w-full rounded border px-2 py-1"
            placeholder="Describe what you want to build"
          />
        </div>
        <div className="text-muted-foreground mt-3 flex items-center justify-between border-t pt-2 text-xs">
          <span>? for shortcuts</span>
          <span>Thinking off (tab to toggle)</span>
        </div>
      </div>
    </div>
  )
}
