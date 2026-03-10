#!/bin/bash

# Simple script to sync backend changes to git
cd "$(dirname "$0")"

# Update from remote
git pull origin main

# Add all changes
git add .

# Prompt for message or use default
if [ -z "$1" ]; then
  COMMIT_MSG="Auto-commit: sync latest updates $(date +'%Y-%m-%d %H:%M:%S')"
else
  COMMIT_MSG="$1"
fi

git commit -m "$COMMIT_MSG"

# Push to remote
git push origin main

echo "Backend sync complete!"
