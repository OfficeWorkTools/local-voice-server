# 乾淨部署驗證

2026-10-13 在 Ubuntu 26.04.1 LTS、Linux x86_64、Ryzen 9 7945HX 上，以此 repo 的全新 `.localai/` 和 loopback 埠 8768 執行安裝。沒有複製原服務的二進位、模型、Python 環境或 cache；下載時核對固定來源與 hash。

首次執行在官方封裝的 Python 路徑定位處停止。加入官方 `run.sh --help` 初始化後，重跑同一乾淨實例，重用已校驗的下載檔並成功。這個初始化已包含在 `deploy.py install` 與 `verify-fp32`。

通過的範圍：

- 官方 LocalAI binary SHA256、CPU FunASR OCI digest、backend.py hash、全部必要模型檔及兩個原始音訊 hash。
- 官方原生 `BackendServicer.LoadModel` 真實載入，917 個參數全為 CPU `torch.float32`，模型類別為 SenseVoiceSmall。證據見 [validation/fp32.json](validation/fp32.json)。
- 原生 FSMN VAD 的權重、配置、CMVN 校驗；完整安裝重跑，以及 stop → repair-link → start → test。
- 模型相對路徑 symlink、user systemd enable／start、真實中文啟動暖機、Web UI HTTP 200 與 `/v1/models`。
- 16 kHz mono 16-bit PCM WAV 的 multipart API：中文及中英樣本，各使用 `zh`、`auto`、空字串與省略 language。
- 從 checkout 外的工作目錄執行 `restart` 與完整 `test`，再次通過暖機、GUI、模型清單及全部音訊請求。
- 拒絕 `--port 0`；Python 編譯檢查與 Git whitespace 檢查。
- 提交檔案的秘密、機器專屬絕對路徑、大小與 Git ignore 檢查；權重、音訊、執行檔、快取均未提交。
- 停止並 disable 8768 臨時單元後，原 8766 ONNX 與 8767 LocalAI 的健康／模型清單仍正常。

重啟後的完整 HTTP 延遲、原生文字與英文誤辨記錄見 [validation/api.json](validation/api.json)。中文與中英都有文字輸出，但四種 language 都沒有辨識出參考文字中的 `training`；這是功能成功、該樣本英文辨識失敗，並未量測一般字錯率。

未驗證：另一台實體電腦、其他 Linux 發行版／架構、重新開機、完全斷網啟動、從 `Linger=no` 啟用、長句、高負載、使用者麥克風或 VocaLinux GUI 聽寫。系統套件原已安裝，因此 README 的 apt 前提步驟不是乾淨 OS 重建證據。後端有自己的固定 Python 套件，但 ModelScope VAD 的上游 cache／網路檢查仍可能影響初次啟動。
