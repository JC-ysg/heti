# CLAUDE.md — 進這個 repo 的 agent 先讀這裡

最後更新:2026-09-24

這個檔案是給 agent(Claude Code、Cursor 等)的入口。**它的任務只有一個:讓你讀到對的東西,不要被舊內容帶偏。**

---

## 0. 最重要的一句話

**Hēti 在 2026-09-23 換了方向。repo 裡有大量舊內容,它們描述的是已經放棄的系統。**

| 你可能會看到的 | 它是什麼 | 怎麼對待 |
|---|---|---|
| `agent/` `tools/` `ui/` `Heti/` `mem0/` `examples/` `tests/` `config/` `logs/`、根目錄的 `heticontrol.py` `start_heti.py` `run_*.py` `*_test_memory.py` `debug_api_connection.py` `generate_error.py` `test_heticontrol*.py` | **舊系統**:OpenMemory/mem0 的記憶監控器 + Tkinter 控制面板 | 已被取代。**不要以它為準,不要在上面加功能,不要修它的 bug。** 依 PLAN.md 決定 D,會在 M0 被清掉 |
| `.cursor/` 裡的所有 `.mdc` / `.md`(包括 `heti-project-overview.mdc`、`rules/heti-project-rules.mdc`) | **舊願景與舊規格**:「Jarvis 級個人 AI OS」、本地跑 LLM、向量嵌入、MCP 工具、遊戲化 | 已被取代,保留只為留存歷史。**不要引用它回答「Heti 是什麼」** |
| `.cursor/legacy-README.md` | 改版前的 README | 同上 |

**現行方向只看下面第 1 節列的文件。**

---

## 1. 現行文件與權威順序

衝突時,上面的贏。

| 順位 | 位置 | 內容 | 層級 |
|---|---|---|---|
| 1 | vault(L0,**不在這個 repo**) | 使用者的 seed 筆記與原文。PLAN.md 寫「如果哪天這份文件跟 vault 裡的決定衝突,以 vault 為準」 | L0 |
| 2 | [`PLAN.md`](PLAN.md) | **工程計劃**:已定的決定(以 seed 編號 `#NN` 標示)、架構、技術選型、里程碑 M0–M4、明確不做的事、未解問題、風險、目前進度 | L2 |
| 3 | [`plans/overnight-memory-loop-plan.md`](plans/overnight-memory-loop-plan.md) | 2026-09-24 隔夜自主執行的計劃(英文)。**已執行完畢**,不要重跑 | L2 |
| 4 | [`plans/overnight-memory-loop-report.md`](plans/overnight-memory-loop-report.md) | 上面那次執行的驗收報告:DoD 逐項結果、待使用者決定的事、BLOCKED 項目 | L2 |
| 5 | [`memory/README.md`](memory/README.md) | `memory/` 套件的使用說明(中文) | L2 |
| 6 | [`README.md`](README.md) | 給人看的專案首頁 | L2 |

`#NN` 指的是 vault 裡的第 NN 則 seed。**seed 原文不在 repo 裡**,只有 PLAN.md 第一節的決定摘要。

---

## 2. Hēti 現在是什麼(一段話版)

**記憶是底層。記憶不是給使用者自己翻的,是給代勞的 AI 夥伴讀的(#01)。**

價值只在兩層(#02):

- **L0 資料**:原文、seed 筆記,純 markdown,半衰期永久。
- **L1 契約**:五欄位 schema、正規化規則、抽取判準,半衰期數年。

程式碼是 **L2 耗材**,3–12 個月就會過期,必須能在一天內整個換掉。程式全部刪光之後,L0 仍然要能用肉眼讀懂。

資料流:`來源 → 轉接器(L2,每來源一個)→ 正規化關卡(L1,只有一個)→ 原始層(L0,append-only)→ 抽取器 → 檢索 → 代勞層`。詳見 PLAN.md 第二節。

---

## 3. 不可違反的原則

這些來自 PLAN.md 第一節的已定決定。寫程式、審程式、給建議時都要守。

1. **原文不可變更**(#08、#14)。原始層只有新增權,沒有更新、刪除、覆寫的路徑,連索引重建也不能變成後門。模型永不回寫原始層。遺失原文是嚴重錯誤。
2. **判為沒用的不刪,只是不進索引**(#10)。**索引隨時可整個刪掉重建**(#11),它是衍生物,不是快取。
3. **答案只能來自檢索到的片段,附出處。撈不到就說撈不到**(#12)。
4. **L1 五欄位**:`type / created / about / source / status`,`type` 只有四個值:`decision / learning / fact / open`(#07)。抽取器輸出必須過 schema 驗證,不合格重試,再不合格進佇列,不准猜(#09)。
5. **不為未來預先準備**(#04)。不做 plugin 系統、抽象基底類別、provider 介面、registry。**框架數量為零。**
6. **單人單副本**(#06)。不做權限、多使用者、帳號。**不寫死任何個人路徑、金鑰、vault 位置。**
7. **推理走雲端 API,主權在資料和系統,不在算力**(#05)。**主權要在資料流上成立**,觀察器與 API 之間要有過濾(#40)。
8. **一次接一個來源**(#38)。捕捉是被動觀察,不是主動輸入(#36)。
9. **明確不做**(v1):向量庫、M4 之前的 MCP、agent/loop 框架、常駐程序、本地跑大模型、判斷層/主動層。完整清單見 PLAN.md 第六節。

### 未解問題:不要替使用者決定

PLAN.md 第七節列的未解項目(例如 #20 常駐 vs 定時、#29 更正、#30 刪除、#31 備份、#32 衍生資料放哪、#33 佇列超時、#42 他人的資料),**agent 不得自行決定**。遇到了就記下來、問使用者,程式寫成容易改的樣子。

---

## 4. 隱私紅線(repo 是公開的)

`JC-ysg/heti` 是 **public repo**。

- **不得把個人內容放進 repo 或 commit 訊息**:seed 原文、seed 檔名、`about`/`status` 的實際值、真實對話,**包括改寫過的版本**。
- 描述架構決定時,**只用 PLAN.md 第一節已公開的措辭**,用 `#NN` 編號引用。
- 測試只用明顯是假的合成資料(例如 "Test note A")。
- 有 seed 檔時,commit 前跑:`HETI_SEED=<seed 路徑> python plans/tools/privacy_check.py --repo`(exit 0 才能 commit)。這支工具只印檔名,不要設法看它比對到什麼。

---

## 5. 目前進度(2026-09-24)

| 里程碑 | 狀態 |
|---|---|
| M0 地基 | **大部分未完成**:舊程式尚未清除;vault 尚未建立;44 則 seed 尚未進 vault(S2 因容器裡沒有 seed 檔而 BLOCKED);`.cursor/` 已標記取代 |
| M1 第一條迴路 | **部分完成**,但做法和 PLAN.md 不同(見下方「偏離」) |
| M2 抽取器 | 未開始 |
| M3 檢索 | 結構查詢已有雛形(`memory query`);回答組裝未做 |
| M4 代勞層 | 未開始 |

**已完成的程式:`memory/` 套件**,75 個測試,Python 3.9 和 3.11 都通過,離線可跑:
Claude 對話匯出 → 正規化關卡 → append-only 無損原始層 → 可重建索引 → 附路徑的結構查詢。

### 和 PLAN.md 的偏離(需要使用者確認)

| PLAN.md 寫的 | 實際做的 |
|---|---|
| 第一個來源:**Claude Code 本地 JSONL**(決定 B) | 做的是 **Claude 網頁版對話匯出**(`memory/adapters/claude_export.py`)。Claude Code JSONL 轉接器**還沒有** |
| 程式放 `src/heti/`,規則放 `contract/` | 程式放 `memory/`(因為 macOS 不分大小寫,和舊的 `Heti/` 會撞名);`contract/` 還沒建,L1 規則目前寫在 `memory/contract.py` 常數裡 |
| 關卡包含**密鑰清洗** | 關卡目前只做格式驗證、去重、時間正規化,**沒有密鑰清洗** |
| launchd 定時跑 | 目前只有一次性 CLI,沒有排程 |

完整細節見 PLAN.md 第九節。

---

## 6. 怎麼跑

```bash
python3 -m pip install pyyaml pytest
python -m pytest memory/tests -q          # 應該 75 passed

export HETI_VAULT=/tmp/heti-try            # 先用拋棄式 vault
python3 -m memory ingest-claude <匯出的 zip / 資料夾 / conversations.json>
python3 -m memory index rebuild
python3 -m memory query --kind raw --since 2026-01-01
python3 -m memory validate
```

沒有給 `HETI_VAULT` 也沒有給 `--vault` 會直接報錯,這是故意的(#06)。

---

## 7. 工作方式

- **新程式只放在 `memory/`(或 PLAN.md 規劃的新位置),不要動舊程式。** 清除舊程式是 M0 的工作,要等使用者確認再做。
- 先寫測試再實作。測試不連網、不 sleep、不寫進 repo(用 `tmp_path`),時間用 `now=` 參數注入。
- 只依賴標準函式庫 + PyYAML(之後 M2 會加 `anthropic` SDK)。要支援 Python ≥ 3.9:每個模組 `from __future__ import annotations`,不用 `match`,用 `timezone.utc` 而不是 `datetime.UTC`。
- PLAN.md 最後一段:**「M0 完成之前,不要再產生第五份文件。」** 除非使用者要求,不要再寫新的計劃文件。更新既有文件可以。
