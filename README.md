# floorplan — 室內平面圖協作專案

用 [draw.io](https://app.diagrams.net)（`.drawio` 格式）畫室內平面圖，
用 Git 做版本控管，透過 [claude.ai/code](https://claude.ai/code) 派任務給 Claude
協助調整格局。

## 專案目的

以純文字（XML）保存室內平面圖，讓格局的每一次調整都能：

- **被版本控管**：每次改動都有 diff，可回溯、可比較、可回復。
- **可協作**：用 PR 審查格局變更，就像審查程式碼一樣。
- **可自動化**：交由 Claude 依固定慣例修改，並自動驗證檔案正確性。

## 檔案結構

| 檔案              | 說明                                                          |
| ----------------- | ------------------------------------------------------------- |
| `floorplan.drawio` | 平面圖本體，draw.io 的 mxGraph XML。1 px = 1 cm，四個圖層。   |
| `CLAUDE.md`       | 繪圖慣例（比例、牆厚、圖層、標籤格式、改圖規則）。**改圖前必讀。** |
| `README.md`       | 本說明檔。                                                    |

平面圖分為四個圖層：`rooms`（房間/牆）、`doors`（門）、`labels`（房名尺寸面積）、
`dims`（尺寸標註）。詳細慣例見 [`CLAUDE.md`](./CLAUDE.md)。

## 目前格局

總體 700 cm × 700 cm，共六間：客廳、餐廳、主臥、次臥、衛浴、廚房。

## 協作流程

1. **在 claude.ai/code 下任務**：描述你要的格局變更
   （例如「主臥加寬到 3.8m，次臥對應縮小」）。
2. **Claude 修改並推 branch**：Claude 依 `CLAUDE.md` 慣例修改 `floorplan.drawio`，
   同步更新受影響房間的尺寸/面積標籤，驗證 XML well-formed 後推到功能分支。
3. **審查 diff**：在 GitHub 上檢視這次改動的 diff，確認格局符合預期。
4. **建 PR 並 merge**：滿意後開 Pull Request，合併回主分支。
5. **回 draw.io 重新載入查看結果**：在 draw.io 重新載入 `floorplan.drawio`，
   即可看到更新後的平面圖。

## 在 draw.io 連接這個 GitHub repo

1. 開啟 <https://app.diagrams.net>。
2. 起始畫面選擇儲存位置時點 **GitHub**（或 `Extras → ...` / 開檔對話框中選 GitHub）。
3. 依指示 **授權 draw.io 存取你的 GitHub 帳號**。
4. 選擇本 repo、分支與 `floorplan.drawio` 開啟。
5. 在 draw.io 編輯後 **Save**，會直接 commit 回該分支；
   合併或他人更新後，用 **File → 重新載入（Reload）** 取得最新版本。

> 提示：以 Claude 修改時是直接編輯 XML；用 draw.io 手動編輯時，請仍遵守
> [`CLAUDE.md`](./CLAUDE.md) 的圖層與標籤慣例，方便雙方協作。
