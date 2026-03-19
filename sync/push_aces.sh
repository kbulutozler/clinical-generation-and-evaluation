#!/usr/bin/env bash
set -euo pipefail

REMOTE_HOST="aces"
REMOTE_PATH="/scratch/group/p.cis251377.000/u.ko341547/repositories/any-llm-inference/"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCAL_PATH="$(dirname "$SCRIPT_DIR")/"

rsync -avz --delete --progress \
    --exclude='.claude/' \
    --exclude='outputs/' \
    --exclude='logs/' \
    "$LOCAL_PATH" "${REMOTE_HOST}:${REMOTE_PATH}"
