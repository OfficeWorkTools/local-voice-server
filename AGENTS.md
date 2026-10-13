# 部署與驗證

安裝、修復、升級或測試前，先讀完整 README.md，依其中的安裝步驟與驗收條件執行。固定來源的唯一設定是 config/versions.json。

保持 SenseVoice 預設 CPU FP32、loopback 綁定與獨立 user systemd 單元。其他模型依 config/versions.json 的 profile 精度驗證。實際 class、權重與 dtype 由 scripts/verify_model.py 的 LoadModel 驗證，模型名稱不是精度證據。變更來源、補丁或 profile 後，重新檢驗 hash、dtype、模型切換、繁體 HTTP 與重啟。

既有服務或連接埠由使用者擁有；測試另選空埠，完成後停止及 disable 臨時單元。VocaLinux 設定由使用者管理。模型、cache、credentials、音訊、log 和機器專屬設定留在 .localai/，只提交原創程式及文件。

繁體轉換使用固定 OpenCC s2t，在原生 FunASR 組裝 transcript 之前執行，JSON text 與 segments 必須一致。維護可校驗的小補丁，不加入 LLM 改寫。ITN 與 training 辨識不是此部署的已驗證能力；記錄真實 ASR 誤辨，不以另一個環境成功取代安裝驗證。
