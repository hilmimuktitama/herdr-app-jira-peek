#!/bin/sh
# Enable the tracked pre-push hook for this checkout. Run once per clone.
set -eu
root=$(git rev-parse --show-toplevel)
chmod +x "$root/.githooks/pre-push"
# Relative so every worktree resolves its own .githooks directory.
git -C "$root" config core.hooksPath .githooks
printf 'Enabled %s\n' "$root/.githooks/pre-push"
