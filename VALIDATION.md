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

## Whisper GPU 安裝與切換驗證，2026-10-15

完整 large-v3 已加入正式 8767。官方 LocalAI 原生 NVIDIA faster-whisper 後端、模型 revision、必要檔案 hash 與原始 backend.py hash 均固定在 config/versions.json 的 whisper 區段。先在 8768 驗證，再發布模型設定；準備與發布流程重跑通過，沒有改動 VocaLinux 設定。

- 原生 BackendServicer.LoadModel 真實載入 WhisperModel／CTranslate2 Whisper，device=cuda、compute_type=float32；所有模型檔 hash 通過。實際封裝版本為 faster-whisper 1.2.1、CTranslate2 4.8.2、PyTorch 2.4.1。見 [validation/whisper-model.json](validation/whisper-model.json)。這是 FP32 推論證據，不是發布權重原始儲存精度的聲明。
- 小補丁明確傳遞 en、zh、auto／省略語言，使用 PCM16 WAV 解碼並套用 OpenCC s2t。以真實 RPC 方法驗證語言欄位及 text／segments 繁體一致，補丁 hash 見 [validation/whisper-extension.json](validation/whisper-extension.json)。
- 在獨立 8768 與正式 8767，各使用中文、純英文與中英夾雜音訊，測 zh、en、auto、省略 language，均回應非空 JSON；合適語言下的中文繁體及英文關鍵字通過。見 [validation/whisper-api.json](validation/whisper-api.json)。training 樣本仍誤辨，不能把功能驗證當成準確率通過。
- 與先前比較測試相同的 30 段錄音，透過原生 LocalAI API 重播。忽略大小寫、空白、標點與繁簡差異後，30/30 與先前完整 Whisper 結果一致。這是部署輸出一致性，不是 30/30 辨識正確。見 [validation/whisper-native-parity.json](validation/whisper-native-parity.json)。
- 正式 8767 完成 Whisper → SenseVoice → Whisper → SenseVoice 往返切換；每次 system endpoint 均只列一個常駐模型。見 [validation/whisper-switch.json](validation/whisper-switch.json)。
- 正式服務重啟後再次驗證三個模型可列出、SenseVoice 暖機、Whisper 載入轉錄及換回 SenseVoice。見 [validation/whisper-restart.json](validation/whisper-restart.json)。SenseVoice 再次通過 CPU FP32、917 個參數張量與固定 VAD hash 驗證。
- Installed GUI 顯示三個模型。8768 臨時實例已停止，開機預載與最終常駐均維持 SenseVoice；Whisper 可由 GUI Load 或 API model 載入。

未測使用者麥克風／VocaLinux 完整聽寫、其他電腦、重新開機、FP16／INT8、長錄音或高負載。Whisper 仍可能把英文辨成中文；繁體轉換只改字形，不修正辨識內容。

## Whisper large-v3-turbo 安裝與切換驗證，2026-10-15

Turbo 已加入正式 8767，API Model 為 `whisper-large-v3-turbo`。它與完整版本共用已固定的原生 NVIDIA faster-whisper 後端及同一份補丁，權重、revision、模型目錄與驗證報告則分開。來源與檔案 SHA256 在 config/versions.json 的 whisper_turbo；沒有修改 VocaLinux 設定或開機預載選擇。

- 所有 Turbo 模型檔案核對固定來源 hash，原生 LoadModel 實際載入為 WhisperModel／CTranslate2 Whisper、CUDA、float32，並驗證 en、zh、auto／省略語言的傳遞及繁體 text／segments 一致。見 [原生模型證據](validation/whisper-turbo-model.json)與[後端擴充 hash](validation/whisper-turbo-extension.json)。
- 獨立 8768 與正式 8767，各測中文、純英文及混合樣本的 zh、en、auto、省略 language，共各 12 次 API 轉錄；均為非空 JSON，合適語言下中文繁體及英文關鍵字通過。見[獨立埠 API](validation/whisper-turbo-staging-api.json)與[正式 API](validation/whisper-turbo-api.json)。training 在這個短樣本有辨識出，但不代表所有英文混合詞都正確。
- 原有同批 30 段錄音透過原生 Turbo API 重播，正規化輸出 30/30 與先前 Turbo 比較結果相同。這是部署一致性，不是 30/30 辨識正確。見[同音訊核對](validation/whisper-turbo-native-parity.json)。
- 正式服務重啟後列出四個模型，預載仍為 SenseVoice，隨後 Turbo 與完整版本的 API 均通過。見[重啟證據](validation/whisper-turbo-restart.json)。完整 Whisper API 使用省略 --model 的舊指令回歸通過。
- 正式服務完成 Turbo → 完整 Whisper → SenseVoice → Turbo → 完整 Whisper，每次 system endpoint 僅列出當次請求模型，最終恢復原本使用的完整 Whisper。見[切換證據](validation/whisper-turbo-switch.json)。SenseVoice 另以原生 LoadModel 再次確認 CPU、917 個 float32 參數張量、設定及 VAD hash，見[SenseVoice 回歸](validation/whisper-turbo-sensevoice-model.json)。
- prepare／publish 重跑通過；scripts/test_whisper_profiles.py 檢查完整與 Turbo 各自發布，拒絕其他模型 ID、錯誤權重 hash 及變更後的設定證據。Python 編譯及 Git whitespace 檢查通過。
- Installed GUI 顯示四個模型及 Turbo 的 Idle 項目。8768 臨時程序已停止，正式 user service 維持 active／enabled；原 8766 服務未變更。

未測使用者麥克風／VocaLinux 完整聽寫、重新開機、其他電腦、斷網啟動、長錄音、高負載或 GPU FP16／INT8。兩個 Whisper profile 都可能把英文辨成中文；模型切換後首次載入延遲不等於暖機後辨識速度。
