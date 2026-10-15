# 上游來源與授權

此 repo 的 MIT 授權僅涵蓋本 repo 原創的部署程式、設定及文件。它不重新授權 LocalAI、FunASR、PyTorch、模型權重或測試音訊。這些檔案在安裝時取得，沒有隨 Git repo 散布，使用時須遵守各上游條款。

- [LocalAI v4.11.0](https://github.com/mudler/LocalAI/tree/v4.11.0)：主程式與原生 CPU FunASR 後端來源。
- [FunASR](https://github.com/modelscope/FunASR)：辨識及 FSMN VAD。
- [FunAudioLLM/SenseVoiceSmall](https://huggingface.co/FunAudioLLM/SenseVoiceSmall)：官方權重；固定版本見 `config/versions.json`，下載的上游 README 保留於模型目錄。
- [funasr/paraformer-zh](https://huggingface.co/funasr/paraformer-zh)：官方第二個模型 profile，同樣下載並校驗固定 revision。
- [opencc-python-reimplemented](https://pypi.org/project/opencc-python-reimplemented/0.1.7/)：OpenCC s2t 字詞轉換，固定 wheel 及 SHA256，套件不隨此 repo 散布。
- [PyTorch](https://pytorch.org/)：後端套件內的 CPU 推論引擎。
- [Qwen3-ASR](https://github.com/QwenLM/Qwen3-ASR)：官方中文測試音訊。
- [ky552/ML2021_ASR_ST](https://huggingface.co/datasets/ky552/ML2021_ASR_ST)：公開 test 第 1279 列中英混用音訊與參考文字。依據資料集自己的授權使用。

- [Whisper](https://github.com/openai/whisper) 與 [Systran/faster-whisper-large-v3](https://huggingface.co/Systran/faster-whisper-large-v3)：完整 large-v3 及 CTranslate2 發布權重；固定 revision／檔案 hash 見 `config/versions.json`。
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) 與 [CTranslate2](https://github.com/OpenNMT/CTranslate2)：Whisper GPU 推論。LocalAI 原生 NVIDIA 後端以固定 OCI digest 下載，語言、推論精度及 OpenCC 補丁由本 repo 原創程式套用。
- [Whisper JFK 測試音訊](https://github.com/openai/whisper/blob/6e3be77e1a105e59086e3e21ff5f609fd6fa89a5/tests/jfk.flac)：純英文 API 測試樣本，來源與 hash 固定在 Whisper 區段。

- [OpenAI Whisper large-v3-turbo](https://huggingface.co/openai/whisper-large-v3-turbo) 與 [mobiuslabsgmbh/faster-whisper-large-v3-turbo](https://huggingface.co/mobiuslabsgmbh/faster-whisper-large-v3-turbo)：Turbo 原始模型與 CTranslate2 發布權重；固定 revision／檔案 SHA256 在 `config/versions.json` 的 `whisper_turbo`。與完整版本共用原生 GPU runtime，不隨 Git 散布權重。

- [Qwen3-ASR](https://github.com/QwenLM/Qwen3-ASR)：Qwen 官方模型與使用說明。本 repo 的 CPU profile 使用 [audio-cpp/audio.cpp-gguf](https://huggingface.co/audio-cpp/audio.cpp-gguf) 第三方 GGUF Q8_0 轉換權重，由 LocalAI 固定 CPU OCI 內的 [audio.cpp](https://github.com/0xShug0/audio.cpp) 執行，並非官方 Python runtime。來源 revision、OCI digest、權重 SHA256 在 `modern_cpu_asr` 區段。
- [FireRedASR2S](https://github.com/FireRedTeam/FireRedASR2S) 與 [FireRedASR2-AED](https://huggingface.co/FireRedTeam/FireRedASR2-AED)：官方 AED 程式與權重，固定程式 archive SHA256、模型 revision 與全部必要檔案 hash。僅載入 AED 模組，以 CPU FP32 執行；上游程式與權重下載到 `.localai/`，不隨 Git 散布。
- [kaldi-native-fbank](https://github.com/csukuangfj/kaldi-native-fbank)：FireRed 特徵擷取依賴，固定 CPython 3.12 Linux wheel SHA256。共用 CPU runtime 的其他套件版本亦記錄於 `modern_cpu_asr.base_packages`。

- [Fun-ASR-Nano-2512-hf](https://huggingface.co/FunAudioLLM/Fun-ASR-Nano-2512-hf)：官方 native HF checkpoint，與 GGUF、原 FunASR checkpoint 分開。使用 [Transformers](https://github.com/huggingface/transformers) 原生實作、[PyTorch CPU](https://pytorch.org/)、torchaudio 與其他獨立 venv 套件；全部版本與權重 revision／SHA256 在 `nano_hf` 區段。權重、依賴與上游 README 留在 `.localai/`，不隨 Git 散布。

- [MediaTek Breeze-ASR-25](https://huggingface.co/MediaTek-Research/Breeze-ASR-25) 與 [Breeze-ASR-26](https://huggingface.co/MediaTek-Research/Breeze-ASR-26)：聯發科官方權重，在本機以固定 [CTranslate2](https://github.com/OpenNMT/CTranslate2)／Transformers 轉 CPU INT8，使用 faster-whisper。來源、轉換產物 SHA256 及獨立 runtime 套件版本見 `breeze_cpu`；26 為台語轉華語中文字，兩者權重不隨 Git 散布。
- [行政院 115 年 3 月公益廣告](https://www.ey.gov.tw/Page/463789EEBA7377FC/9c1f7ecb-a125-4aee-aaa0-ed46f4b296a8)：教育部「臺灣台語輸入法 APP」台語錄音的前 8 秒，僅作 Breeze 26 功能驗證。ZIP 與原始 MP3 SHA256 見 `breeze_cpu.taigi_sample`；音檔與原始腳本不隨 Git 散布。
- [sherpa-onnx SenseVoice](https://k2-fsa.github.io/sherpa/onnx/sense-voice/index.html)：k2-fsa 維護的 SenseVoice ONNX 匯出與 CPU Python／C++ runtime；固定匯出 archive、model.onnx、tokens、Sherpa／core wheel 與 [ONNX](https://github.com/onnx/onnx) 檢查器 wheel 的 SHA256 見 `modern_cpu_asr`。僅使用 FP32 模型；權重、第三方套件留在 `.localai/`。
