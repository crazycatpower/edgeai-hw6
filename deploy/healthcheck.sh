#!/usr/bin/env bash
# Copyright (c) 2026 <Your Name(s)>
# Tatung University — I4210 AI實務專題

set -euo pipefail

HOST="${HEALTHCHECK_HOST:-localhost}"
PORT="${HEALTHCHECK_PORT:-8000}"
URL="http://${HOST}:${PORT}/healthz"
TIMEOUT=60
REQUIRED_CONSECUTIVE=3
consecutive=0
elapsed=0
interval=3

echo "[healthcheck] Polling ${URL} (need ${REQUIRED_CONSECUTIVE} consecutive successes within ${TIMEOUT}s)"

while [ "$elapsed" -lt "$TIMEOUT" ]; do
    if curl -sf --max-time 3 "${URL}" > /dev/null 2>&1; then
        consecutive=$((consecutive + 1))
        echo "[healthcheck] Success ${consecutive}/${REQUIRED_CONSECUTIVE} (${elapsed}s elapsed)"
        if [ "$consecutive" -ge "$REQUIRED_CONSECUTIVE" ]; then
            echo "[healthcheck] Health check passed"
            exit 0
        fi
    else
        consecutive=0
        echo "[healthcheck] Failed (${elapsed}s elapsed), resetting counter"
    fi
    sleep "$interval"
    elapsed=$((elapsed + interval))
done

echo "[healthcheck] TIMEOUT after ${TIMEOUT}s — service did not become healthy"
exit 1
