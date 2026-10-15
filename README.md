# LocalAI ASR：繁體輸出與模型切換

## 給人看的：用途與能力

### 它是做什麼的

這是 Linux 本機語音辨識部署工具，提供 LocalAI 原生 Web UI 與 OpenAI 相容的音訊上傳 API。VocaLinux 或其他支援 `/v1/audio/transcriptions` 的應用程式可以使用它；預設只監聽 `127.0.0.1:8767`，無需 API key。

預設模型是官方 SenseVoiceSmall CPU FP32。辨識完成後，原生 FunASR 後端用 OpenCC `s2t` 將文字轉為繁體，再交給 LocalAI 回應。整段 `text` 與各個 `segments[].text` 使用同一個結果；英文、數字及格式保留，沒有 LLM 潤飾或翻譯。繁體轉換不會修正 ASR 聽錯的詞。

### 可以切換的模型

| Profile／API Model | 官方來源 | Runtime | 此 profile 精度 |
| --- | --- | --- | --- |
| `sensevoice-fp32`，預設 | `FunAudioLLM/SenseVoiceSmall` | 原生 FunASR／PyTorch CPU | FP32，實際載入 917 個 float32 參數張量 |
| `paraformer-zh` | `funasr/paraformer-zh` | 原生 FunASR／PyTorch CPU | 此 profile 為 float32，實測 956 個參數張量 |
| `whisper-large-v3` | `Systran/faster-whisper-large-v3` | 原生 faster-whisper／CTranslate2 NVIDIA GPU | GPU FP32 推論，獨立固定後端與小補丁 |
| `whisper-large-v3-turbo` | `mobiuslabsgmbh/faster-whisper-large-v3-turbo` | 與完整 Whisper 共用原生 GPU 後端 | GPU FP32 推論，獨立權重與模型設定 |

上述模型使用固定來源 revision 與檔案 hash。Whisper 使用獨立 NVIDIA GPU 後端，透過 GUI 或 API Model 切換；既有兩個 FunASR profile 也支援下方的 CLI 預載切換。LocalAI 最多保留一個自己的模型常駐，下載檔保留，供再次切換。不是只改 model 名稱；詳細證據在 [VALIDATION.md](VALIDATION.md)。

其他 profile 的精度由它自己的配置決定，不能把 SenseVoice 的 FP32 保證套到所有模型。目前驗證範圍為上述兩個原生 FunASR profile 與兩個 Whisper GPU profiles，沒有宣稱支援所有 ASR runtime。

### GUI 與應用程式

預設 GUI：[LocalAI Installed 模型管理](http://127.0.0.1:8767/app/models?view=installed)。在 Installed 選模型，可 Load／Stop、Actions → Edit configuration、開啟 Transcribe。首次使用第二個 profile，先執行下面的 `switch` 下載及驗證；兩個模型都安裝後，GUI 可 Load 另一個模型，LocalAI 會卸載前一個。

VocaLinux 的精確模型名稱、語言選擇與管理頁載入規則，見 [設定與切換規則](VocaLinux-設定與切換規則.md)。加入 Whisper 不會更改開機預載或 VocaLinux 設定。

CLI 切換並保存重啟後的 FunASR 預設模型：

```bash
python3 deploy.py switch paraformer-zh
python3 deploy.py switch sensevoice-fp32
```

GUI 的 Load 與 API 的 `model` 決定當次實際使用的模型；CLI `switch` 同時保存啟動時的預載選擇。GUI 不會改寫部署工具的選擇檔，重啟後仍使用 CLI 保存的 profile。

| VocaLinux 欄位 | 預設值 |
| --- | --- |
| Server URL | `http://127.0.0.1:8767` |
| API Endpoint | `OpenAI/FunASR (/v1/audio/transcriptions)` |
| 精確 endpoint | `/v1/audio/transcriptions` |
| Model | `sensevoice-fp32`、`paraformer-zh`、`whisper-large-v3` 或 `whisper-large-v3-turbo`，依實際需求選擇 |
| API Key | 留空 |
| Language | 中文及中英夾雜先用 `zh`，純英文用 `en`，整段自動辨識用 `auto` |

VocaLinux 設定由使用者修改。API request 的 `model` 必須選真正要用的 profile；若仍送 SenseVoice，即使先前 CLI 選了 Paraformer，LocalAI 仍會載入 SenseVoice 來處理該請求。`zh-tw` 沒有額外映射，請先用 `zh` 或 `auto`。

### 能力的界線

上述模型的 JSON 音訊轉錄已驗證繁體輸出，SenseVoice FP32 已驗證權重與載入參數；不保證中英混用更準。測試中的 `training` 仍有誤辨，字詞轉繁體不會改善它。

兩個 FunASR profile 的原生後端額外使用 FSMN VAD，沒有開啟 ITN，也沒有新增標點模型。原生 `rich_transcription_postprocess` 可能保留情緒／事件符號。OpenCC `s2t` 做字詞及異體轉換，並非 `s2twp` 的臺灣用詞替換；含糊字形的字典選擇仍可能不合使用者偏好。

Web UI／API 都由同一個 LocalAI HTTP 埠提供，沒有新增代理或第二個 HTTP 埠。LocalAI 自動啟動的原生 FunASR gRPC 使用 loopback 動態埠，不對外公開。

## 給 AI agent 看的：安裝、部署和應用

### 範圍與前提

使用此 repo 的固定版本、profile 與可校驗的後端擴充。維持 SenseVoice 預設 CPU FP32、loopback 與使用者既有服務；不得改用量化版來通過 SenseVoice 驗收。其他 profile 依自身 precision 驗證。

- Linux x86_64／glibc。已測 Ubuntu 26.04.1 LTS，其他架構與系統未測。
- Python 3.11 以上、curl、ffmpeg、bash、可用的 `systemctl --user`。官方後端封裝自己的 Python 3.12，工具不修改系統 Python；不需要 Docker 或 uv。
- 至少 6 GiB 可用磁碟、4 GiB 可用 RAM；多個模型的下載檔與載入尖峰需要更多空間。切換時先卸載本 repo 的服務，驗證後才啟動新模型。
- 首次安裝需要 GitHub、quay.io、Hugging Face、PyPI 與 ModelScope 的 HTTPS 網路。VAD cache 即使存在，仍可能檢查 ModelScope，完全斷網啟動未測。
- checkout 與 Python 路徑不含空白、引號、`$`、`%`、反斜線；安裝後保持 checkout 位置。

Ubuntu 的前提範例：

```bash
sudo apt-get install python3 curl ffmpeg git libgomp1 libsndfile1
systemctl --user show-environment
```

系統套件在測試機器原已存在，apt 範例沒有當作乾淨 OS 重建證據。登出後持續運作需要 `Linger=yes`；先查 `loginctl show-user "$USER" -p Linger`，必要時由使用者依系統政策啟用。本次沒有測從 `no` 啟用或重新開機。

### 固定來源與繁體擴充

[config/versions.json](config/versions.json) 是版本／權重／hash 的來源：LocalAI v4.11.0 binary、官方 CPU FunASR OCI digest、原始 backend.py SHA256、各個模型的 HF revision 與完整必要檔案、VAD 檔案，以及 OpenCC 0.1.7 wheel。

v4.11.0 的音訊 endpoint 沒有已驗證的通用 OpenCC 配置；chat filter 不適用。`prepare_conversion()` 檢查原始 backend.py hash，保存 `backend.upstream.py`，以兩個唯一 anchor 加入 conversion import，並在原生 transcript 組裝前呼叫 `convert_text()`。補丁只改 import 與 segment 後處理，不修改權重或推論精度。

下載的固定 wheel 解出 OpenCC 套件，後端以 symlink 存取；原創的 [scripts/transcription_conversion.py](scripts/transcription_conversion.py) 使用 `s2t`。原始 hash、補丁後 hash、模組與 wheel hash 記錄在 `.localai/reports/backend-extension.json`。重跑只接受原始或確定的已套用內容，未知改動會停止，不會覆蓋人工修改。升級後端必須重新檢查 anchor、hash、實際 dtype 與 HTTP 輸出。

### 安裝、更新與啟動

先確認空埠、資源與 user systemd。不要停止無關服務或操作 VocaLinux。

```bash
git clone https://github.com/OfficeWorkTools/localai-sensevoice-fp32.git
cd localai-sensevoice-fp32
python3 deploy.py install --model sensevoice-fp32
```

已有程式使用 8767 時，先用空埠驗證：

```bash
python3 deploy.py install --port 8768 --model sensevoice-fp32
```

工具計算 checkout 根目錄，所有 runtime 在 `.localai/`，生成的 user systemd 單元為 `localai-sensevoice-fp32.service`。下載支援重試、暫存檔及 hash；模型、後端二進位、cache、音訊、log 不進 Git。

安裝會初始化官方可攜 Python、準備模型 symlink 與 OpenCC 擴充、驗證轉換和實際模型，啟動並以中文音訊暖機，再跑真實 API 自測。只有 warmup 成功後 systemd 才進入 running。`--galleries=[]` 避開 v4.11.0 預設 GGUF gallery 預估預載的崩潰；Explore 空白，Installed、匯入及設定仍可用。

更新已安裝的同一 checkout：

```bash
git pull --ff-only
python3 deploy.py install
python3 deploy.py restart
python3 deploy.py test
```

重跑保留原選擇的 profile 與埠；需要恢復 SenseVoice 時明確指定 `--model sensevoice-fp32`。工具只控制自己生成、且屬於此 checkout 的單元，拒絕接管其他 checkout。搬移 checkout 前先 stop／disable，確認舊單元停止後移除那份自己生成的單元，再在新位置安裝。

### 真正切換模型

```bash
python3 deploy.py switch paraformer-zh
python3 deploy.py verify-model
python3 deploy.py test
python3 deploy.py switch sensevoice-fp32
python3 deploy.py verify-fp32
python3 deploy.py test
```

`switch` 會卸載目前模型，下載並校驗所選官方 profile 的實際檔案，更新模型 YAML、symlink、保存的選擇及 systemd 預載，再驗證、暖機、測試。已下載且 hash 匹配的檔案會重用，不刪除原權重。預設的 FP32 保證專指 SenseVoice；目前 Paraformer profile 的驗證資料另記錄它的 class、956 個 float32 參數張量與不同權重 SHA256。

兩個已驗證 profile 共用固定原生 FunASR CPU backend，因此不需要新增第二個 runtime。其他 backend 必須有自己的固定依賴、下載校驗與實測。Whisper 共用後端與完整模型的來源在 `config/versions.json` 的 `whisper` 區段，Turbo 的獨立權重來源在 `whisper_turbo` 區段，由 `add_whisper.py` 管理，不在 `deploy.py switch` 的 FunASR profile 選單內；不能用 FunASR 補丁代替 Whisper 驗證。

### 加入完整 Whisper large-v3 GPU 模型

這是選用安裝，先完成既有 LocalAI 安裝，並使用有 NVIDIA GPU 的 Linux x86_64。本機驗證卡為 RTX 4060 Ti 16GB；SenseVoice 預設及 VocaLinux 設定由原選擇保留。

```bash
python3 add_whisper.py prepare
LD_LIBRARY_PATH="$PWD/.localai/backends/cuda12-faster-whisper/lib" \
  .localai/backends/cuda12-faster-whisper/venv/bin/python scripts/verify_model.py whisper-large-v3
```

prepare 下載固定 OCI 後端及完整 large-v3 權重，核對 hash，加入 GPU FP32、language 傳遞與 OpenCC s2t 的小補丁。模型 YAML 先放在 `.localai/whisper-staging/models`，正式清單尚未發布。已知後端及模型會重用；未知檔案改動會停止。

在另一個終端機啟動獨立測試埠，先確認 8768 沒有其他服務使用：

```bash
.localai/bin/local-ai run --address 127.0.0.1:8768 \
  --models-path "$PWD/.localai/whisper-staging/models" \
  --backends-path "$PWD/.localai/backends" \
  --data-path "$PWD/.localai/whisper-staging/data" \
  --galleries=[] --threads 8 --load-to-memory whisper-large-v3 --max-active-backends 1
```

等測試服務 ready 後，在原終端機執行 API 測試：

```bash
python3 scripts/check_whisper_api.py --port 8768
```

在測試服務的終端機按 Ctrl+C 停止該實例，再發布已通過的設定：

```bash
python3 add_whisper.py publish
python3 deploy.py restart
python3 scripts/check_whisper_api.py --port 8767
```

publish 檢查原生 CUDA FP32 驗證與獨立埠 API 證據，再把 `whisper-large-v3` 加入正式模型目錄。API 測試的英文錄音由固定 Whisper 測試檔下載並轉成 PCM16 WAV。測試會載入 Whisper；要回復原本使用方式，依 [VocaLinux 設定與切換規則](VocaLinux-設定與切換規則.md) 選回 SenseVoice。具體已驗證範圍與未測項目見 [VALIDATION](VALIDATION.md)。

### 加入 Whisper large-v3-turbo

Turbo 共用上述固定 NVIDIA 後端、FP32 推論與 OpenCC 小補丁，另有固定 revision、檔案 hash、權重目錄與 API Model 名稱。已安裝完整版本時會重用後端，預載選擇與 VocaLinux 設定保持原值。

```bash
python3 add_whisper.py prepare --model whisper-large-v3-turbo
LD_LIBRARY_PATH="$PWD/.localai/backends/cuda12-faster-whisper/lib" \
  .localai/backends/cuda12-faster-whisper/venv/bin/python scripts/verify_model.py whisper-large-v3-turbo
```

沿用上方獨立 8768 埠的 LocalAI 啟動指令，把 `--load-to-memory` 改為 `whisper-large-v3-turbo`，其餘路徑相同。ready 後驗證 Turbo：

```bash
python3 scripts/check_whisper_api.py --port 8768 --model whisper-large-v3-turbo
```

停止該臨時測試實例，再發布與重啟正式服務：

```bash
python3 add_whisper.py publish --model whisper-large-v3-turbo
python3 deploy.py restart
python3 scripts/check_whisper_api.py --port 8767 --model whisper-large-v3-turbo
```

每個 Whisper profile 使用各自的原生載入及 API 證據，發布時檢查模型 ID、權重 hash、設定 hash 與後端補丁 hash，防止混用完整版本與 Turbo 的測試結果。`add_whisper.py` 與 `check_whisper_api.py` 省略 `--model` 時仍選完整版本。小型發布隔離檢查為 `python3 scripts/test_whisper_profiles.py`。

Local Voice／VocaLinux 的 Turbo Model 精確填 `whisper-large-v3-turbo`；完整版本填 `whisper-large-v3`。Server URL 與 endpoint 相同，詳細語言及暖機比較規則見 [設定與切換規則](VocaLinux-設定與切換規則.md)。

### API 與自測

```bash
curl -fsS -F file=@.localai/samples/chinese.wav \
  -F model=sensevoice-fp32 -F language=zh \
  http://127.0.0.1:8767/v1/audio/transcriptions
```

改用 Paraformer 時替換 `model=paraformer-zh`；部署其他埠時同步修改 URL。輸入測試格式為 16 kHz mono 16-bit PCM WAV；回應是 JSON `text`。本次只驗證 JSON 短句，串流／字幕格式與其他音訊格式未測。

```bash
python3 deploy.py verify-fp32
python3 deploy.py verify-model
python3 deploy.py test
```

`verify-fp32` 僅在選定 SenseVoice 時執行。`verify-model` 用所選 profile，透過官方原生 `LoadModel` 檢查實際模型類別、權重 SHA256、CPU、profile precision，SenseVoice 額外檢查 917 個 float32 參數張量；也校驗 VAD 檔案。它暫時另外載入一份模型，RAM 不足時先 stop，驗證後再 start。

測試包括：OpenCC 簡轉繁、空字串、英文／數字／換行保留；兩段真實音訊各使用 `zh`、`auto`、空字串與省略；GUI HTTP、模型清單、繁體字及 text／segments 一致。`training` 誤辨會如實記錄，不當成已修正。報告在 `.localai/reports/`，公開的實測範圍見 [VALIDATION.md](VALIDATION.md)。

### 狀態、停止與回復

```bash
python3 deploy.py status
python3 deploy.py logs
python3 deploy.py stop
python3 deploy.py start
```

查詢可隨時執行。start、stop、restart、switch、重跑 install 只作用於此 checkout 的單元，會中斷其進行中的轉錄。取消自動啟動：

```bash
python3 deploy.py stop
systemctl --user disable localai-sensevoice-fp32.service
```

恢復預設服務使用 `python3 deploy.py switch sensevoice-fp32`。模型檔保留，可回復選擇；升級失敗時保留舊 checkout／runtime／單元，在確認它自己的服務停止後回到已驗證版本重新安裝，不覆寫其他 ASR。

### 排錯與驗收

- model 路徑錯誤：原生後端的 cwd 是 backend 目錄，同名 symlink 指向 `../../models/<profile-directory>`。執行 stop → `repair-link` → start → test；這只替換 symlink，遇到同名實體目錄會停止。重裝後端後重跑 install，才能一併重建模型與 OpenCC 擴充。
- checksum／未知補丁錯誤：檢查來源與版本，不刪掉校驗來通過。原始或已套用的固定補丁可重跑，其他改動須人工核對並保留。
- 下載／VAD 失敗：檢查 HTTPS 網路後重跑 install；匹配檔會重用。ModelScope 預設 VAD 變更時，固定 hash 會拒絕接受新內容。
- 埠占用／unit ownership 錯誤：選另一個空埠或確認舊 checkout 已 stop／disable，再處理它自己的單元；不要停止無關服務。
- 想要所有模型都繁體：目前擴充範圍為上述原生 FunASR 與固定 Whisper 後端，任意手動匯入其他 backend 不在保證範圍內。

AI agent 的完成條件是：新或更新安裝成功、SenseVoice 實際 CPU FP32、繁體中文 HTTP、第二 profile 的不同 class／權重與 API、切回 SenseVoice、重啟暖機、GUI 可達。記錄真實 ASR 結果、延遲與未測項目，最後交付 URL、Model 與切換指令。臨時驗證實例需 stop／disable，正式部署保持運作。上游與授權範圍見 [THIRD_PARTY.md](THIRD_PARTY.md)。
