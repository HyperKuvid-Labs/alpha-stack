"use client"

import Image from "next/image"
import Link from "next/link"
import { StarsBackground } from "./stars-background"
import { TextGenerateEffect } from "./text-generate-effect"
import { MovingBorderButton } from "./moving-border-button"

export function HeroSection() {
  return (
    <section className="relative min-h-screen flex items-center justify-center overflow-hidden">
      <StarsBackground className="z-0" />

      <div className="relative z-10 max-w-5xl mx-auto px-6 text-center">
        {/* Logo */}
        <div className="mb-8 flex justify-center">
          <Image
            src="/images/screenshot-20from-202025-12-03-2002-42-54.png"
            alt="AlphaStack Logo"
            width={120}
            height={120}
            className="rounded-xl"
            priority
          />
        </div>

        {/* Title */}
        <h1 className="text-5xl md:text-7xl font-bold text-foreground mb-6">AlphaStack</h1>

        {/* Animated Tagline */}
        <div className="mb-8">
          <TextGenerateEffect
            words="Generate Production-Ready Projects with AI"
            className="text-xl md:text-2xl text-foreground/80"
          />
        </div>

        {/* Description */}
        <p className="text-lg text-foreground/60 max-w-2xl mx-auto mb-12">
          Transform natural language descriptions into complete, production-ready software projects. From Docker configs
          to automated testing, AlphaStack handles it all.
        </p>

        {/* CTA Buttons */}
        <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
          <MovingBorderButton as={Link} href="#installation">
            Get Started
          </MovingBorderButton>

          <Link
            href="https://github.com/alphastack"
            target="_blank"
            rel="noopener noreferrer"
            className="px-6 py-3 border border-foreground/30 rounded-full text-foreground hover:bg-foreground/10 transition-colors"
          >
            View on GitHub →
          </Link>
        </div>

        {/* Quick Install */}
        <div className="mt-12 inline-flex items-center gap-3 px-4 py-2 rounded-full border border-foreground/20 bg-background/50 backdrop-blur-sm">
          <span className="text-foreground/50 text-sm">$</span>
          <code className="text-foreground font-mono text-sm">pip install alphastack</code>
          <button
            onClick={() => navigator.clipboard.writeText("pip install alphastack")}
            className="text-foreground/50 hover:text-foreground transition-colors"
            aria-label="Copy install command"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
              />
            </svg>
          </button>
        </div>

        {/* Scroll Indicator */}
        <div className="absolute bottom-8 left-1/2 -translate-x-1/2 animate-bounce">
          <svg className="w-6 h-6 text-foreground/50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 14l-7 7m0 0l-7-7m7 7V3" />
          </svg>
        </div>
      </div>
    </section>
  )
}
