import Image from "next/image"
import Link from "next/link"

export function Footer() {
  return (
    <footer className="py-12 px-6 border-t border-white/10">
      <div className="max-w-5xl mx-auto">
        <div className="flex flex-col md:flex-row items-center justify-between gap-6">
          {/* Logo & Copyright */}
          <div className="flex items-center gap-3">
            <Image
              src="/images/screenshot-20from-202025-12-03-2002-42-54.png"
              alt="AlphaStack Logo"
              width={28}
              height={28}
              className="rounded opacity-80"
            />
            <span className="text-white/50 text-sm">© 2025 AlphaStack. MIT License.</span>
          </div>

          {/* Links */}
          <div className="flex items-center gap-6">
            <Link
              href="https://github.com/HyperKuvid-Labs/alpha-stack"
              target="_blank"
              rel="noopener noreferrer"
              className="text-white/50 hover:text-white/70 transition-colors text-sm"
            >
              GitHub
            </Link>
            <Link href="#docs" className="text-white/50 hover:text-white/70 transition-colors text-sm">
              Documentation
            </Link>
            <Link
              href="https://github.com/HyperKuvid-Labs/alpha-stack/issues"
              target="_blank"
              rel="noopener noreferrer"
              className="text-white/50 hover:text-white/70 transition-colors text-sm"
            >
              Issues
            </Link>
          </div>
        </div>
      </div>
    </footer>
  )
}
