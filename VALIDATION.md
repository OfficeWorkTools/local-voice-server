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

## Qwen 與 FireRed CPU 安裝驗證，2026-10-15

三個 CPU profile 已加入正式 8767：`qwen3-asr-0.6b-cpu`、`qwen3-asr-1.7b-cpu`、`fireredasr2-aed-cpu`。來源 revision、檔案 SHA256、原生 CPU OCI digest、FireRed 程式 archive 與 fbank wheel 均固定在 `config/versions.json` 的 `modern_cpu_asr`；原創 gRPC 擴充的 hash 見 [modern-cpu-extension.json](validation/modern-cpu-extension.json)。沒有修改 VocaLinux 設定。

- Qwen 0.6B 與 1.7B 真實載入固定 Q8_0 GGUF，使用原生 audio.cpp `qwen3_asr` 引擎、`backend:cpu`、8 threads。檢查原生子程序沒有載入 CUDA／cuBLAS／cuDNN，並以相同模型識別進行中文、英文與混合音訊轉錄。見 [0.6B 模型證據](validation/qwen3-asr-0.6b-cpu-model.json)及 [1.7B 模型證據](validation/qwen3-asr-1.7b-cpu-model.json)。
- FireRed 真實載入官方 AED 為 `FireRedAsrAed`，所有參數 device=cpu、dtype=torch.float32，中文、英文與混合音訊皆回傳非空文字。沒有執行 FireRed LLM、VAD、標點或串流整套系統。見 [FireRed 模型證據](validation/fireredasr2-aed-cpu-model.json)。
- 臨時 8768 與正式 8767 都通過短錄音 API 驗證。Qwen 各測 `zh`、`en`、`auto` 與省略語言，FireRed 測 `auto` 與省略語言。Qwen 的 zh/en 轉為原生提示 Chinese/English，Auto 不加提示。FireRed 沒有強制語言介面，wrapper 明確拒絕 zh/en。三個 profile 的繁體 text 與 segments 一致；單元檢查亦確認 Qwen words 轉繁體一致。見 [0.6B staging](validation/qwen3-asr-0.6b-cpu-api-8768.json)、[1.7B staging](validation/qwen3-asr-1.7b-cpu-api-8768.json)、[FireRed staging](validation/fireredasr2-aed-cpu-api-8768.json)與各自的 [0.6B 正式](validation/qwen3-asr-0.6b-cpu-api-8767.json)、[1.7B 正式](validation/qwen3-asr-1.7b-cpu-api-8767.json)、[FireRed 正式](validation/fireredasr2-aed-cpu-api-8767.json)。
- `scripts/test_cpu_asr.py` 通過 CPU-only、未知模型拒絕、語言對應、繁體一致及發布證據隔離檢查。發布拒絕錯誤模型 ID、變更的設定／後端 hash、未通過 API 及錯誤原生權重證據；既有 Whisper 發布檢查亦通過。
- 正式服務重啟列出七個模型並預載 SenseVoice，隨後完成三個 CPU 模型 → SenseVoice → Turbo → 完整 Whisper 的切換，每次僅有一個 LocalAI 後端常駐。最終恢復本次工作前的 `whisper-large-v3`，見 [重啟及切換](validation/modern-cpu-restart-switch.json)。SenseVoice 原生驗證仍為 CPU、917 個 float32 參數張量，權重、設定與 VAD hash 通過，見 [SenseVoice 回歸](validation/modern-cpu-sensevoice-model.json)。
- Installed 管理頁實際顯示七個模型。臨時 8768 已停止，正式 user service active／enabled，原 8766 健康回應正常。

這些是安裝與 API 功能驗證，沒有完整同批錄音的準確率排名。混合測試音訊中的 `training`，Qwen 0.6B 與 FireRed 的 Auto 仍辨成「圈子」，Qwen 1.7B 在這一段保留 `training`；單一例子不能代表整體準確度。報告秒數包含初次載入，部分 staging／原生驗證同時執行，不能當成公平效能排名。未測使用者麥克風、完整 VocaLinux 聽寫、OS 重新開機、其他電腦、離線啟動、長錄音、高負載或串流；FireRed 此 profile 不提供時間戳。

## 官方 Nano HF CPU FP32 部署，2026-10-15

`fun-asr-nano-2512-hf-cpu` 已加入正式 8767。使用官方 `FunAudioLLM/Fun-ASR-Nano-2512-hf`，模型與必要設定檔 SHA256、revision、獨立 venv 的推論套件版本固定於 `config/versions.json` 的 `nano_hf`。主權重約 1.66 GB；它與先前 Nano GGUF 的 F16 encoder／Q8 decoder 測試分開，沒有修改既有 ASR 套件或 VocaLinux 設定。

- 真實 `LoadModel` 載入 `FunAsrNanoForConditionalGeneration` 與 `FunAsrNanoProcessor`，所有參數 device=cpu、dtype=torch.float32，`trust_remote_code=False`。固定的本機權重及套件版本全部檢查通過；實際使用 Torch／torchaudio 2.10.0+cpu、Transformers 5.17.0。見 [原生模型證據](validation/nano-hf-model.json)與 [runtime 擴充 hash](validation/nano-hf-extension.json)。
- 8768 staging 與正式 8767 各驗證中文、英文、中英混合三段音訊，分別使用 zh、en、auto 及省略 language，共各 12 次。Auto 不傳語言提示，zh/en 交給官方 processor 建立對應提示。所有回應非空，中文轉繁體，text 與 segments 一致。見 [staging API](validation/nano-hf-api-8768.json)及 [正式 API](validation/nano-hf-api-8767.json)。
- 本次混合短樣本在四種語言設定均輸出「放進你的 training 裏面。」。這只證明這一段保留英文，不代表使用者其他英文詞或一般混合句都能正確辨識。
- `scripts/test_nano_hf.py` 檢查 CPU-only／未知模型拒絕、語言別名、繁體一致、純零值靜音、超過 60 秒拒絕及生成未結束拒絕。發布檢查能拒絕不同模型、設定／後端 hash、FP16 原生證據與錯誤權重 hash；prepare／publish 重跑通過。Python 編譯、既有 Whisper 發布檢查及 Git whitespace 檢查通過。
- 正式服務重啟後列出八個模型，開機預載設定仍為 SenseVoice。完成 SenseVoice → Whisper Turbo → Qwen 0.6B CPU → Nano HF 的 API 往返切換，每次僅有一個 LocalAI 後端常駐，最後保持 Nano 載入供使用者試用。見 [服務及切換證據](validation/nano-hf-switch.json)。SenseVoice 原生回歸仍為 CPU、917 個 float32 參數張量，設定、權重與 VAD hash 通過，見 [SenseVoice 回歸](validation/nano-hf-sensevoice-model.json)。
- 臨時 8768 已停止，正式服務 active／enabled，原 8766 健康回應正常。自訂 Nano gRPC 保留固定的認證、模型識別與父程序生命週期攔截器，僅監聽 loopback，沒有新增 HTTP 代理。

這是安裝與功能驗證，沒有執行完整同批錄音排名、使用者麥克風／VocaLinux 聽寫、OS 重新開機、日文音訊、長錄音、高負載或串流測試。此 profile 單段上限 60 秒，最多生成 256 token，未產生結束符會要求縮短錄音；沒有詞級時間戳或翻譯模式。官方記錄過的 attention dispatch 警告在本機亦出現，但上述推論均成功；未評估各注意力 kernel 的效能差異。

## Breeze 25／26 CPU 與 Sherpa SenseVoice，2026-10-15

正式 LocalAI 加入 `breeze-asr-25-cpu`、`breeze-asr-26-cpu` 與 `sensevoice-onnx-cpu`，模型清單共十一個。Breeze 使用官方 HF 權重在本機轉 CTranslate2 CPU INT8；Sherpa 使用 k2-fsa 的 SenseVoiceSmall FP32 ONNX 匯出。各 profile 的來源、必要檔案、工具與轉換後 hash 皆固定於 `config/versions.json`。沒有修改 VocaLinux 設定或原 8766 服務。

- Breeze 25 與 26 分別核對官方原始權重及獨立轉換產物，真實 LoadModel 均為 faster-whisper `WhisperModel`／CTranslate2 `Whisper`、device=cpu、compute_type=int8_float32。兩個模型的 model.bin SHA256 不同。見 [25 原生證據](validation/breeze-25-model.json)、[26 原生證據](validation/breeze-26-model.json)與 [runtime hash](validation/breeze-extension.json)。這是本機轉換路線，不宣稱與官方 patched Whisper 解碼逐位元等價。
- Breeze 25 在 staging 8768 與正式 8767 各測中文、英文與中英混合，使用 zh、en、auto 及省略 language，各 12 次；回應非空，繁體 text／segments 一致。見 [25 staging](validation/breeze-25-api-8768.json)、[25 正式](validation/breeze-25-api-8767.json)。
- Breeze 26 針對台語轉華語中文字，使用行政院教育部公開台語錄音的前 8 秒，分別測 zh、auto 及省略 language。兩個埠都回傳「妳是在煩惱什麼」「我想要教孩子臺語」「怎麼打字」等話題文字；這是非空功能檢查，沒有人工逐字評分或復現模型卡 benchmark。見 [26 staging](validation/breeze-26-api-8768.json)、[26 正式](validation/breeze-26-api-8767.json)。原始 ZIP／MP3 hash 見 `breeze_cpu.taigi_sample`。
- Sherpa 實際載入 `OfflineRecognizer`、provider=cpu、sherpa-onnx 1.13.8、ITN 開啟；ONNX 權重檢查為 917 個 FLOAT initializer，沒有量化運算。只使用 model.onnx，沒有載入 INT8 模型，也沒有轉送原 8766 HTTP。見 [Sherpa 原生證據](validation/sensevoice-onnx-cpu-model.json)及 [共用後端 hash](validation/sherpa-backend-extension.json)。
- Sherpa 的中文、英文及混合三段音訊，在兩個埠各測 zh、en、auto 與省略 language，共各 12 次，繁體 text／segments 一致。混合短樣本在 Auto／zh 仍把 training 辨成「圈子」，en 也未正確辨識整句。見 [Sherpa staging](validation/sensevoice-onnx-cpu-api-8768.json)、[Sherpa 正式](validation/sensevoice-onnx-cpu-api-8767.json)。此結果不支持把換引擎宣稱為英文準確度修正。
- 因 Sherpa 加入共用 CPU 後端，Qwen 0.6B／1.7B 及 FireRed 以相同新後端 hash 重新完成原生載入與 staging API 檢查；原先固定來源與精度不變。見 [共用後端回歸](validation/sherpa-shared-backend-regression.json)。SenseVoice PyTorch 原生回歸仍為 CPU、917 個 float32 參數張量，設定、權重與 VAD 檢查通過，見 [原始 SenseVoice 回歸](validation/sherpa-original-sensevoice-model.json)。
- 服務重啟後進行 Breeze 25 → Breeze 26 → Qwen 0.6B → Qwen 1.7B → FireRed → Sherpa SenseVoice → Nano HF → PyTorch SenseVoice 切換，每次僅有一個 LocalAI 後端常駐，最後回到原 SenseVoice。正式單元 active／enabled，開機預載設定不變，8768 臨時實例已停止，原 8766 健康正常。見 [切換與服務證據](validation/breeze-sherpa-switch.json)。
- Breeze 的 CPU-only、語言、繁體 text／segment／word、gRPC 奈秒時間單位、分模型發布證據與錯誤 hash 拒絕檢查通過。共用 CPU guard／語言／發布檢查、Python 編譯及 Git whitespace 檢查通過。

未測使用者麥克風、完整 VocaLinux 聽寫、OS 重新開機、長錄音、高負載、Sherpa 串流或 Sherpa Paraformer。短樣本及非空檢查不能代表整體準確度；Breeze CPU 本次多個請求需要數秒至十多秒，較長錄音可能超過 Local Voice 的 30 秒逾時。部分獨立測試同時運作，報告秒數不能當成公平速度排名。

## README 流程追蹤檢查，2026-10-15

README 的轉錄與擴充模型部署圖以 `diagrams/*.mmd` 為來源，由 `scripts/diagrams.py` 同步；`--check` 能拒絕過期副本。`scripts/test_diagrams.py` 已確認過期內容及缺少 marker 會失敗。兩張圖以 Mermaid CLI 11.12.0 與本機 Chrome 渲染成 SVG／PNG，檢查過文字、分支與錯誤路徑；衍生圖面留在 `.localai/reports/`。`AGENTS.md` 將流程圖、功能對照與驗證同步列為硬性完成條件。

Local Voice 的錄音、WAV、語言映射、文字清理、可選固定替換／語音命令／外部腳本及回填路徑，依已安裝原始碼直接查核，檔案 hash 與非敏感設定快照見 [voice-flow-source.json](validation/voice-flow-source.json)。圖沒有把可選功能當成已啟用；磁碟設定快照不保證執行中程式的記憶體設定相同。沒有實際使用者焦點程式的端到端回填測試。
