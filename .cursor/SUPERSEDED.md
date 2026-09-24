# `.cursor/` 已被取代

**日期:2026-09-23**

這個資料夾裡的所有檔案描述的都是 Hēti **改版前**的系統。依 `PLAN.md` M0「`.cursor/` 舊計劃檔標記為已取代(保留,不刪)」,這些檔案全部保留,但**不再代表現行方向**。

## 現行方向在哪裡

| 檔案 | 用途 |
|---|---|
| `/CLAUDE.md` | 給 agent 的入口:讀什麼、不讀什麼、不可違反的原則 |
| `/PLAN.md` | 工程計劃:已定的決定、架構、里程碑、未解問題、進度 |
| `/README.md` | 給人看的專案首頁 |

## 舊的和新的差在哪

| 面向 | 舊(本資料夾) | 新(PLAN.md) |
|---|---|---|
| 定位 | 「Jarvis 級」個人 AI 作業系統,什麼都做 | 記憶是底層,給代勞的 AI 夥伴讀(#01) |
| 價值在哪 | 功能與自主能力 | 只在 L0 資料與 L1 契約;程式是耗材(#02) |
| 推理 | 本地跑 LLM(RTX 3070) | 走雲端 API;主權在資料,不在算力(#05) |
| 記憶後端 | OpenMemory / mem0 + 向量嵌入 | 純 markdown + frontmatter;v1 不裝向量庫(#13) |
| 捕捉 | 螢幕、語音、檔案全都抓 | 被動觀察,一次接一個來源(#36、#38) |
| MCP | 一開始就做 MCP 工具 | M4 代勞層才出現 |
| 框架 | 多模組、多 agent | 框架數量為零(#04) |
| UI | Tkinter 控制面板、遊戲化 | 不做;Obsidian 當閱讀器 |

## 本資料夾的內容

- `heti-project-overview.mdc`、`rules/heti-project-rules.mdc`:舊願景與舊規則(已加上取代橫幅)
- `legacy-README.md`:改版前的 repo README
- `memory_*_spec.mdc`、`*_endpoint_*.md`、`openmemory_*.mdc`:OpenMemory API 與監控器的規格
- `mvp_*.mdc`、`ui_connection_validation.mdc`、`structure_review.mdc`:舊 MVP 的狀態與審查
- `openmemory_client_test_results*.log`:舊客戶端的測試紀錄
