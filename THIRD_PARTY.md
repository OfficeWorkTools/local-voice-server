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
