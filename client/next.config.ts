import type { NextConfig } from "next";

const backendHost = process.env.BACKEND_HOST || "127.0.0.1";
const backendPort = process.env.BACKEND_PORT || "3000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `http://${backendHost}:${backendPort}/:path*`,
      },
    ];
  },
};

export default nextConfig;
