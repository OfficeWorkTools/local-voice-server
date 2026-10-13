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

## 繁體與模型切換驗證，2026-10-13

以下是加入原生 FunASR OpenCC 擴充與 profiles 後的驗證，前段及原 `api.json`／`fp32.json` 保留初始部署紀錄。

- OpenCC `s2t` 檢查中文、空字串及英文／數字／換行；見 [validation/conversion.json](validation/conversion.json)。固定官方後端的小補丁與 helper／wheel hash 見 [validation/backend-extension.json](validation/backend-extension.json)。
- 在獨立新目錄、沒有舊 binary／venv／權重／cache 的環境，於 8769 完成完整下載、安裝、OpenCC 擴充、FP32、暖機、自測；再重跑安裝與重啟。兩段真實 HTTP 繁體結果見 [validation/clean-traditional-api.json](validation/clean-traditional-api.json)。這是同一台實體電腦的新 runtime，沒有冒充另一台機器。
- 於 8768 及正式 8767 驗證 Paraformer → SenseVoice 往返切換。實際檔案 hash、模型 class、precision、model directory 均不同；每次 system endpoint 僅有一個常駐模型。正式 8767 已恢復 SenseVoice，見 [validation/switch.json](validation/switch.json)。
- SenseVoice 真實載入為 `SenseVoiceSmall`、CPU、917 個 float32 參數張量，部署 YAML 與模型 symlink 必須匹配 profile；見 [validation/sensevoice-model.json](validation/sensevoice-model.json)。此數目是參數張量數，不是 scalar 參數總量。
- 第二個官方 `funasr/paraformer-zh` 的實際 class 為 `Paraformer`，956 個 float32 參數張量，權重 SHA256 與 SenseVoice 不同；見 [validation/paraformer-model.json](validation/paraformer-model.json)。
- 中文及中英音訊、四種 language、JSON text／segments 一致、GUI 可達、模型清單：見 [validation/traditional-api.json](validation/traditional-api.json)、[validation/paraformer-api.json](validation/paraformer-api.json)。原生輸出現在經字詞轉繁體，`training` 仍有誤辨，沒有宣稱改善辨識。
- 同埠關閉後的 TIME_WAIT 曾被探測誤判為占用；加入 SO_REUSEADDR 後，正式 8767 更新、重啟與往返切換通過，原 8766 服務持續運作。舊 LocalAI 檔案與單元保留但停用，防止重新開機搶同一埠。

未測另一台電腦、斷網、重新開機、任意其他 backend、串流／字幕格式、長句及一般字錯率。新 profiles／繁體擴充並未增加 ITN、第二個 HTTP 埠、代理或 LLM 改寫。
