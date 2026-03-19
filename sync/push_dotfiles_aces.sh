#!/usr/bin/env bash
set -euo pipefail

REMOTE_HOST="aces"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$(dirname "$SCRIPT_DIR")/dotfiles/aces"

rsync -avz --progress \
    "$DOTFILES_DIR/.bashrc" "${REMOTE_HOST}:~/.bashrc"

rsync -avz --progress \
    "$DOTFILES_DIR/.bash_env" "${REMOTE_HOST}:~/.bash_env"
