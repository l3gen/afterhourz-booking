#!/usr/bin/env bash
# Rewrites the placeholder domain in the SEO files for the environment being deployed, and makes
# sure non-production environments are invisible to Google.
#   usage: prepare-seo.sh https://www.yourdomain.com prod|dev
set -euo pipefail
SITE_URL="${1%/}"
ENV_NAME="${2:?env required}"
cd "$(dirname "$0")/.."

sed -i "s|https://www.example.com|${SITE_URL}|g" index.html public/robots.txt public/sitemap.xml

if [ "$ENV_NAME" != "prod" ]; then
  printf 'User-agent: *\nDisallow: /\n' > public/robots.txt
  rm -f public/sitemap.xml
  sed -i 's|<meta name="viewport"[^>]*>|&\n    <meta name="robots" content="noindex, nofollow" />|' index.html
fi
echo "SEO files prepared for ${ENV_NAME} at ${SITE_URL}"
