/** @type {import('next').NextConfig} */
const nextConfig = {
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
  // Ensure static files are served correctly
  async headers() {
    return [
      {
        source: '/alpha_stack_paper_draft2.pdf',
        headers: [
          {
            key: 'Content-Type',
            value: 'application/pdf',
          },
          {
            key: 'Content-Disposition',
            value: 'inline',
          },
        ],
      },
    ]
  },
  // Trailing slash handling for consistent URLs
  trailingSlash: false,
}

export default nextConfig