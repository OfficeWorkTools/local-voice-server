# 部署與驗證

安裝、修復、升級或測試前，先讀完整 README.md，依其中的安裝步驟與驗收條件執行。固定來源的唯一設定是 config/versions.json。

保持原生 FunASR CPU FP32、loopback 綁定與獨立 user systemd 單元。實際 dtype 由 scripts/verify_fp32.py 的 LoadModel 驗證，模型名稱不是精度證據。變更下載來源或後端後，重新檢驗 hash、dtype、重啟及真實音訊 API。

既有服務或連接埠由使用者擁有；測試另選空埠，完成後停止及 disable 臨時單元。VocaLinux 設定由使用者管理。模型、cache、credentials、音訊、log 和機器專屬設定留在 .localai/，只提交原創程式及文件。

繁體輸出、ITN 與 training 辨識都不是此部署的已驗證能力。記錄真實結果，不以另一個環境成功取代乾淨安裝驗證。
