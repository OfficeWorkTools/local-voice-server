import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".localai"
sys.path.insert(0, str(STATE / "backends/cpu-funasr"))
from transcription_conversion import convert_text

cases = {
    "甚至出现交易几乎停滞的情况": "甚至出現交易幾乎停滯的情況",
    "放进你的 training 里面": "放進你的 training 裏面",
    "": "",
    "English training 123\n": "English training 123\n",
}
for original, expected in cases.items():
    assert convert_text(original) == expected, (original, convert_text(original))
(STATE / "reports/conversion.json").write_text(json.dumps({"mode": "s2t", "cases": cases, "passed": True}, ensure_ascii=False, indent=2) + "\n")
print("OpenCC s2t conversion checks passed")
