"""Load the installed official backend and verify real CPU FP32 parameters."""
import collections
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".localai"
BACKEND = STATE / "backends/cpu-funasr"
sys.path.insert(0, str(BACKEND))
import backend
import backend_pb2
import torch

pins = json.loads((ROOT / "config/versions.json").read_text())
weights = STATE / "models/SenseVoiceSmall-official/model.pt"
with weights.open("rb") as f:
    checksum = hashlib.file_digest(f, "sha256").hexdigest()
assert checksum == pins["model"]["files"]["model.pt"], "Model checksum mismatch"
servicer = backend.BackendServicer()
reply = servicer.LoadModel(backend_pb2.ModelOptions(Model=str(weights.parent), CUDA=False), None)
assert reply.success, reply.message
model = servicer.model.model
types = collections.Counter(str(parameter.dtype) for parameter in model.parameters())
devices = {parameter.device.type for parameter in model.parameters()}
assert types == {"torch.float32": 917}, types
assert devices == {"cpu"}, devices
assert model.__class__.__name__ == "SenseVoiceSmall", type(model)
vad_root = Path(servicer.model.vad_kwargs["init_param"]).parent
for filename, expected in pins["vad"]["files"].items():
    with (vad_root / filename).open("rb") as f:
        assert hashlib.file_digest(f, "sha256").hexdigest() == expected, f"VAD checksum mismatch: {filename}"
report = {"source_model": pins["model"]["repo"], "revision": pins["model"]["revision"],
          "model_sha256": checksum, "parameter_dtypes": dict(types), "device": "cpu",
          "torch": torch.__version__, "native_backend_load_passed": True, "vad_files_verified": True}
(STATE / "reports/fp32.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
