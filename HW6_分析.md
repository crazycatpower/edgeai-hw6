# HW6 完整分析筆記

> **課程**：I4210 AI實務專題，大同大學  
> **截止日期**：2026年5月26日 23:59  
> **團隊**：2人（延續 Lab 11/12 的組合）  
> **總分**：100分  
> **預估工時**：18–26 小時（有 AI 輔助）

---

## 目標概述

建立一條生產級 CI/CD pipeline，從 `git push` 出發，依序完成：
1. 自動化測試 / 安全掃描
2. Docker image 建置並推送到 GHCR
3. 在 Jetson 上執行整合測試
4. Tag 觸發 + 人工審批後自動部署到 Jetson
5. 30 秒內可回滾

---

## 硬體需求

| 硬體 | 用途 | 備注 |
|------|------|------|
| Jetson Orin Nano 8GB | Part C、D 必須 | original 或 Super 皆可 |
| IMX219 CSI 相機 | Part C | 沒有會扣 2 分，需用靜態圖片備案 |
| 第二台 Jetson 或 x86 Linux | Part F 艦隊示範 | |
| Mosquitto broker | MQTT | localhost:1883 |

---

## 評分總覽

| Part | 主題 | 分數 |
|------|------|------|
| 0 | INT8 校準 | 10 |
| A | 真實測試 + Coverage/Accuracy 門檻 | 15 |
| B | 五階段 Workflow Graph | 15 |
| C | Jetson 整合測試 | 15 |
| D | Tag 觸發部署 + nvpmodel | 20 |
| E | 30 秒內 Rollback | 5 |
| F | 文件 + 艦隊就緒 | 15 |
| — | Code Quality | 5 |
| **合計** | | **100** |

---

## 最終 Repo 結構

```
edgeai-hw6/
├── .github/workflows/
│   ├── ci.yml              # Part B：5 階段 pipeline
│   └── deploy.yml          # Part D：tag 觸發部署
├── src/
│   ├── inference_node.py   # 重構後（Part A）
│   ├── mqtt_publisher.py   # Part A：抽出 MQTT 邏輯
│   └── healthcheck.py      # Part D：/healthz endpoint
├── calibration/
│   ├── calibrate_int8.py   # Part 0
│   ├── calibration.yaml    # Part 0
│   ├── calibration_data/   # Part 0（gitignore）
│   ├── accuracy_baseline.json  # Part 0（CI 讀取）
│   └── README.md
├── tests/
│   ├── test_smoke.py       # 從 Lab 12 延續
│   ├── test_inference.py   # Part A（≥6 tests）
│   ├── test_mqtt.py        # Part A（≥4 tests）
│   ├── test_accuracy.py    # Part A（INT8 vs FP16 門檻）
│   └── integration/
│       ├── sample_frame.jpg    # Part C：無相機備案
│       └── test_jetson_e2e.py  # Part C
├── deploy/
│   ├── docker-compose.yml  # Part D
│   ├── deploy.sh           # Part D
│   ├── rollback.sh         # Part E
│   ├── healthcheck.sh      # Part D
│   └── power_profile.json  # Part D
├── evidence/               # 截圖 + 錄影
├── models/
│   └── test_video.mp4      # 從 HW5 複製
├── Dockerfile.ci
├── pyproject.toml
├── requirements.txt
├── best.pt
├── best_int8.engine        # Part 0（~7MB）
├── entrypoint.sh
└── README.md               # 所有文件都在這裡
```

---

## 各 Part 詳細工作項目

### Part 0 — INT8 校準（10分）

**在 Jetson 上執行，可與 Step 0.0 + 0.6 合併一次 SSH session**

- [ ] 確認 `best.pt` 是 HW5 fine-tuned 版（md5sum 比對）
- [ ] 從 HW5 dataset 隨機取樣 ~500 張到 `calibration/calibration_data/`
- [ ] 建立 `calibration/calibrate_int8.py`（`Int8Calibrator` 類別）
- [ ] 建立 `calibration/calibration.yaml`（nc: 25，names 對應 Lab 9）
- [ ] 執行校準：`python3 calibration/calibrate_int8.py`
- [ ] 測量 FP16 vs INT8 的 mAP@50（用 test split）
- [ ] 填寫 `calibration/accuracy_baseline.json`：
  ```json
  {
    "fp16_map50": 0.xxxx,
    "int8_map50": 0.xxxx,
    "test_split": "...",
    "calibrated_at": "2026-xx-xx",
    "best_pt_md5": "..."
  }
  ```
- [ ] 提交 `best_int8.engine`（約 7MB）
- [ ] 寫 `calibration/README.md`（如何重新校準）
- [ ] 寫 README §"Optimization (INT8 vs FP16)"

**評分標準**：
- INT8 engine 用真實校準產生：4分
- INT8 mAP drop ≤ 2pts vs FP16（或說明原因）：3分
- README 比較表 + 生產建議：3分

---

### Part A — 真實測試 + 門檻（15分）

**在 laptop 上開發，不需要 Jetson**

#### A1 — 重構 `src/inference_node.py`
- [ ] 抽出 `src/mqtt_publisher.py`（`MqttPublisher` 類別 + `PublisherConfig`）
- [ ] YOLO/ultralytics import 改為 lazy（在函式內才 import，加 `# pragma: no cover`）
- [ ] cv2, paho 可以繼續在模組頂部 import（有 x86 wheel）
- [ ] `inference_node.py` 使用 `client_factory` 注入（dependency injection）

#### A2 — `tests/test_mqtt.py`（≥4 tests）
- [ ] 用 `MagicMock` 替代真實 paho client
- [ ] 測試：JSON payload 發送、disconnected 時回傳 False、字串 payload 不重複編碼、disconnect 停止 loop

#### A3 — `tests/test_inference.py`（≥6 tests）
- [ ] 使用 `@pytest.mark.parametrize`
- [ ] 用 `pytest.fixture` mock `cv2.VideoCapture`
- [ ] 測試：preprocess_frame 輸出形狀、灰階輸入處理、confidence threshold 過濾、payload 格式

#### A4 — Coverage gate
- [ ] 確認 `pyproject.toml` 有 `fail_under = 90`
- [ ] 本地跑：`pytest tests/ --ignore=tests/integration --cov=src --cov-fail-under=90`

#### A5 — `tests/test_accuracy.py` + 示範 PR
- [ ] 讀 `calibration/accuracy_baseline.json`，assert `fp16 - int8 <= 0.02`
- [ ] 用 `@pytest.mark.skipif` 讓沒有 baseline 時跳過（不阻擋早期 CI）
- [ ] 做示範 PR：把 int8_map50 改成比 fp16 低 5pts → CI 失敗 → 恢復 → CI 通過

#### 要提交的 PR（共 2 個）：
1. `demo/coverage-gate-failing`：新增無測試的模組 → 覆蓋率掉到 <90% → 刪除 → 恢復
2. `demo/accuracy-gate-failing`：把 int8_map50 人為降低 → 測試失敗 → 恢復

---

### Part B — 五階段 Workflow（15分）

**Workflow 依賴圖（必須完全符合）：**
```
         ┌──────────┐
         │   lint   │
         └────┬─────┘
              │
        ┌─────┴───────┐
        ▼             ▼
   ┌────────┐  ┌─────────────┐
   │  test  │  │security-scan│
   └───┬────┘  └──────┬──────┘
       │              │
       └──────┬────────┘
              ▼
         ┌─────────┐
         │  build  │
         └────┬────┘
              │
              ▼
     ┌─────────────────┐
     │ integration-test│
     │   (Jetson only) │
     └─────────────────┘
```

**各 Job 設定重點：**

| Job | runs-on | needs | 觸發條件 |
|-----|---------|-------|----------|
| lint | ubuntu-latest | — | 所有 push/PR |
| test | ubuntu-latest | lint | 所有 push/PR |
| security-scan | ubuntu-latest | lint | 所有 push/PR |
| build | ubuntu-latest | [test, security-scan] | 所有 push/PR |
| integration-test | [self-hosted, linux, arm64, jetson] | build | 僅 main push |

**關鍵設定：**
- test job 要有 `--cov-fail-under=90` 和 `--ignore=tests/integration`
- test job 要上傳 `htmlcov/` 為 artifact（`if: always()`）
- security-scan 跑 `bandit -r src/ -ll` + `pip-audit --strict -r requirements.txt`
- integration-test 要有 `if: github.event_name == 'push' && github.ref == 'refs/heads/main'`

---

### Part C — Jetson 整合測試（15分）

**`tests/integration/test_jetson_e2e.py` 功能：**
1. 拉 `ghcr.io/<repo>/edgeai-hw6:sha-<short>`（當前 commit 的 image）
2. 用 `--runtime nvidia` 啟動容器（掛載 model cache volume）
3. 等待 engine 編譯/載入（最多 10 分鐘）
4. 用相機或 `sample_frame.jpg` 餵入推理節點
5. 訂閱 MQTT topic，斷言 30 秒內收到至少一則訊息
6. `finally` block 清理容器（避免卡住下一次 CI）

**實作提示：**
- MQTT subscriber 用背景 thread + `threading.Event`
- 沒有相機時用 `sample_frame.jpg`，用 `if Path('/dev/video0').exists()` 區分
- 容器清理必須放 `finally`

---

### Part D — Tag 觸發部署（20分）

#### D1 — `src/healthcheck.py`
- `HealthCheckServer` 類別
- `GET /healthz` 回傳：`{"status": "healthy", "model_version": "...", "power_mode": "..."}`
- `power_mode` 從 `nvpmodel -q` 即時讀取（不從 config file）
- 在 `inference_node.main()` 中呼叫 `healthcheck.start_in_thread()`

#### D2 — `deploy/docker-compose.yml`
- image tag 用 `${IMAGE_TAG}` env var
- `runtime: nvidia`
- `network_mode: host`（讓 healthcheck.sh 可以連到 /healthz）
- volumes：
  - `lab12-models:/opt/models`
  - `../models/test_video.mp4:/opt/data/test_video.mp4:ro`
  - `/var/lib/nvpmodel/status:/var/lib/nvpmodel/status:ro`
  - `/etc/nvpmodel.conf:/etc/nvpmodel.conf:ro`

#### D2 — `deploy/power_profile.json`
```json
{
  "production": "15W",
  "low_power_demo": "7W",
  "burst_demo": "MAXN"
}
```
（依照自己 Jetson SKU 調整，先用 `sudo nvpmodel -m <ID>` 測試每個 mode）

#### D3 — `deploy/healthcheck.sh`
- 輪詢 `/healthz`
- 60 秒內需連續 3 次成功才算過

#### D4 — `deploy/deploy.sh`
流程：
1. 從 `power_profile.json` 解析 mode name → ID
2. `sudo nvpmodel -m <ID>` + `sudo jetson_clocks`
3. 備份舊 tag 到 state file
4. `docker compose pull` + `docker compose up -d --force-recreate`
5. 執行 `healthcheck.sh`，失敗則自動呼叫 `rollback.sh`
6. 寫入新 tag 到 state file

#### D5 — 一次性 GitHub 設定
- [ ] `sudo mkdir -p /var/lib/edgeai-hw6 && sudo chown $USER:$USER /var/lib/edgeai-hw6`
- [ ] GitHub → Settings → Environments → `production` → Required reviewers
- [ ] GitHub Secrets：`JETSON_HOST`, `JETSON_USER`, `JETSON_SSH_KEY`
- [ ] Workflow permissions → Read and write

#### D6 — `.github/workflows/deploy.yml`
- 觸發：`push: tags: ['v[0-9]+.[0-9]+.[0-9]+']`
- `environment: production`（觸發人工審批）
- 步驟：
  1. re-tag image（`v1.2.3`, `v1.2`, `v1`, `latest`，不重建）
  2. 執行 `deploy.sh`
- 推 `v1.0.0` tag 做第一次完整測試

---

### Part E — Rollback（5分）

#### `deploy/rollback.sh` 功能：
1. 讀取 `/var/lib/edgeai-hw6/deployed.txt`（當前）和 `.history`（舊的）
2. 拉舊 tag（`docker compose pull || true`）
3. `IMAGE_TAG=<舊tag> docker compose up -d --force-recreate`
4. 執行 `healthcheck.sh`
5. 更新 state file

#### README §"Operations" → "How to roll back" 需包含：
- 何時要 rollback（症狀清單：healthcheck 失敗、mAP drop >5%、容器 restart loop）
- 確切指令：`time bash deploy/rollback.sh`
- 如何找舊 tag：`cat /var/lib/edgeai-hw6/deployed.txt.history`
- 兩個 tag 都壞了怎麼辦
- 要通知誰（Slack/Email 模板）

#### 示範錄影（evidence/rollback-demo.cast）：
1. `docker ps` 顯示當前 tag
2. `time bash deploy/rollback.sh`（< 30 秒）
3. 確認舊 tag 正在跑
4. 顯示 wall time

---

### Part F — 文件（15分）

全部寫在 `README.md`，順序如下：

1. **§Operations**（Quickstart / Deploy / Rollback）
2. **§Architecture**（流程圖 + 每階段說明 + 選擇不做什麼）
3. **§Optimization (INT8 vs FP16)**（比較表 + 建議）
4. **§Scaling to a Fleet**（N 台 Jetson 策略 + 工具建議）
5. **§Reflections**（每人 150–250 字）
6. **§Submission Evidence**（每個評分項目的 permalink）

#### §Reflections 4 個必填項目（每位成員）：
1. 你在 HW6 做了哪些具體部分（要說 Part 名稱和細節）
2. 最困難的技術問題是什麼（症狀、嘗試、解法）
3. 學到了什麼原本不知道的事
4. 下次會做什麼不同的決定

---

### Code Quality（5分）

#### 所有檔案必須有 header：

**Python (.py)：**
```python
#!/usr/bin/env python3
# Copyright (c) 2026 <Your Name(s)>
# Tatung University — I4210 AI實務專題
```

**Shell (.sh)：**
```bash
#!/usr/bin/env bash
# Copyright (c) 2026 <Your Name(s)>
# Tatung University — I4210 AI實務專題
```

**YAML (.yml)：**
```yaml
# Copyright (c) 2026 <Your Name(s)>
# Tatung University — I4210 AI實務專題
```

#### Class 對應表：
| 檔案 | Class 名稱 |
|------|-----------|
| `src/inference_node.py` | `InferenceNode` |
| `src/healthcheck.py` | `HealthCheckServer` |
| `src/mqtt_publisher.py` | `MqttPublisher` |
| `calibration/calibrate_int8.py` | `Int8Calibrator` |

#### `pdm run ci` 必須全過（六個子檢查）：
1. `ruff format --check`
2. `ruff check`
3. `mypy`
4. `bandit`
5. `pylint --fail-under=7.0`
6. `pytest --cov=src --cov-fail-under=90`

**不能新增任何**：`# noqa`, `# nosec`, `# type: ignore`, `# pylint: disable`

---

## 一次性 Jetson 設定（只做一次）

### Step 0.0 — 重新註冊 Runner
```bash
# 三種情況擇一：
# A：把 Lab12 的 runner 改指向 HW6（最簡單）
# B：在旁邊裝第二個 runner（保留 Lab12 CI）
# C：全新安裝

./config.sh \
  --url "https://github.com/<org>/edgeai-hw6" \
  --token "$HW6_TOKEN" \
  --labels "self-hosted,linux,arm64,jetson,orin-nano" \
  --name "jetson-team-XX" \
  --unattended
sudo ./svc.sh install $(whoami)
sudo ./svc.sh start
```

確認 runner 上線：
```bash
gh api /repos/<org>/edgeai-hw6/actions/runners \
  --jq '.runners[] | {name, status, labels: [.labels[].name]}'
```

### Step 0.6 — SSH Key 設定
```bash
ssh-keygen -t ed25519 -f ~/.ssh/edgeai-hw6 -N ""
cat ~/.ssh/edgeai-hw6.pub >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
sudo systemctl enable --now ssh
ssh -i ~/.ssh/edgeai-hw6 $(whoami)@localhost "echo 'SSH works'"
```

### NOPASSWD sudo 設定
```
# sudo visudo → 新增一行：
<runner-user> ALL=(ALL) NOPASSWD: /usr/sbin/nvpmodel, /usr/bin/jetson_clocks
```

---

## 建議執行順序（最少來回）

| 天 | 工作 | 輸出 | 預估時間 |
|----|------|------|---------|
| 1–2 | 建 repo + 結構 + GitHub 設定 | Green CI | 2–3h |
| 3 | Part 0（INT8 校準） | `best_int8.engine` + baseline JSON | 2–3h |
| 4 | Part A（測試 + 門檻） | 兩個示範 PR 完成 | 3–4h |
| 5 | Part B（5 階段 workflow） | `ci.yml` 五個 job 全綠 | 2–3h |
| 6 | Part C（整合測試） | `integration-test` job 在 Jetson 跑過 | 2h |
| 7–8 | Part D（部署） | 第一次 `v1.0.0` tag 成功部署 | 3–4h |
| 9 | Part E（rollback） | `rollback.sh` < 30 秒 | 1h |
| 10–11 | Part F（文件） | README 全部區段完成 | 2–3h |
| 12 | 截圖 + 整理 evidence/ | 提交就緒 | 1–2h |
| 13 | Buffer | 補做 + Debug | 0–4h |
| 14 | 提交 | `submission-final` tag | 0.5h |

---

## 需要的截圖清單（evidence/ 資料夾）

| 檔案 | 來源 |
|------|------|
| `htmlcov-artifact.png` | CI run 頁面，coverage artifact 下載按鈕 |
| `production-env-settings.png` | GitHub Settings → Environments → production |
| `deploy-log-nvpmodel.png` | deploy run log，含 `[deploy] Setting nvpmodel...` |
| `healthz-curl.png` | `curl http://<jetson>:8000/healthz` 的 JSON 回應 |
| `rollback-demo.cast` | asciinema 錄影，wall time < 30 秒 |

---

## GitHub 永久 Artifacts 清單

提交前必須存在：
- [ ] 至少一個 semver annotated tag（如 `v1.0.0`）觸發成功部署
- [ ] `main` 的 branch protection rule（需要全部 CI job + 1 人審查）
- [ ] `production` environment 設定 required reviewer
- [ ] self-hosted runner 帶 `jetson` label 且 online
- [ ] 至少一次 main 上全五個 job 通過的 CI run
- [ ] 至少一次 `v*.*.*` tag push 觸發的成功 deploy run
- [ ] 一個關閉的 PR 示範 coverage gate 失敗再恢復
- [ ] 一個關閉的 PR 示範 accuracy gate 失敗再恢復

---

## 常見陷阱

| 症狀 | 原因 | 解法 |
|------|------|------|
| `nvpmodel -m N` 失敗，EMC error | Jetson kernel 不接受某個 mode | 先 `sudo nvpmodel -m <ID>` 逐個測試，選能用的 |
| integration-test 在 PR 也跑 | 缺少 `if:` 條件 | 加 `if: github.event_name == 'push' && github.ref == 'refs/heads/main'` |
| coverage 本地 78%，CI 62% | CI 排除了 `tests/integration/` | 本地也要加 `--ignore=tests/integration` |
| `/healthz` 回傳 `power_mode: ""` | nvpmodel 在容器內不可用 | 改讀 `/var/lib/nvpmodel/status` + `/etc/nvpmodel.conf`（已 bind-mount） |
| GHCR auth 過期（~8 小時後） | GitHub token 有效期限 | deploy.yml 的 `docker/login-action` 每次 run 重新認證 |
| INT8 mAP drop > 5% | 校準資料不夠代表性 | 加更多圖片、不同光線/時段/遮擋情況，不能直接降低門檻 |
| `import torch` 在 x86 CI 失敗 | ultralytics 有 Jetson-only CUDA wheel | 改成 lazy import，放在函式內 |
