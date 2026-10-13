import type { NextConfig } from "next";

// Static export for GitHub Pages (public repo azzammasood/roshni-site). The publish workflow sets
// NEXT_PUBLIC_BASE_PATH=/roshni-site;
// local builds serve from the root.
const basePath = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

const nextConfig: NextConfig = {
  output: "export",
  basePath,
  trailingSlash: true,
  images: { unoptimized: true },
  // The root layout is app/[lang]/layout.tsx, so the site-wide 404 is app/global-not-found.tsx.
  experimental: { globalNotFound: true },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
