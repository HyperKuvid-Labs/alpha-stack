import { FloatingNavbar } from "@/components/floating-navbar"
import { HeroSection } from "@/components/hero-section"
import { FeaturesSection } from "@/components/features-section"
import { InstallationSection } from "@/components/installation-section"
import { UsageSection } from "@/components/usage-section"
import { RoadmapSection } from "@/components/roadmap-section"
import { Footer } from "@/components/footer"

export default function Home() {
  return (
    <main className="bg-background min-h-screen">
      <FloatingNavbar />
      <HeroSection />
      <FeaturesSection />
      <InstallationSection />
      <UsageSection />
      <RoadmapSection />
      <Footer />
    </main>
  )
}
