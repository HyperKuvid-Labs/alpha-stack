"use client"

import type React from "react"

import { useMotionValue, motion, useMotionTemplate } from "framer-motion"
import { cn } from "@/lib/utils"
import type { MouseEvent } from "react"

export function CardSpotlight({
  children,
  className,
}: {
  children: React.ReactNode
  className?: string
}) {
  const mouseX = useMotionValue(0)
  const mouseY = useMotionValue(0)

  function handleMouseMove({ currentTarget, clientX, clientY }: MouseEvent) {
    const { left, top } = currentTarget.getBoundingClientRect()
    mouseX.set(clientX - left)
    mouseY.set(clientY - top)
  }

  return (
    <div
      className={cn(
        "group relative rounded-xl border border-foreground/20 bg-background p-6",
        "hover:border-foreground/40 transition-colors",
        className,
      )}
      onMouseMove={handleMouseMove}
    >
      <motion.div
        className="pointer-events-none absolute -inset-px rounded-xl opacity-0 group-hover:opacity-100 transition-opacity"
        style={{
          background: useMotionTemplate`
            radial-gradient(
              350px circle at ${mouseX}px ${mouseY}px,
              rgba(255, 255, 255, 0.06),
              transparent 80%
            )
          `,
        }}
      />
      {children}
    </div>
  )
}
