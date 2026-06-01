import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  devIndicators: false,
  transpilePackages: ["@monaco-editor/react"],
};

export default nextConfig;
