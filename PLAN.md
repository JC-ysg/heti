# Hēti 工程計劃

建立:2026-09-23
依據:vault seed 第 01–44 則(2026-09-19)+ 2026-09-23 的四個決定
狀態:執行中(進度見第九節,最後更新 2026-09-24)

---

## 這份文件的地位

**這份文件是 L2,會過期。** 它不是價值所在。

價值在 `vault/`(L0)和 `contract/`(L1)。這份計劃寫錯了就改,砍掉重寫也不心疼。
如果哪天這份文件跟 vault 裡的決定衝突,**以 vault 為準**。

---

## 一、已定的事

### 來自 44 則(不再討論)

| # | 決定 |
|---|---|
| 01 | 記憶是底層。記憶不是給我翻的,是給代勞的夥伴讀的 |
| 02 | 按半衰期分 L0 資料 / L1 契約 / L2 能力。價值只能在 L0 和 L1 |
| 04 | 不為未來預先準備。唯一的準備是純文字 + 薄介面 |
| 05 | 推理走雲端 API。主權在資料和系統,不在算力 |
| 06 | 單人單副本。不做權限、多使用者、帳號 |
| 07 | L1 五欄位:type / created / about / source / status。type 四值 |
| 08 | 原文不可變更。程式只有新增權。模型永不回寫原始層 |
| 09 | 抽取器輸出必須過 schema 驗證。不合格重試,再不合格進佇列,不准猜 |
| 10 | 判為沒用的不刪,只是不進索引 |
| 11 | 索引隨時可整個刪掉重建 |
| 12 | 答案只能來自檢索到的片段,附出處,撈不到就說撈不到 |
| 13 | 兩種檢索:語意 + 結構查詢。代勞層用的是結構查詢 |
| 14 | type/status 標錯是嚴重級,要靠結構保證 |
| 36 | 捕捉方向是被動觀察,不是主動輸入 |
| 37 | 捕捉層 = 轉接器(L2,每來源一個)+ 正規化關卡(L1,只有一個) |
| 38 | 一次接一個來源,從資訊密度最高的開始 |
| 40 | 主權要在資料流上成立,不只在硬碟上。觀察器與 API 之間要有過濾 |

### 2026-09-23 新定的四件

| 決定 | 內容 | 取代 |
|---|---|---|
| A | **跳過手動期**,直接接第一個來源 | 第 21 則的「三十則手動捕捉」關卡 |
| B | **第一個來源:Claude Code 本地 JSONL** | — |
| C | **vault 進私有 git repo,全部都放** | 解第 31 則 |
| D | **保留 `JC-ysg/heti`,清空內容重來** | — |

### 決定 A 的理由(記錄下來,免得以後又繞回去)

第 21 則把入場關卡定在「三十則在事情發生的當下捕捉」。
第 36 則說:被要求寫一則筆記時想不出要寫什麼,所以主動捕捉的產出會是零。

**這兩則直接衝突,而第 36 則在後、且論證成立。** 那三十則寫不出來。
schema 改用真實捕捉到的資料測,關卡改成「抽取器跑過三十則真實資料」。

---

## 二、架構

### 資料流

```
來源 (Claude Code JSONL)
   │
   ▼
轉接器 adapters/claude_code.py            ← L2,每來源一個,可拋棄
   │  只做一件事:變成 (原文, 來源標記, 時間)
   ▼
正規化關卡 gate.py                        ← L1,只有一個,要定死
   │  格式驗證 → 去重 → 時間正規化 → 密鑰清洗
   ▼
原始層 vault/raw/*.md                     ← L0,append-only,純 markdown
   │
   ▼
抽取器 extract.py                         ← L2,Claude API + structured output
   │  產出 L1 五欄位 + 有用/不確定/沒用
   ├─ 有用   → 衍生欄位寫回同檔 frontmatter
   ├─ 不確定 → vault/queue/
   └─ 沒用   → 標記,留著,不進索引
   │
   ▼
檢索  結構查詢(frontmatter + grep)       ← v1 只做這個
      語意查詢(向量)                      ← 延後,不是 v1
   │
   ▼
代勞層  vault 上的 MCP server              ← M4,不是現在
```

### 三層對應

| 層 | 內容 | 半衰期 | 這個 repo 裡的位置 |
|---|---|---|---|
| L0 | 原文、seed 筆記 | 永久 | `vault/`(建議獨立 repo,見下) |
| L1 | schema、正規化規則、抽取判準 | 數年 | `contract/` |
| L2 | 轉接器、抽取器、檢索、這份計劃 | 3–12 月 | `src/`、`PLAN.md` |

---

## 三、技術選型

**原則:框架數量為零。** 第 04 則的前車之鑑是 85 個 skill、71 個 agent、36 個 hook。

| 用途 | 選什麼 | 為什麼 |
|---|---|---|
| 語言 | Python 3.11+ | 已在用 |
| LLM SDK | `anthropic` 官方 SDK | 唯一依賴 |
| 抽取模型 | **Claude Haiku 4.5**(`claude-haiku-4-5`) | 見下方成本 |
| 判斷層模型(以後) | **Claude Opus 5**(`claude-opus-5`) | 需要判斷力的地方不省 |
| schema 驗證 | API 原生 structured output | 不自己寫驗證碼 |
| 排程 | macOS `launchd` | 系統內建,不裝東西 |
| 儲存 | 純 markdown 檔 | 第 02 則 |
| 索引 | frontmatter + `grep` / `ripgrep` | v1 不需要向量庫 |
| 向量庫 | **不裝** | 第 13 則:代勞層用結構查詢 |
| MCP | **v1 不用** | 只在 M4 代勞層出現 |
| agent / loop 框架 | **不用** | 一支 launchd + 一支 Python |

### 成本(解第 43 則的量級焦慮)

一天 500 則、每則約 500 token,Haiku 4.5($1 / 百萬 input token):

- 一天約 **$0.25**
- 一個月約 **$8**
- 用 Batch API 再砍一半
- 全換 Sonnet 5 也不到一個月 $20

**成本不是限制。** 第 43 則剩下兩個真問題:抽取器要先判值不值得留、佇列會爆。

### 為什麼抽取器用 Haiku 而不是 Opus

抽取是高頻、單一、結構化的任務,配 structured output 之後模型只需要填欄位。
判斷層(讀記憶、回答、推理)以後用 Opus 5,那裡才需要判斷力。
**這是可以隨時改的一行設定** —— 如果抽取品質不夠,升到 Sonnet 5 或 Opus 5,成本仍在一個月 $20 內。

---

## 四、里程碑

### M0 — 地基

- [ ] 清空 `JC-ysg/heti`:移除 `heticontrol.py`、`Heti/`、`agent/`、`tools/`、`ui/`、`mem0/`、`examples/`、根目錄測試腳本
- [x] `.cursor/` 舊計劃檔標記為已取代(保留,不刪)—— 見 `.cursor/SUPERSEDED.md`
- [~] 建立新結構(見第五節)—— 目前程式在 `memory/`,不是 `src/heti/`;`contract/`、`config/heti.yaml` 未建。見第九節偏離 2
- [ ] **44 則 seed 寫進 `vault/00-seed/`**,一則一檔,frontmatter 原樣
- [ ] 建立私有 vault repo + 自動 commit(解第 31 則)

**完成條件:vault 裡有 44 個檔,而且有異地備份。**
第 22 則說「文件三份,vault 檔案零則」—— M0 結束時這句話不再成立。

### M1 — 第一條迴路(最小可跑)

- [ ] `adapters/claude_code.py`:讀 `~/.claude/projects/*/*.jsonl` → `(原文, 來源, 時間)`
- [x] (計劃外)`memory/adapters/claude_export.py`:讀 **Claude 網頁版對話匯出**(json / zip / 資料夾)—— 見第九節偏離 1
- [~] `gate.py`:格式驗證 / 去重 / 時間正規化 / **密鑰清洗** —— 前三項已完成(`memory/gate.py`),密鑰清洗未做
- [x] 寫進 `vault/raw/`,append-only,檔名時間戳 —— `memory/raw_store.py`
- [ ] launchd 每 N 分鐘跑一次

**M1 沒有抽取、沒有索引、沒有檢索。先讓原文進得來。**
完成條件:不碰電腦,vault/raw/ 自己長出東西。

### M2 — 抽取器

- [ ] `extract.py`:Claude API + structured output,schema = L1 五欄位
- [ ] 判斷 有用 / 不確定 / 沒用
- [ ] 不確定 → `vault/queue/`
- [ ] 沒用 → 標記保留,不進索引(第 10 則)
- [ ] 衍生欄位寫回同檔 frontmatter(第 32 則暫採此方案,見未解)

**完成條件:跑過三十則真實資料,schema 沒被打破;打破的那幾則就是第 07 則說的產出,回頭改契約。**

### M3 — 檢索

- [x] 結構查詢:照 type / status / 時間撈 —— `memory/index.py`(用可重建的 JSON 索引,不是 ripgrep)
- [ ] 回答組裝:只用檢索到的片段,附來源檔路徑,撈不到就說撈不到(第 12 則)
- [ ] 語意檢索:**延後**,等結構查詢真的不夠用再說

### M4 — 代勞層讀記憶

- [ ] vault 上一個 MCP server,讓 Claude 讀
- [ ] 這是整個計劃裡 MCP 唯一該出現的地方

**M4 之前不碰 MCP。**

---

## 五、Repo 結構

```
heti/
├── PLAN.md                  # 這份文件(L2)
├── README.md                # 一頁:這是什麼、怎麼跑
├── contract/                # L1 — 改動要有成本意識
│   ├── schema.json          # 五欄位 + type 四值
│   ├── normalize.md         # 正規化關卡規則
│   └── extract-criteria.md  # 抽取判準(第 25 則說的真正風險)
├── src/heti/                # L2 — 耗材
│   ├── adapters/
│   │   └── claude_code.py
│   ├── gate.py
│   └── extract.py
├── config/
│   └── heti.yaml            # 設定與資料分離(第 06 則)
└── .cursor/                 # 已取代的舊計劃,保留不刪
```

`vault/`(L0)**建議放獨立的私有 repo**,理由:

1. vault 要自動 commit(每次捕捉),程式碼不要。混在一起會讓自動 commit 跟你的程式碼 commit 互相干擾。
2. 第 02 則要求「程式全刪光 L0 還看得懂」—— 分開是這句話最直接的實作。
3. Obsidian 直接開那個 repo 當 vault,乾淨。

---

## 六、明確不做的事

| 不做 | 依據 |
|---|---|
| 向量庫 / embedding | 第 13 則,v1 用結構查詢 |
| MCP(M4 之前) | 第 04 則 |
| agent / loop 框架 | 第 04 則 |
| 手機寫入路徑 | 第 36 則之後 Obsidian 是閱讀器,不是入口 |
| 權限 / 多使用者 / 帳號 | 第 06 則 |
| 常駐程序 | 第 20 則(待確認),v1 用 launchd 定時 |
| 本地跑大模型 | 第 05 則 + 第 26 則(16GB) |
| 判斷層 / 主動層 | 第 03 則,第一個迴路跑通之後才碰 |

---

## 七、未解(動工前不必全解,但要知道)

| # | 問題 | 何時會咬到 |
|---|---|---|
| 20 | 常駐 vs 事件觸發,**還沒你點頭** | M1。建議:launchd 定時,不常駐 |
| 29 | 原文更正機制(追加而非覆寫,但舊的還要不要被檢索到) | M2 |
| 30 | 刪除。「原文永不修改」與「我要能刪掉某一則」直接衝突 | M2 |
| 32 | 衍生資料放同檔 frontmatter 還是獨立檔 | M2,計劃暫採同檔 |
| 33 | 待確認佇列超時規則 | M2,第 43 則說自動捕捉後佇列會爆 |
| 34 | Mac mini 是否常開 | M1 |
| 35 | created 分不出「發生時間」與「寫入時間」 | 不急,定義先定死 |
| 42 | **他人的資料**。來源一是你自己的對話,不咬;來源二(郵件)立刻咬 | 接第二個來源前必須解 |
| 43 | 自動捕捉的量級效應。成本已解,佇列與保存策略未解 | M2 |
| — | L1 契約改了,已抽取過的怎麼遷移 | M2 之後 |
| — | 抽取判準是 L1 還是 L2 | M2。建議:判準 L1,prompt 文字 L2 |
| — | iCloud + git 同一個資料夾是否會衝突 | M0,要實測 |

---

## 八、風險

**最大的風險不是技術。** 第 25 則已經說了:風險在抽取判準寫不寫得出來,以及會不會持續用。

第 22 則記錄的模式:五月、六月、九月卡在同一個位置,每次縮回來就再產一份文件,文件三份、vault 檔案零則。

**這份文件是第四份。** 它唯一的價值是被執行掉。
M0 完成之前,不要再產生第五份文件。

---

## 九、進度與偏離(2026-09-24 更新)

這一節記錄計劃和實際執行的差距。**勾選狀態以第四節為準,這裡說明為什麼。**

### 已完成

2026-09-24 一次隔夜自主執行(計劃:`plans/overnight-memory-loop-plan.md`;報告:`plans/overnight-memory-loop-report.md`)產出 `memory/` 套件:

| 模組 | 做什麼 | 對應 |
|---|---|---|
| `memory/contract.py` | 五欄位、type 四值、筆記驗證 → 問題 / 警告 | #07、#35 |
| `memory/frontmatter.py` | frontmatter 解析,值一律保持字串 | #02 |
| `memory/raw_store.py` | 原始層寫入:`open "x"` + `chmod 0444`,檔名時間戳,沒有更新 / 刪除路徑 | #08、#14 |
| `memory/gate.py` | 正規化關卡:格式、時間界限、時區必填、去重;拒絕的項目有計數和理由 | #37 |
| `memory/adapters/claude_export.py` | Claude 網頁版匯出 → 可讀逐字稿 + 原始 JSON 原封保留 | #38、#08 |
| `memory/index.py` | 可重建索引 + 結構查詢(type / status / 時間 / kind),每筆附路徑;拒絕把索引建在 raw 裡 | #10、#11、#12、#13 |
| `memory/seed_split.py` | seed 合集 → 一則一檔,只印數量 | M0 |
| `memory/__main__.py` | 一次性 CLI:`ingest-claude`、`index rebuild`、`query`、`validate`、`seed-split` | #06、#20 |

75 個測試,只用合成資料,Python 3.9 / 3.11、離線都通過。舊程式一行都沒動。

### 偏離

| # | 計劃寫的 | 實際 | 原因 | 要做的 |
|---|---|---|---|---|
| 1 | 第一個來源:Claude Code 本地 JSONL(決定 B) | 做的是 Claude 網頁版對話匯出 | 隔夜計劃依 #38/#39「從 AI 對話開始、Claude 對話可以匯出」選了匯出檔,沒有對齊決定 B | **確認第一個來源**。若維持決定 B,補寫 JSONL 轉接器;匯出轉接器可留可丟(L2) |
| 2 | 程式放 `src/heti/`,規則放 `contract/` | 程式放 `memory/`;L1 規則寫在 `memory/contract.py` 常數 | macOS 不分大小寫,`heti/` 會和舊的 `Heti/` 撞名 | M0 清掉舊程式後,決定是否搬到 `src/heti/`,並把 L1 規則抽成 `contract/` 下的文件 |
| 3 | 關卡包含密鑰清洗 | 沒有 | 隔夜計劃範圍只含格式、去重、時間 | 接真實資料前補上(#40) |
| 4 | launchd 定時跑 | 只有一次性 CLI | #20 未解,agent 不代為決定 | 等 #20、#34 定案 |
| 5 | 結構查詢用 frontmatter + ripgrep | 用可重建的 JSON 索引 | 方便做時間範圍與 kind 過濾 | 無;索引可隨時刪掉重建,符合 #11 |

### BLOCKED

- **seed 進 vault(M0)**:執行容器裡沒有 seed 檔。在有 seed 的機器上跑:
  `python3 -m memory seed-split <seed 合集> --out <vault>/00-seed`,再跑 `python3 -m memory validate`。
- **完整隱私檢查**:同上,缺 seed 所以只跑了降級版。有 seed 時跑 `HETI_SEED=<seed> python plans/tools/privacy_check.py --repo`。

### 待使用者決定(來自隔夜報告)

- raw 的 frontmatter 格式(L1 草案):`source / source_id / source_sha256 / occurred_at / ingested_at`
- raw 的形式 = 可讀逐字稿 + 原封 JSON,能不能接受為 L0
- 對話持續增長時,查詢是否只顯示最新版本(#29)
- `status` 的合法值
- frontmatter 多出來的欄位(例如 `tags`)是否允許;目前只給警告
- raw 的 `--since` 比 `occurred_at`(目前)還是 `ingested_at`
- Claude 匯出格式是憑記憶寫的,**還沒用真實匯出檔驗證過**
- repo 是公開的:Hēti 是否搬到私有 repo

### 下一步建議(依 PLAN.md 順序)

1. **M0**:把 seed 放進 vault(上面的 BLOCKED 項)。這是第 22 則那句「vault 檔案零則」不再成立的條件。
2. 回答偏離 1(第一個來源)與第七節的 #20。
3. M0 清除舊程式(決定 D)。
4. 補密鑰清洗,然後用真實資料跑 M1。
