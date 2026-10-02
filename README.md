# Hēti

**記憶是底層。記憶不是給我翻的,是給代勞的夥伴讀的。**

Hēti 是一個單人使用的個人記憶系統。它被動地收集我和 AI 的對話等資料,一字不漏地保存成純 markdown,整理成有固定欄位的筆記,讓替我做事的 AI 夥伴可以查、可以引用出處。

> ⚠️ **2026-09-23 改版。** 這個 repo 裡還留著舊系統的程式和文件(OpenMemory 記憶監控器、Tkinter 控制面板、`.cursor/` 裡的「Jarvis 級 AI OS」願景)。**那些都已被取代**,只是還沒清掉。清單見下方「舊系統」一節。
>
> 如果你是 agent,先讀 [`CLAUDE.md`](CLAUDE.md)。

---

## 核心價值

### 1. 價值只在資料和契約,不在程式

系統按半衰期分成三層(#02):

| 層 | 內容 | 半衰期 | 地位 |
|---|---|---|---|
| **L0 資料** | 原文、seed 筆記,純 markdown | 永久 | **價值所在** |
| **L1 契約** | 五欄位 schema、正規化規則、抽取判準 | 數年 | **價值所在** |
| L2 能力 | 轉接器、抽取器、檢索、計劃文件 | 3–12 月 | 耗材,一天內可整個換掉 |

**判斷標準:程式全部刪光,L0 還看得懂。**

### 2. 原文一字不漏,永不修改

- 原始層只能新增。程式沒有更新、刪除、覆寫的權限,模型永不回寫(#08)。
- 判為沒用的不刪,只是不進索引(#10)。
- 索引隨時可以整個刪掉重建(#11)。

### 3. 答案有出處,撈不到就說撈不到

答案只能來自檢索到的片段,附出處,不准猜(#12)。代勞層用的是結構查詢(照 type / status / 時間撈),語意檢索延後(#13)。

### 4. 主權在資料,不在算力

推理走雲端 API(#05)。主權要在資料流上成立,不只在硬碟上:觀察器與 API 之間要有過濾(#40)。

### 5. 極簡

不為未來預先準備,唯一的準備是純文字 + 薄介面(#04)。**框架數量為零。** 單人單副本,不做權限、多使用者、帳號(#06)。

---

## 筆記契約(L1)

每則筆記的 frontmatter 有五個欄位(#07):

```yaml
---
type: decision      # 只能是 decision / learning / fact / open 其中一個
created: 2026-09-24 # 寫進 vault 的時間(#35)
about: ...
source: ...
status: ...
---
```

`type` / `status` 標錯是嚴重問題,要靠結構保證(#14)。

---

## 架構

```
來源(一次接一個,從資訊密度最高的開始 #38)
   │
   ▼
轉接器            L2,每個來源一個,可拋棄
   │  只做一件事:變成(原文, 來源標記, 時間)
   ▼
正規化關卡        L1,只有一個,要定死
   │  格式驗證 → 去重 → 時間正規化 → 密鑰清洗
   ▼
原始層 raw/       L0,append-only,純 markdown
   │
   ▼
抽取器            L2,Claude API + structured output(M2)
   │  產出五欄位 + 有用 / 不確定 / 沒用
   ▼
檢索              結構查詢(v1);語意查詢延後
   │
   ▼
代勞層            vault 上的 MCP server(M4,MCP 只在這裡出現)
```

完整設計、技術選型、成本估算見 [`PLAN.md`](PLAN.md)。

---

## 目前進度(2026-09-24)

| 里程碑 | 內容 | 狀態 |
|---|---|---|
| M0 地基 | 清空舊程式、建 vault、seed 進 vault、異地備份 | ⏳ 大部分未完成 |
| M1 第一條迴路 | 轉接器 → 關卡 → 原始層 | 🟡 部分完成(和計劃有偏離,見下) |
| M2 抽取器 | Claude API 產出五欄位 | ⬜ 未開始 |
| M3 檢索 | 結構查詢 + 附出處的回答組裝 | 🟡 結構查詢有雛形 |
| M4 代勞層 | vault 上的 MCP server | ⬜ 未開始 |

**已經能跑的:`memory/` 套件。** 在合成資料上跑通第一條記憶迴路:

Claude 對話匯出 → 正規化關卡 → append-only 無損原始層(完整保留原始 JSON)→ 可重建的索引 → 附檔案路徑的結構查詢

75 個測試,Python 3.9 / 3.11 都通過,離線可跑。

**還沒做到、和計劃不一樣的地方:**

- 計劃的第一個來源是 **Claude Code 本地 JSONL**,但目前做的是 **Claude 網頁版對話匯出**。JSONL 轉接器還沒寫。
- 正規化關卡還沒有**密鑰清洗**。
- 還沒有 launchd 排程,只有手動執行的 CLI。
- seed 還沒進 vault(執行時容器裡沒有 seed 檔)。

細節與待決定事項見 [`PLAN.md`](PLAN.md) 第九節,以及 [`plans/overnight-memory-loop-report.md`](plans/overnight-memory-loop-report.md)。

---

## 快速開始

需要 Python ≥ 3.9 和 PyYAML。在 repo 根目錄執行:

```bash
python3 -m pip install pyyaml

# 先用拋棄式 vault 試跑:匯入 raw 的東西目前沒有刪除機制(#30)
export HETI_VAULT=/tmp/heti-try

python3 -m memory ingest-claude <Claude 匯出的 zip、資料夾或 conversations.json>
python3 -m memory index rebuild
python3 -m memory query --kind raw --since 2026-01-01
python3 -m memory query --type open
python3 -m memory validate
```

跑測試:

```bash
python3 -m pip install pytest
python3 -m pytest memory/tests -q
```

完整用法見 [`memory/README.md`](memory/README.md)。

---

## Repo 地圖

### 現行

| 路徑 | 內容 |
|---|---|
| [`CLAUDE.md`](CLAUDE.md) | 給 agent 的入口:讀什麼、不讀什麼、不可違反的原則 |
| [`PLAN.md`](PLAN.md) | 工程計劃:已定的決定、架構、里程碑、未解問題、進度 |
| [`memory/`](memory/) | 記憶層程式(L2)與測試 |
| [`plans/`](plans/) | 隔夜自主執行的計劃、驗收報告、隱私檢查工具 |
| `.heti-baseline` | 隔夜執行的基準 commit,隱私檢查用 |

**vault(L0)不在這個 repo。** 計劃建議放在獨立的私有 repo(PLAN.md 第五節)。

### 舊系統(已被取代,待 M0 清除)

| 路徑 | 內容 |
|---|---|
| `agent/` `tools/` `ui/` `Heti/` `mem0/` `examples/` `tests/` `config/` `logs/` | OpenMemory 記憶監控器、API 客戶端、Tkinter 控制面板、MCP 伺服器雛形 |
| `heticontrol.py` `start_heti.py` `run_demo.py` `run_tests.py` `test_heticontrol*.py` `*_test_memory.py` `debug_api_connection.py` `generate_error.py` | 舊系統的啟動、測試、除錯腳本 |
| `.cursor/` | 舊願景、舊規格、舊的 Cursor 規則。見 [`.cursor/SUPERSEDED.md`](.cursor/SUPERSEDED.md) |

---

## 明確不做的事(v1)

向量庫 / embedding、M4 之前的 MCP、agent / loop 框架、手機寫入路徑、權限 / 多使用者 / 帳號、常駐程序、本地跑大模型、判斷層 / 主動層。理由見 PLAN.md 第六節。

---

## 隱私

這個 repo 是**公開的**。seed 原文、真實對話、任何個人內容都不放進來,測試只用合成資料。規則見 [`CLAUDE.md`](CLAUDE.md) 第 4 節。
