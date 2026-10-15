# LocalAI 與 VocaLinux 設定及切換規則

Local Voice（本機安裝的 VocaLinux）使用 Turbo 時，將 Remote Server 的 Model 設為 `whisper-large-v3-turbo`；完整版本使用 `whisper-large-v3`。LocalAI 會依請求載入對應模型；切換模型不需要更換 Server URL 或 API Endpoint。此文件記錄本機設定，安裝工具與固定來源見 [README](README.md)。

手動步驟會修改 VocaLinux 設定；API 測試會切換 LocalAI 常駐模型。以下規則不會自動修改 VocaLinux。

## VocaLinux 連線設定

1. 使用者開啟 VocaLinux 的 Settings。
2. 使用者選 Speech Model。
3. 使用者展開該頁的 Advanced。
4. 使用者確認 Speech Engine 使用 Remote Server。
5. 使用者在 Remote Server 填入下列欄位。

| 欄位 | 使用 Turbo 的值 |
| --- | --- |
| Server URL | `http://127.0.0.1:8767` |
| API Endpoint | `OpenAI/FunASR (/v1/audio/transcriptions)` |
| API Key | 留空 |
| Model | `whisper-large-v3-turbo` |

`OpenAI/FunASR` 是 VocaLinux 的 API 格式選項名稱；實際辨識模型由 Model 欄位決定。名稱區分大小寫，請直接貼上表中的小寫名稱。

## 模型與語言選擇

| 用途 | Model |
| --- | --- |
| Whisper large-v3-turbo，速度優先試用，NVIDIA GPU FP32 | `whisper-large-v3-turbo` |
| 完整 Whisper large-v3，品質優先對照，NVIDIA GPU FP32 | `whisper-large-v3` |
| SenseVoiceSmall，CPU FP32 | `sensevoice-fp32` |
| 原有 Paraformer 中文模型，CPU float32 | `paraformer-zh` |

兩個 Whisper 名稱對應不同的實際權重，皆使用同一個 NVIDIA GPU 後端與 FP32 推論。Model 欄位填上表中的完整 API 名稱；不要填 `turbo`、`whisper-1` 或權重目錄名稱。這裡沒有自動融合或依句子自動選模型；發布檔案儲存精度與 GPU 推論精度須分開看。

在 Speech Engine 的 Language 選擇下列模式。先停止當次聽寫，再切換模型或語言，避免影響正在處理的錄音。

| 說話方式 | Language 選單 | API 語言 |
| --- | --- | --- |
| 中文為主，包含英文單字或術語 | Chinese | `zh` |
| 整句或整段英文 | English (US) | `en` |
| 不同錄音可能整段中文或整段英文 | Auto-detect | 省略 language，自動辨識 |

以中文為主的混合句可先用 Chinese。Auto 不保證正確辨識同一句裡的所有英文。選 Chinese 也不保證英文原詞一定保留，模型仍可能漏字或辨成中文字。

## LocalAI 管理頁與載入規則

1. 使用者開啟 [Installed 模型管理](http://127.0.0.1:8767/app/models?view=installed)。
2. 使用者選擇 `whisper-large-v3-turbo` 或 `whisper-large-v3`。
3. 使用者按 Load，或直接從 VocaLinux 送出相同 Model 的轉錄請求。

LocalAI 限制最多一個後端常駐。完整 Whisper、Turbo 與 SenseVoice 之間會依請求互相卸載及載入；模型下載檔保留。切換後第一次請求需要載入時間，接著使用同一模型才是暖機後的速度。

VocaLinux 的 Model 欄位必須和想用的模型一致。只在管理頁 Load Whisper，卻讓 VocaLinux 繼續送出 `sensevoice-fp32`，下一次聽寫仍會要求 SenseVoice。管理頁側邊的 Change language 是顯示語言，語音辨識語言使用上述 VocaLinux Language 欄位。

目前開機預載仍是 SenseVoice。Whisper 已安裝後，重新開機不需要重新下載；當 VocaLinux 的 Model 設為兩個 Whisper 名稱之一，首次請求會載入該模型。桌面的啟動及停止快捷方式控制整個 LocalAI 服務。

## 完整版本與 Turbo 對照測試

中文夾英文的比較，先固定 Language 為 Chinese，只改 Model 欄位。速度優先先試 `whisper-large-v3-turbo`，品質對照改回 `whisper-large-v3`。兩者都可能把短英文詞辨成中文，名稱和熱詞設定不能保證修正。

每次切換前先停止聽寫，再把整個模型名稱貼入 Model。第一段用來載入及暖機，後續段落才比較回應速度；輪流切換每一段會反覆觸發載入，不能代表正常常駐速度。要精確比較準確度，需用同一段已錄好的音訊，而非每次重新說一句。

保持 Speech Engine 為 Remote Server。內建的 Whisper／whisper.cpp 選項使用另一條執行路徑，不會由上述 Model 欄位選取 LocalAI。管理頁只有 Load Turbo，而 VocaLinux Model 仍填完整版本時，聽寫會再載回完整版本。

## 回復與確認

要回復原本用法，使用者將 VocaLinux Model 改回 `sensevoice-fp32`，再依說話方式選 Chinese 或 Auto-detect。其他連線欄位保持表中的值。

在本 repo 目錄可用以下 API 呼叫確認 Turbo。此呼叫會載入 Turbo 並卸載目前的模型。

```bash
curl -fsS -F file=@.localai/samples/chinese.wav \
  -F model=whisper-large-v3-turbo -F language=zh \
  http://127.0.0.1:8767/v1/audio/transcriptions
```

回應應包含非空的 JSON `text`，中文樣本的「出現」應為繁體。真實 GPU 推論、language 傳遞、繁體輸出及模型往返切換的證據見 [VALIDATION](VALIDATION.md)。VocaLinux 選單路徑依已安裝版本來源確認，沒有代操作使用者設定或測試使用者麥克風。
