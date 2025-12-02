"use client"

import type React from "react"
import { motion } from "framer-motion"
import { cn } from "@/lib/utils"

export function MovingBorderButton({
  children,
  className,
  containerClassName,
  borderClassName,
  duration = 2000,
  as: Component = "button",
  ...otherProps
}: {
  children: React.ReactNode
  className?: string
  containerClassName?: string
  borderClassName?: string
  duration?: number
  as?: React.ElementType
  [key: string]: unknown
}) {
  return (
    <Component className={cn("relative p-[1px] overflow-hidden group", containerClassName)} {...otherProps}>
      <motion.div
        className={cn("absolute inset-0", borderClassName)}
        style={{
          background: `linear-gradient(90deg, transparent, white, transparent)`,
        }}
        animate={{
          rotate: [0, 360],
        }}
        transition={{
          duration: duration / 1000,
          repeat: Number.POSITIVE_INFINITY,
          ease: "linear",
        }}
      />
      <div
        className={cn(
          "relative bg-background px-6 py-3 rounded-full text-foreground font-medium",
          "group-hover:bg-foreground group-hover:text-background transition-colors",
          className,
        )}
      >
        {children}
      </div>
    </Component>
  )
}
