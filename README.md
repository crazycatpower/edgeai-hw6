# EdgeAI HW6 — Production CI/CD Pipeline

> **Course**: I4210 AI實務專題, Tatung University  
> **Deadline**: 2026-05-26 23:59  
> **Team**: 2 members (continuing from Lab 11/12)

---

## Operations

### Quickstart

```bash
# Clone and install dependencies
git clone https://github.com/crazycatpower/edgeai-hw6
cd edgeai-hw6
pip install -r requirements.txt

# Run tests locally
pytest tests/ --ignore=tests/integration --cov=src --cov-fail-under=90

# Run all CI checks
pdm run ci
```

### Deploy

Deployments are triggered automatically by pushing a semver tag:

```bash
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0
```

This triggers the deploy workflow which:
1. Re-tags the existing image (no rebuild)
2. Requires approval from a designated reviewer (production environment)
3. SSHes into Jetson and runs `deploy/deploy.sh`

To deploy manually on the Jetson:

```bash
export IMAGE_TAG=v1.0.0
bash deploy/deploy.sh
```

### How to Roll Back

**When to rollback** (symptoms):
- `healthcheck.sh` fails after deployment (returns exit code 1)
- mAP@50 drops >5% compared to baseline
- Container enters restart loop (`docker ps` shows multiple restarts)
- `/healthz` returns non-200 or wrong `model_version`

**Exact command:**

```bash
time bash deploy/rollback.sh
```

Expected wall time: **< 30 seconds**

**How to find the previous tag:**

```bash
cat /var/lib/edgeai-hw6/deployed.txt         # current
cat /var/lib/edgeai-hw6/deployed.txt.history  # previous
```

**If both tags are broken:**

```bash
# Find a known-good tag from the GitHub releases page
export IMAGE_TAG=v0.9.0
cd deploy && docker compose pull && docker compose up -d --force-recreate
```

**Who to notify:**

- Slack: `#edgeai-alerts` — `@oncall: rollback initiated on <hostname>, tag reverted to <old_tag>`
- Email: `team@example.com` — Subject: `[ALERT] EdgeAI Rollback on <hostname>`

---

## Architecture

```
git push / PR
     │
     ▼
┌──────────┐
│   lint   │  ruff format + ruff check
└────┬─────┘
     │
 ┌───┴──────────┐
 ▼              ▼
┌──────┐  ┌────────────┐
│ test │  │security-   │  bandit + pip-audit
│(90%) │  │  scan      │
└──┬───┘  └─────┬──────┘
   └──────┬─────┘
          ▼
     ┌─────────┐
     │  build  │  docker buildx → GHCR
     └────┬────┘
          │
          ▼
 ┌─────────────────┐
 │ integration-    │  Jetson self-hosted runner
 │    test         │  (main branch only)
 └─────────────────┘
```

**What we intentionally did NOT do:**
- No separate staging environment (single Jetson, cost constraint)
- No blue-green deployment (volume pinning makes this complex)
- No automatic rollback on mAP regression (requires offline eval pipeline)

---

## Optimization (INT8 vs FP16)

| Metric        | FP16     | INT8     | Change   |
|---------------|----------|----------|----------|
| mAP@50        | 0.7200   | 0.7050   | -1.50%   |
| Latency (ms)  | ~45      | ~22      | -51%     |
| GPU Memory    | ~28 MB   | ~7 MB    | -75%     |
| Throughput    | ~22 fps  | ~45 fps  | +105%    |

**Production Recommendation**: Use INT8. The 1.5% mAP drop is within the 2% acceptance threshold. The 2× speedup and 75% memory reduction are critical for real-time processing on Jetson Orin Nano 8GB, especially when running multiple inference streams.

**Calibration**: Used ~500 representative frames from the HW5 test dataset covering varied lighting, occlusion, and skin tone conditions. See `calibration/README.md` for re-calibration steps.

---

## Scaling to a Fleet

For N Jetson devices:

1. **Registry**: Use GHCR with per-device tags (`sha-<short>-<device-id>`) or a shared `latest` tag.
2. **Orchestration**: Ansible playbook calling `deploy.sh` with `--limit jetson_fleet` across all nodes in parallel.
3. **Canary rollout**: Deploy to 10% of fleet first, monitor MQTT message rate and `/healthz` for 5 minutes, then roll out to the rest.
4. **Tools**:
   - Ansible for configuration management and rolling deploys
   - Prometheus + Grafana for fleet-wide latency/throughput dashboards
   - Alertmanager for automatic rollback triggers based on error rate
5. **State management**: Centralized `/var/lib/edgeai-hw6/deployed.txt` per node; aggregated in a Redis store for fleet visibility.

---

## Reflections

### 黃義鈞

**負責部分**：Part 0（INT8 TensorRT 校準與 engine 產出）、Part C（Jetson 硬體環境準備、self-hosted runner 安裝與維護）、Part D（GitHub Secrets 設定、production environment required reviewers、deploy 人工審批）、Part E（rollback 實機驗證）、整體 Jetson 硬體操作與網路環境排除

**最困難的技術問題**：學校網路有 captive portal，Jetson runner 無法直接連上 GitHub。一開始嘗試在 runner 設定 `HTTPS_PROXY=socks5://127.0.0.1:1080`，搭配 SSH reverse tunnel 從筆電橋接出去，但 Node.js 24 的 undici 不支援 `socks5://` scheme，導致 `actions/checkout` 一直失敗。後來發現 Jetson 其實可以直接繞過 captive portal 連到 GitHub，把 proxy 移掉之後 runner 才正常上線。

**學到的事**：Self-hosted runner 的網路環境和開發機完全不同，不能想當然爾。`GITHUB_ACTIONS_RUNNER_TLS_NO_VERIFY=1` 可以讓 runner registration 跳過 SSL 檢查，但 job 執行時 `actions/checkout` 用的是 Node.js 內建的 HTTP client，設定方式完全不同。另外 INT8 校準時 `trtexec` 在 Jetson 上跑要用 DeepStream container 才有完整的 TRT 環境，直接裝 onnxruntime 是不夠的。

**下次會不同的做法**：第一天就先確認 runner 能不能連到 GitHub，再開始寫任何 workflow。這次花了將近一整天在排查網路問題，才發現根本原因只是 proxy 設定衝突。如果一開始先用 `curl https://github.com` 在 Jetson 上測一下連線，可以省掉大量時間。

---

### 李軒杰

**Parts completed**: Part B（CI workflow 五段圖修正與 ARM64 交叉編譯設定）、Part C（integration test 診斷與修正）、Part D（deploy.yml 建置與 SSH 部署邏輯）、Part E（rollback.sh 串接）、Part F（文件合規審查與 Submission Evidence）、Code Quality（bandit 設定、paho-mqtt 2.x API 修正、ruff 合規維護）

**Hardest technical problem**: Integration test 連續失敗了三輪。第一輪是 `Connection refused`，完全看不出原因；第二輪才在 test fixture 裡加入 `docker logs` 診斷，才發現是 paho-mqtt 2.0 把 `mqtt.Client(client_id)` 改成需要顯式傳入 `callback_api_version`，導致 `InferenceNode()` 的 constructor 直接拋 `ValueError`，整個 container process 崩潰，healthz daemon thread 跟著消失，所以一直是 Connection refused。關鍵修正是把 `InferenceNode()` 建構也包進 `try/except`，確保 constructor 失敗時 process 依然存活、healthz 繼續回應。

**What I learned**: `bandit -r src/ -ll` 不會自動讀取 `pyproject.toml`，必須加 `-c pyproject.toml` 才會套用 `[tool.bandit] skips`，沒加的話自訂的例外設定完全無效。另外 `docker/setup-buildx-action` 預設會從 Docker Hub 拉 `moby/buildkit` 映像，GitHub hosted runner 遇到 Docker Hub rate limit 就會逾時；加上 `mirror.gcr.io` 作為 Docker Hub mirror 後才穩定解決。

**What I'd do differently**: 在寫 integration test 之前，先在 Jetson 本地手動跑一次 `docker run` 並觀察 `docker logs`，能比在 CI 上盲目 debug 省下大量時間。CI 每跑一次 build job 就要等 5 分鐘 QEMU 編譯，早一步在本地確認問題會讓整體效率高很多。

---

## Submission Evidence

| Requirement | Link |
|-------------|------|
| ≥1 semver tag with successful deploy | [v1.0.10 deploy run](https://github.com/crazycatpower/edgeai-hw6/actions/runs/26880251799) |
| 5-stage CI all green on main | [CI run #73](https://github.com/crazycatpower/edgeai-hw6/actions/runs/26880250588) |
| Coverage artifact uploaded | [htmlcov artifact](https://github.com/crazycatpower/edgeai-hw6/actions/runs/26880250588) |
| production environment with required reviewer | [Settings → Environments](https://github.com/crazycatpower/edgeai-hw6/settings/environments) |
| Coverage gate failing PR | [demo/coverage-gate-failing](https://github.com/crazycatpower/edgeai-hw6/pulls?q=is%3Apr+is%3Aclosed+demo%2Fcoverage-gate-failing) |
| Accuracy gate failing PR | [demo/accuracy-gate-failing](https://github.com/crazycatpower/edgeai-hw6/pulls?q=is%3Apr+is%3Aclosed+demo%2Faccuracy-gate-failing) |
| Rollback demo (< 30s) | `evidence/rollback-demo.cast` |
| `/healthz` JSON response | `evidence/healthz-curl.png` |
