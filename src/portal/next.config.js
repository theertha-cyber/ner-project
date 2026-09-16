/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  async redirects() {
    return [
      { source: "/schema-proposals", destination: "/annotate/automated/schema", permanent: false },
      { source: "/prelabel-batches", destination: "/annotate/automated/prelabel", permanent: false },
      { source: "/retraining", destination: "/annotate/automated/retrain", permanent: false },
    ];
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
