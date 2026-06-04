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

**Parts completed**: Part 0 (INT8 calibration), Part A (test refactoring), Part B (CI workflow design)

**Hardest technical problem**: Getting INT8 TensorRT export to work on Jetson. Initial attempts failed with `CUDA out of memory` during calibration. Tried reducing batch size from 8 to 1 and workspace from 8GB to 4GB — that resolved it. Key insight: INT8 calibration needs representative data distribution, not just quantity.

**What I learned**: The lazy import pattern for `ultralytics`/`torch` was new to me. These libraries pull in CUDA at import time, which breaks x86 CI. Wrapping them in `# pragma: no cover` functions lets the CI test all other logic without touching GPU code.

**What I'd do differently**: Set up the self-hosted runner in Week 1 instead of Week 3. Half our debugging time was spent on runner connectivity issues that had nothing to do with the actual code.

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
