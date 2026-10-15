# 部署與驗證

## README 流程圖與功能追蹤，硬性規定

新增、修改或移除功能、資料流、模型接入、前後處理或部署步驟時，必須在同一變更更新 README.md 的流程圖及功能對照表。每項功能須說明作用、設定或程式入口、對辨識內容／速度的影響與驗證限制；未實作、未啟用或未驗證的功能須明確標示。

圖的來源保存在 diagrams/。修改後執行 `python3 scripts/diagrams.py` 同步 README，再執行 `python3 scripts/diagrams.py --check`，並渲染修改的圖確認語法與可讀性。沒有同步圖文、來源對照與檢查結果，工作不算完成。撰寫技術文件時使用 technical-writing 與 reviewing-technical-prose 技能；修改此規則時使用 writing-for-agents 技能。

## 部署要求

安裝、修復、升級或測試前，先讀完整 README.md，依其中的安裝步驟與驗收條件執行。固定來源的唯一設定是 config/versions.json。

保持 SenseVoice 預設 CPU FP32、loopback 綁定與獨立 user systemd 單元。其他模型依 config/versions.json 的 profile 精度驗證。實際 class、權重與 dtype 由 scripts/verify_model.py 的 LoadModel 驗證，模型名稱不是精度證據。變更來源、補丁或 profile 後，重新檢驗 hash、dtype、模型切換、繁體 HTTP 與重啟。

既有服務或連接埠由使用者擁有；測試另選空埠，完成後停止及 disable 臨時單元。VocaLinux 設定由使用者管理。模型、cache、credentials、音訊、log 和機器專屬設定留在 .localai/，只提交原創程式及文件。

繁體轉換使用固定 OpenCC s2t，在原生 FunASR 組裝 transcript 之前執行，JSON text 與 segments 必須一致。維護可校驗的小補丁，不加入 LLM 改寫。ITN 與 training 辨識不是此部署的已驗證能力；記錄真實 ASR 誤辨，不以另一個環境成功取代安裝驗證。
