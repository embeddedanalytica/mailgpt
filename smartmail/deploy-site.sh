#!/usr/bin/env bash
set -euo pipefail

# Deploy static frontend files to S3.
# Default target is the live website bucket used in this repo.

BUCKET="${1:-geniml.com}"
INVALIDATE_DIST_ID="${2:-}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INDEX_FILE="$ROOT_DIR/index.html"
API_FILE="$ROOT_DIR/api.js"

if ! command -v aws >/dev/null 2>&1; then
  echo "Error: aws CLI is not installed or not in PATH." >&2
  exit 1
fi

if [[ ! -f "$INDEX_FILE" ]]; then
  echo "Error: $INDEX_FILE not found." >&2
  exit 1
fi

if [[ ! -f "$API_FILE" ]]; then
  echo "Error: $API_FILE not found." >&2
  exit 1
fi

echo "Uploading to s3://$BUCKET ..."
aws s3 cp "$INDEX_FILE" "s3://$BUCKET/index.html" --content-type text/html
aws s3 cp "$API_FILE" "s3://$BUCKET/api.js" --content-type application/javascript

echo "Done uploading index.html and api.js to s3://$BUCKET"

if [[ -n "$INVALIDATE_DIST_ID" ]]; then
  echo "Creating CloudFront invalidation for distribution $INVALIDATE_DIST_ID ..."
  aws cloudfront create-invalidation \
    --distribution-id "$INVALIDATE_DIST_ID" \
    --paths "/index.html" "/api.js" "/"
  echo "Invalidation submitted."
fi
