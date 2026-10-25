import type { NextConfig } from "next";

// Fully static: the build is plain files in out/, served from S3 via CloudFront.
const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
  reactStrictMode: true,
};

export default nextConfig;
