# 上游來源與授權

此 repo 的 MIT 授權僅涵蓋本 repo 原創的部署程式、設定及文件。它不重新授權 LocalAI、FunASR、PyTorch、模型權重或測試音訊。這些檔案在安裝時取得，沒有隨 Git repo 散布，使用時須遵守各上游條款。

- [LocalAI v4.11.0](https://github.com/mudler/LocalAI/tree/v4.11.0)：主程式與原生 CPU FunASR 後端來源。
- [FunASR](https://github.com/modelscope/FunASR)：辨識及 FSMN VAD。
- [FunAudioLLM/SenseVoiceSmall](https://huggingface.co/FunAudioLLM/SenseVoiceSmall)：官方權重；固定版本見 `config/versions.json`，下載的上游 README 保留於模型目錄。
- [PyTorch](https://pytorch.org/)：後端套件內的 CPU 推論引擎。
- [Qwen3-ASR](https://github.com/QwenLM/Qwen3-ASR)：官方中文測試音訊。
- [ky552/ML2021_ASR_ST](https://huggingface.co/datasets/ky552/ML2021_ASR_ST)：公開 test 第 1279 列中英混用音訊與參考文字。依據資料集自己的授權使用。
