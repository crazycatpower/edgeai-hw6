#!/usr/bin/env bash
# Copyright (c) 2026 <Your Name(s)>
# Tatung University — I4210 AI實務專題

set -euo pipefail

exec python3 -m src.inference_node "$@"
