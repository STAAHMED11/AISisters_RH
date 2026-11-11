import type { NextConfig } from 'next'

// Flask API (backend/). In Docker/Modal both run in the same container; in dev, `flask run` / gunicorn on :8000.
// Rewrites are resolved at BUILD time (baked into the routes manifest): set API_URL before `next build`, not at start.
const API_URL = process.env.API_URL ?? 'http://127.0.0.1:8000'

const nextConfig: NextConfig = {
  output: 'standalone',      // self-contained server.js for the Docker image
  poweredByHeader: false,
  // The browser only ever talks to Next: /api/* is proxied to Flask (same origin => the session cookie just works).
  async rewrites() {
    return [{ source: '/api/:path*', destination: `${API_URL}/api/:path*` }]
  },
  experimental: {
    proxyTimeout: 300_000,   // same as gunicorn's --timeout: creating an offer / preparing an interview waits for the LLM
  },
}

export default nextConfig
