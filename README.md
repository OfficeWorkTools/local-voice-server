# LocalAI SenseVoice FP32

在 Linux x86_64 上安裝可管理模型的官方 LocalAI Web UI，以及 SenseVoiceSmall 的原生 FunASR CPU FP32 語音 API。模型常駐，啟動時用真實語音暖機，預設只監聽 `127.0.0.1:8767`。適合人與 AI agent 按相同步驟在另一台電腦部署。

**這個原生後端輸出簡體，沒有 OpenCC 或 LLM 改寫；中英混用測試仍有誤辨。** 此 repo 提供可重現部署，不保證辨識品質更好。

## 前提

- Linux x86_64、glibc；實際驗證環境為 Ubuntu 26.04.1 LTS。其他架構、macOS、Windows 未測。
- Python 3.11 以上、`curl`、`ffmpeg`、可用的 `systemctl --user`。後端有自己的 Python 3.12 與依賴，不會安裝到系統 Python。Docker 和 uv 不是這些腳本的必要依賴。
- 至少 6 GiB 可用磁碟、4 GiB 可用 RAM，另留空間給其他應用程式。腳本會檢查；模型常駐約 1.5 GiB，安裝及 FP32 驗證的尖峰較高。
- 首次安裝需要 HTTPS 網路，能存取 GitHub、quay.io、Hugging Face 和 ModelScope。下載量約數 GiB。
- checkout 路徑及 Python 執行檔路徑不含空白、引號、`$`、`%` 或反斜線。安裝後保持 checkout 原位置。

Ubuntu 可先安裝系統工具：

```bash
sudo apt-get install python3 curl ffmpeg git libgomp1 libsndfile1
systemctl --user show-environment
```

`apt` 步驟是新機器的前提範例，本次機器已具備工具，未重新執行系統套件安裝。

## 一次安裝與啟動

以下 clone 只寫入選定目錄；`install` 下載固定版本、建立本 repo 的 user systemd 單元、enable 並啟動。它不修改 VocaLinux。

```bash
git clone https://github.com/OfficeWorkTools/localai-sensevoice-fp32.git
cd localai-sensevoice-fp32
python3 deploy.py install
```

已有程式占用 8767 時，使用另一個空埠：

```bash
python3 deploy.py install --port 8768
```

重跑安裝會核對已下載檔案並重用匹配的內容；會停止、重新設定此 checkout 自己的單元，再啟動。它拒絕覆蓋另一個 checkout 的同名單元。更換埠也使用 `install --port`；其他命令讀取已儲存埠號。單一使用者僅管理一份本 repo 的單元。

下載使用 curl 重試、暫存檔及 SHA256；模型檔全部固定到同一 HF revision。CPU 後端固定 OCI digest，而非追蹤 `latest`。安裝後必須通過真正的 CPU FP32 載入檢查、中文暖機、Web UI／模型清單與 multipart 自測。

登出後也需要持續運作時，先查 `loginctl show-user "$USER" -p Linger`。若為 `no`，由本機使用者依系統政策啟用 `loginctl enable-linger "$USER"`，再驗證；本次環境原本已是 `yes`，未測從 `no` 啟用或重新開機。

## GUI 與 VocaLinux

預設 GUI：[已安裝模型管理](http://127.0.0.1:8767/app/models?view=installed&model=sensevoice-fp32)。在 Installed 選擇 `sensevoice-fp32`，可 Load／Stop、Actions → Edit configuration，以及開啟 Transcribe。用 8768 部署時，將 URL 的埠改為 8768。

| VocaLinux 欄位 | 預設值 |
| --- | --- |
| Server URL | `http://127.0.0.1:8767` |
| API Endpoint | `OpenAI/FunASR (/v1/audio/transcriptions)` |
| 精確 endpoint | `/v1/audio/transcriptions` |
| Model | `sensevoice-fp32` |
| API Key | 留空 |
| Language | `auto` 或 `zh` |

完整 API URL 為 `http://127.0.0.1:8767/v1/audio/transcriptions`。這個原生 FunASR 後端接受 `zh`，本 repo 不加 `zh-tw` 映射；使用 `auto` 或 `zh` 做對照。空字串／省略 language 都會交給後端預設。

```bash
curl -fsS -F file=@.localai/samples/chinese.wav \
  -F model=sensevoice-fp32 -F language=zh \
  http://127.0.0.1:8767/v1/audio/transcriptions
```

安裝與測試音訊為 16 kHz、mono、16-bit PCM WAV，符合 VocaLinux 上傳格式。API 回應包含 JSON `text`。LocalAI 可透過 ffmpeg 處理其他格式，但此 repo 只驗證上述格式與短句。

## 固定版本與 FP32

所有 URL、revision 與 checksum 的唯一設定在 [config/versions.json](config/versions.json)：

- LocalAI v4.11.0 官方 Linux amd64 二進位及官方 checksum。
- 官方 CPU FunASR OCI digest、官方 backend.py hash；來源 gallery 為 v4.11.0。
- `FunAudioLLM/SenseVoiceSmall` 官方 revision，以及 `model.pt`、配置、CMVN、tokenizer 與上游 README 的 SHA256。
- 原生 FSMN VAD 的權重、配置與 CMVN hash。原生後端仍向 ModelScope 解析預設版本，檔案變更時驗證會失敗，不會默默接受新版本。
- 兩段公開測試音訊的來源與原始 SHA256。混用音訊由固定公開列取得 URL，內容仍必須符合 hash，再以 ffmpeg 轉成 PCM；來源若變更，安裝會失敗，不會默默接受新音訊。

```bash
python3 deploy.py verify-fp32
python3 deploy.py test
python3 deploy.py restart
python3 deploy.py test
```

`verify-fp32` 呼叫已安裝官方原生後端的 `BackendServicer.LoadModel`，檢查真正模型類別、所有 917 個參數為 `torch.float32`、裝置為 CPU，並核對權重 SHA256。不是只查看 `sensevoice-fp32` 名稱或 YAML 的 `f16: false`。此命令暫時另載入一份模型，RAM 不足時先 `stop` 本 repo 的服務，完成後再 `start`。

報告寫到 `.localai/reports/fp32.json` 與 `api.json`，不提交 Git。API 自測使用中文及中英樣本，各比較 `zh`、`auto`、空字串與省略；檢查成功、非空文字與無原始標籤。它記錄是否保留 `training`，不把已知誤辨當作功能測試失敗，也不宣稱量測了一般字錯率。

## 狀態、日誌與停止

查詢命令可隨時執行；start／restart／stop 只控制本 repo 的單元，restart／stop 會中斷這個服務正在進行的轉錄。

```bash
python3 deploy.py status
python3 deploy.py logs
python3 deploy.py stop
python3 deploy.py start
```

需要停止並取消自動啟動：

```bash
python3 deploy.py stop
systemctl --user disable localai-sensevoice-fp32.service
```

恢復自動啟動用 `systemctl --user enable --now localai-sensevoice-fp32.service`。模型與快取保留，不需重新下載。

所有下載與機器專屬狀態在 `.localai/`；user systemd 單元在使用者的 XDG config 下。安裝腳本計算實際 checkout 路徑再生成單元，repo 內沒有固定使用者 home 路徑。改變 checkout 位置時先從原位置停止及 disable，再搬移；新位置的安裝遇到舊單元 ownership 檢查時，確認舊服務已停，再移除那份自己生成的單元並重新安裝。

## 修復與升級

### 後端找不到 SenseVoiceSmall-official

原生後端以自己的目錄作為 cwd，且將相對 model 值原樣交給 FunASR。因此 `.localai/backends/cpu-funasr/SenseVoiceSmall-official` 必須指向 `../../models/SenseVoiceSmall-official`。重裝 backend 可能移除這個連結。

```bash
python3 deploy.py stop
python3 deploy.py repair-link
python3 deploy.py start
python3 deploy.py test
```

程式只替換 symlink，遇到同名實體目錄會停止，避免刪除資料。

### 無法下載或 checksum 不符

先確認 HTTPS 連線，然後重跑 `install`。有效檔案會被重用；錯誤內容留在 `.part`，不會覆蓋既有匹配檔案。OCI 安裝最多重試三次。backend digest／程式 hash 不符時停止服務並檢查來源；不要為了成功而刪掉校驗條件。

### Explore 目錄為空

這是已知 v4.11.0 問題的回避措施：預設遠端 GGUF gallery 的預估預載曾觸發異常超大配置並使程序退出。本 repo 使用 `--galleries=[]`，Installed、匯入、模型設定與原生 ASR 仍可使用。不要在未重測之前恢復預設 gallery。

### 埠被占用或 user systemd 不可用

不要停止無關服務。使用另一個 `install --port`；確認 `systemctl --user show-environment` 可用，再安裝。腳本對另一個 checkout 的同名單元會拒絕接管。

升級時先停止服務，保留 `.localai/models` 與 cache。此 repo 只測固定版本；要升級先在分支更新 `config/versions.json`、來源證據及必要腳本，再於空埠做乾淨安裝、FP32 載入、重啟與 API 比較。保留舊 checkout／單元／runtime 供回復。不可把模型改成 INT8、FP16 或其他模型，或把綁定位址改成公開介面，來繞過驗收。

## 給 AI agent 的驗收流程

1. 確認前提與可用 RAM／磁碟；查看埠與 user systemd，保留使用者既有 ASR、VocaLinux 設定和憑證。
2. 新 checkout 選空埠，執行 `python3 deploy.py install --port <空埠>`。完成條件為安裝命令成功，FP32 報告全部 CPU float32，systemd running 且模型已暖機。
3. 執行 `restart` 與 `test`。完成條件為 GUI 可達、模型清單含 `sensevoice-fp32`，四種 language 的兩段真實音訊均有 JSON text；如實記錄英文誤辨與簡體輸出。
4. 交付 GUI、Server URL、精確 endpoint、model、key 留空與 language。測試用臨時實例要 stop 並 disable；正式部署保持運作。不要用舊環境結果代替這次 checkout 的報告。

## 已知限制與延遲參考

原生 FunASR 後端額外啟用 FSMN VAD，預設未開 ITN，且沒有原生 OpenCC 繁體轉換配置。`rich_transcription_postprocess` 清除原始標籤，可能保留情緒／事件符號；兩段測試沒有此類符號。首次模型／VAD 下載及冷推論較慢，systemd 在進入 running 前以語音暖機。

VAD cache 即使存在，啟動仍可能檢查 ModelScope；完全斷網啟動未驗證。LocalAI 同時僅允許一個自己的 backend 常駐，原本其他 ASR 服務不在此限制內。VocaLinux 請求逾時 30 秒，長句或高負載仍可能逾時。

先前 Ryzen 9 7945HX 部署：4.20 秒中文完整 HTTP 約 0.30 秒，中英 1.59 秒約 0.22 秒，冷推論約 11.5 秒。中文回傳「甚至出现交易几乎停滞的情况」；中英把 `training` 誤辨為「圈里／圈利」。原 ONNX FP32 同樣本約 0.13／0.10 秒。這些是兩個樣本的實測參考，不保證其他電腦速度或一般準確率。

此 repo 的乾淨安裝與重啟測試範圍及結果記錄於 [VALIDATION.md](VALIDATION.md)。上游來源與第三方授權範圍見 [THIRD_PARTY.md](THIRD_PARTY.md)。
