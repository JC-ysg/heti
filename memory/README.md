# memory：Hēti 記憶層的第一個迴圈

把 Claude 對話匯出檔 → 經過正規化閘門 → 寫進只能新增的 raw 層（完整保留原始 JSON）→ 建立可隨時重建的索引 → 用結構化查詢找回來，每筆答案都附檔案路徑。

> ⚠️ **警告：第一次真正匯入前，請先用一個拋棄式的 `--vault` 試跑。** 匯入 raw 的東西目前沒有刪除機制（#30），而且匯出檔裡含有別人說的話（#42）。

## 需求

- Python **≥ 3.9**（已在 3.9 與 3.11 上跑過全部測試）
- 只依賴標準函式庫 + PyYAML：

```bash
python3 -m pip install pyyaml
```

在 repo 根目錄執行（`memory/` 是一個套件，用 `python3 -m memory` 呼叫）。

## 三個指令就能用

```bash
# 0. 先用拋棄式 vault 試（強烈建議）
export HETI_VAULT=/tmp/heti-try

# 1. 匯入 Claude 匯出檔（conversations.json，或含它的 zip / 資料夾）
python3 -m memory ingest-claude ~/Downloads/claude-export.zip

# 2. 重建索引（隨時可刪、可重建）
python3 -m memory index rebuild

# 3. 查詢（每行：path  kind  type  status  about）
python3 -m memory query --kind raw --since 2026-01-01
python3 -m memory query --type open
```

其他指令：

```bash
python3 -m memory validate              # 對整個 vault 做筆記契約檢查，預設只印數字
python3 -m memory validate --details    # 逐筆列出問題與警告
python3 -m memory seed-split <seed-all.md> --out <dir>   # 把種子合集拆成一檔一則
```

## 環境變數

| 變數 | 用途 |
|---|---|
| `HETI_VAULT` | vault 位置。也可以每次用 `--vault` 指定。**兩者都沒給就報錯，沒有預設值**（#06：不寫死任何個人路徑）。 |

## 目錄結構

```
<vault>/
  *.md, 子資料夾/*.md   ← 你手寫的筆記（L0），會被索引
  raw/                  ← 只能新增的原始層（每則一檔，檔名以時間開頭，權限 0444）
  .heti-index/          ← 衍生索引：index.json、problems.json、.heti-index 標記檔
  .obsidian/ .trash/ …  ← 以 . 開頭的資料夾一律不索引
```

程式碼：

```
memory/
  contract.py      筆記契約：5 個欄位、4 種 type、validate_note
  frontmatter.py   frontmatter 解析（值一律保持字串）
  raw_store.py     只能新增的 raw 層（沒有 update/delete/overwrite）
  gate.py          正規化閘門：格式、重複、時間
  adapters/claude_export.py   Claude 匯出檔轉接器（無損）
  index.py         可重建的結構化索引 + 查詢
  seed_split.py    種子合集拆檔工具
  __main__.py      CLI（一次性執行，沒有常駐程式）
  tests/           只用合成資料
```

## 筆記契約（#07）

每則筆記的 frontmatter 要有 5 個欄位：`type`、`created`、`about`、`source`、`status`。

- `type` 必須是 `decision`、`learning`、`fact`、`open` 其中**一個**。
- 缺欄位、type 不合法或多個、`created` 無法解析 → **問題**：不進索引，但檔案不會被刪（記在 `problems.json`）。
- 多出來的欄位（例如 `tags`）→ **警告**：照樣進索引。
- `status` 只計數、不判斷（契約還沒定義允許的值）。

## raw 層格式（L1 草案）

每個 raw 檔的 frontmatter：`source`、`source_id`、`source_sha256`、`occurred_at`、`ingested_at`。raw 永遠不會有 `type` 欄位。

Claude 對話的 raw 內文 = 方便人眼閱讀的逐字稿 + `## Source JSON (verbatim)` 底下完整的原始 JSON。tool_use、thinking、附件、檔案等全部都在 JSON 區塊裡，一個都不丟。

- 同一份匯出檔匯入兩次 → 新增 0 個檔案。
- 對話變長後再匯入 → 新增 1 個檔案，舊檔一個位元組都不變。
- 去重鍵 = `(source, source_id, source_sha256)`，`source_sha256` 是原始物件的雜湊，跟呈現方式無關。

## 做了什麼、沒做什麼

做了：

- Claude 匯出檔匯入、正規化閘門、只能新增的 raw 層、可重建索引、依 type / status / 日期 / kind 的結構化查詢、契約檢查、種子拆檔。

刻意沒做（等待決定或不在這一步的範圍）：

- 修正與刪除（#29/#30）、備份（#31）、衍生資料放哪（#32）、佇列逾時（#33）、常駐程式（#20）、他人資料與匯入範圍（#42）。
- 語意搜尋、分塊（#46）、萃取層（等 #32/#40）、LLM 呼叫、任何網路存取。
- 外掛系統、抽象基底類別、provider 介面（#04）。

## 架構依據（引自計畫 §0 表格原文）

| # | Constraint on the code |
|---|---|
| #02 | Value lives only in L0 (plain markdown) and L1 (fields and rules). The L2 code must be replaceable within a day. L0 must be readable by eye after all the code is deleted. |
| #04 | Do not build anything in advance for "being able to do everything later": no plugin systems, abstract base classes, or provider interfaces. |
| #06 | Single user. No hard-coded personal paths, keys, or vault locations. |
| #07 | Note contract: 5 fields `type/created/about/source/status`; `type` ∈ {decision, learning, fact, open}; exactly one type per note. It is still being tested by hand: when something doesn't fit, surface it, don't drop it. |
| #08/#14 | The raw layer's only job is to lose nothing; losing original text is a fatal error. It is append-only, no program may modify it, and models never write back to it. One file per item, named by timestamp. |
| #10/#11 | Anything unusable is not deleted, only left out of the index. The index can be deleted and rebuilt at any time. |
| #12/#13 | Query answers must include the source path, and must not be made up. Tonight only builds structural queries (type/status/time). |
| #35 | A note's `created` = the time it was written into the vault. This definition does not change tonight. |
| #37 | Adapters (L2, one per source) and the normalization gate (L1, the only one, which checks format, duplicates, and time). |
| #38/#39 | Connect one source at a time, starting with AI conversations. Claude conversations can be exported. |
| #46 | Scale is solved by chunking in the index layer. |

## 跑測試

```bash
python3 -m pip install pytest pyyaml
python3 -m pytest memory/tests -q
```
