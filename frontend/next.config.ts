import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.BACKEND_URL || "http://localhost:8000"}/api/:path*`,
      },
    ];
  },
  experimental: {
    optimizePackageImports: [
      "@radix-ui/react-tooltip",
      "@radix-ui/react-dialog",
      "@radix-ui/react-select",
      "lucide-react",
      "class-variance-authority",
    ],
    // BUG-054: idle timeout (ms) of the /api rewrite proxy. A cold model load is
    // ~30 s of silence, which the 30 s default cut off. Keep a finite number:
    // 0 falls back to 30000, null is dropped, Infinity dies in JSON.stringify.
    proxyTimeout: 600_000,
    // BUG-040: 100 MiB, equal to the backend max_upload_size_mb. The 10 MiB
    // default truncated every proxied upload body.
    proxyClientMaxBodySize: 104_857_600,
  },
};

export default nextConfig;
