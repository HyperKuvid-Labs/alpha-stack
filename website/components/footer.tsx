import Image from "next/image"
import Link from "next/link"

export function Footer() {
  return (
    <footer className="py-12 px-6 bg-background border-t border-foreground/10">
      <div className="max-w-6xl mx-auto">
        <div className="flex flex-col md:flex-row items-center justify-between gap-6">
          {/* Logo & Copyright */}
          <div className="flex items-center gap-3">
            <Image
              src="/images/screenshot-20from-202025-12-03-2002-42-54.png"
              alt="AlphaStack Logo"
              width={32}
              height={32}
              className="rounded"
            />
            <span className="text-foreground/60 text-sm">© 2025 AlphaStack. MIT License.</span>
          </div>

          {/* Links */}
          <div className="flex items-center gap-6">
            <Link
              href="https://github.com/alphastack"
              target="_blank"
              rel="noopener noreferrer"
              className="text-foreground/60 hover:text-foreground transition-colors text-sm"
            >
              GitHub
            </Link>
            <Link href="#docs" className="text-foreground/60 hover:text-foreground transition-colors text-sm">
              Documentation
            </Link>
            <Link
              href="https://github.com/alphastack/alphastack/issues"
              target="_blank"
              rel="noopener noreferrer"
              className="text-foreground/60 hover:text-foreground transition-colors text-sm"
            >
              Issues
            </Link>
            <Link
              href="https://discord.gg/alphastack"
              target="_blank"
              rel="noopener noreferrer"
              className="text-foreground/60 hover:text-foreground transition-colors text-sm"
            >
              Discord
            </Link>
          </div>
        </div>
      </div>
    </footer>
  )
}
