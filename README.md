# EdgeAI HW6 — Production CI/CD Pipeline

> **Course**: I4210 AI實務專題, Tatung University  
> **Deadline**: 2026-05-26 23:59  
> **Team**: 2 members (continuing from Lab 11/12)

---

## Operations

### Quickstart

```bash
# Clone and install dependencies
git clone https://github.com/<org>/edgeai-hw6
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

### Member 1

**Parts completed**: Part 0 (INT8 calibration), Part A (test refactoring), Part B (CI workflow design)

**Hardest technical problem**: Getting INT8 TensorRT export to work on Jetson. Initial attempts failed with `CUDA out of memory` during calibration. Tried reducing batch size from 8 to 1 and workspace from 8GB to 4GB — that resolved it. Key insight: INT8 calibration needs representative data distribution, not just quantity.

**What I learned**: The lazy import pattern for `ultralytics`/`torch` was new to me. These libraries pull in CUDA at import time, which breaks x86 CI. Wrapping them in `# pragma: no cover` functions lets the CI test all other logic without touching GPU code.

**What I'd do differently**: Set up the self-hosted runner in Week 1 instead of Week 3. Half our debugging time was spent on runner connectivity issues that had nothing to do with the actual code.

---

### Member 2

**Parts completed**: Part C (Jetson integration test), Part D (tag deployment), Part E (rollback), Part F (documentation)

**Hardest technical problem**: The `healthcheck.sh` polling logic. First version used a simple `curl || exit 1` which failed intermittently because the TensorRT engine takes 3–8 minutes to compile on first run. Rewrote to poll every 5 seconds for up to 60 seconds, requiring 3 consecutive successes. This eliminated all false positives.

**What I learned**: `nvpmodel` in a Docker container requires bind-mounting `/var/lib/nvpmodel/status` and `/etc/nvpmodel.conf` — reading these files is much more reliable than running `nvpmodel -q` inside a container where the command may not be available.

**What I'd do differently**: Use `docker compose watch` for local development to avoid the build-push-pull cycle during iteration. Also would set up the production environment protection rule on Day 1 — accidentally deploying broken code to the device before protection was configured cost us an hour of debugging.

---

## Submission Evidence

| Requirement | Link |
|-------------|------|
| ≥1 semver tag with successful deploy | [v1.0.0 deploy run](https://github.com/<org>/edgeai-hw6/actions) |
| 5-stage CI all green on main | [CI run](https://github.com/<org>/edgeai-hw6/actions) |
| Coverage artifact uploaded | [htmlcov artifact](https://github.com/<org>/edgeai-hw6/actions) |
| production environment with required reviewer | [Settings → Environments](https://github.com/<org>/edgeai-hw6/settings/environments) |
| Coverage gate failing PR | [demo/coverage-gate-failing](https://github.com/<org>/edgeai-hw6/pulls) |
| Accuracy gate failing PR | [demo/accuracy-gate-failing](https://github.com/<org>/edgeai-hw6/pulls) |
| Rollback demo (< 30s) | `evidence/rollback-demo.cast` |
| `/healthz` JSON response | `evidence/healthz-curl.png` |
