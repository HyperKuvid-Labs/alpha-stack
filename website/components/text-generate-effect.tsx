"use client"

import { useEffect, useState } from "react"
import { motion, stagger, useAnimate } from "framer-motion"
import { cn } from "@/lib/utils"

export function TextGenerateEffect({
  words,
  className,
  filter = true,
  duration = 0.5,
}: {
  words: string
  className?: string
  filter?: boolean
  duration?: number
}) {
  const [scope, animate] = useAnimate()
  const [hasAnimated, setHasAnimated] = useState(false)
  const wordsArray = words.split(" ")

  useEffect(() => {
    if (!hasAnimated) {
      animate(
        "span",
        {
          opacity: 1,
          filter: filter ? "blur(0px)" : "none",
        },
        {
          duration: duration,
          delay: stagger(0.1),
        },
      )
      setHasAnimated(true)
    }
  }, [animate, duration, filter, hasAnimated])

  return (
    <motion.div ref={scope} className={cn("font-bold", className)}>
      {wordsArray.map((word, idx) => (
        <motion.span
          key={word + idx}
          className="text-foreground opacity-0"
          style={{
            filter: filter ? "blur(10px)" : "none",
          }}
        >
          {word}{" "}
        </motion.span>
      ))}
    </motion.div>
  )
}
