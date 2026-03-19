#!/usr/bin/env bash
set -euo pipefail

REMOTE_USER="x-kozler"
REMOTE_HOST="anvil.rcac.purdue.edu"
REMOTE_PATH="/anvil/projects/x-cis251377/x-kozler/repositories/any-llm-inference/"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCAL_PATH="$(dirname "$SCRIPT_DIR")/"

rsync -avz --progress \
    "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}outputs/" "${LOCAL_PATH}outputs/"

rsync -avz --progress \
    "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}logs/" "${LOCAL_PATH}logs/"
