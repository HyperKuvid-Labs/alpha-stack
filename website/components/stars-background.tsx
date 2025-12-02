"use client"

import { useEffect, useRef, useState } from "react"
import { cn } from "@/lib/utils"

interface Star {
  x: number
  y: number
  radius: number
  opacity: number
  twinkleSpeed: number | null
}

interface ShootingStar {
  x: number
  y: number
  length: number
  speed: number
  angle: number
  opacity: number
}

export function StarsBackground({
  className,
  starDensity = 0.00015,
  allStarsTwinkle = true,
  twinkleProbability = 0.7,
  minTwinkleSpeed = 0.5,
  maxTwinkleSpeed = 1,
  shootingStarSpeed = 15,
  shootingStarMinDelay = 1200,
  shootingStarMaxDelay = 4200,
}: {
  className?: string
  starDensity?: number
  allStarsTwinkle?: boolean
  twinkleProbability?: number
  minTwinkleSpeed?: number
  maxTwinkleSpeed?: number
  shootingStarSpeed?: number
  shootingStarMinDelay?: number
  shootingStarMaxDelay?: number
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [stars, setStars] = useState<Star[]>([])
  const [shootingStars, setShootingStars] = useState<ShootingStar[]>([])
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 })

  useEffect(() => {
    const handleResize = () => {
      if (canvasRef.current) {
        const { width, height } = canvasRef.current.getBoundingClientRect()
        setDimensions({ width, height })
      }
    }
    handleResize()
    window.addEventListener("resize", handleResize)
    return () => window.removeEventListener("resize", handleResize)
  }, [])

  useEffect(() => {
    const generateStars = () => {
      const { width, height } = dimensions
      const starCount = Math.floor(width * height * starDensity)
      const newStars: Star[] = []

      for (let i = 0; i < starCount; i++) {
        const shouldTwinkle = allStarsTwinkle || Math.random() < twinkleProbability
        newStars.push({
          x: Math.random() * width,
          y: Math.random() * height,
          radius: Math.random() * 1.5 + 0.5,
          opacity: Math.random() * 0.5 + 0.5,
          twinkleSpeed: shouldTwinkle ? minTwinkleSpeed + Math.random() * (maxTwinkleSpeed - minTwinkleSpeed) : null,
        })
      }
      setStars(newStars)
    }

    if (dimensions.width > 0 && dimensions.height > 0) {
      generateStars()
    }
  }, [dimensions, starDensity, allStarsTwinkle, twinkleProbability, minTwinkleSpeed, maxTwinkleSpeed])

  useEffect(() => {
    const createShootingStar = () => {
      const { width, height } = dimensions
      if (width === 0 || height === 0) return

      const newStar: ShootingStar = {
        x: Math.random() * width,
        y: 0,
        length: Math.random() * 80 + 60,
        speed: shootingStarSpeed,
        angle: Math.PI / 4 + (Math.random() * Math.PI) / 6,
        opacity: 1,
      }
      setShootingStars((prev) => [...prev, newStar])
    }

    const scheduleShootingStar = () => {
      const delay = shootingStarMinDelay + Math.random() * (shootingStarMaxDelay - shootingStarMinDelay)
      setTimeout(() => {
        createShootingStar()
        scheduleShootingStar()
      }, delay)
    }

    if (dimensions.width > 0) {
      scheduleShootingStar()
    }
  }, [dimensions, shootingStarSpeed, shootingStarMinDelay, shootingStarMaxDelay])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext("2d")
    if (!ctx) return

    canvas.width = dimensions.width
    canvas.height = dimensions.height

    let animationId: number

    const animate = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height)

      // Draw stars
      stars.forEach((star, index) => {
        ctx.beginPath()
        ctx.arc(star.x, star.y, star.radius, 0, Math.PI * 2)
        ctx.fillStyle = `rgba(255, 255, 255, ${star.opacity})`
        ctx.fill()

        if (star.twinkleSpeed !== null) {
          stars[index].opacity = 0.5 + Math.abs(Math.sin(Date.now() * star.twinkleSpeed * 0.001)) * 0.5
        }
      })

      // Draw and update shooting stars
      setShootingStars((prev) => {
        return prev
          .map((star) => {
            ctx.beginPath()
            ctx.moveTo(star.x, star.y)
            const endX = star.x + Math.cos(star.angle) * star.length
            const endY = star.y + Math.sin(star.angle) * star.length

            const gradient = ctx.createLinearGradient(star.x, star.y, endX, endY)
            gradient.addColorStop(0, `rgba(255, 255, 255, ${star.opacity})`)
            gradient.addColorStop(1, "rgba(255, 255, 255, 0)")

            ctx.strokeStyle = gradient
            ctx.lineWidth = 2
            ctx.lineTo(endX, endY)
            ctx.stroke()

            return {
              ...star,
              x: star.x + Math.cos(star.angle) * star.speed,
              y: star.y + Math.sin(star.angle) * star.speed,
              opacity: star.opacity - 0.008,
            }
          })
          .filter(
            (star) => star.opacity > 0 && star.x < canvas.width + star.length && star.y < canvas.height + star.length,
          )
      })

      animationId = requestAnimationFrame(animate)
    }

    animate()

    return () => {
      cancelAnimationFrame(animationId)
    }
  }, [stars, dimensions])

  return <canvas ref={canvasRef} className={cn("absolute inset-0 h-full w-full bg-background", className)} />
}
