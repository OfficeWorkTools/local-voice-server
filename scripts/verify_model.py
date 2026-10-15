"""Verify the selected FunASR profile or an explicit Whisper/CPU ASR profile."""
import collections
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if len(sys.argv) == 2 and sys.argv[1] in json.loads((ROOT / 'config/versions.json').read_text()).get('breeze_cpu', {}).get('profiles', {}):
    from verify_breeze_model import verify
    verify(sys.argv[1])
    sys.exit(0)
if sys.argv[1:] == ['fun-asr-nano-2512-hf-cpu']:
    from verify_nano_hf_model import verify
    verify()
    sys.exit(0)
if len(sys.argv) == 2 and sys.argv[1] in json.loads((ROOT / 'config/versions.json').read_text()).get('modern_cpu_asr', {}).get('profiles', {}):
    from verify_cpu_model import verify
    verify(sys.argv[1])
    sys.exit(0)
if len(sys.argv) == 2 and sys.argv[1] in ("whisper-large-v3", "whisper-large-v3-turbo"):
    from verify_whisper_model import verify
    verify(sys.argv[1])
    sys.exit(0)
if sys.argv[1:]:
    raise SystemExit("Use a configured CPU ASR model ID, whisper-large-v3 or whisper-large-v3-turbo")
STATE = ROOT / ".localai"
BACKEND = STATE / "backends/cpu-funasr"
sys.path.insert(0, str(BACKEND))
import backend
import backend_pb2
import torch
import yaml

pins = json.loads((ROOT / "config/versions.json").read_text())
model_id = json.loads((STATE / "install.json").read_text()).get("model", "sensevoice-fp32")
profile = pins["profiles"][model_id]
source = pins[profile["model_key"]]
configuration = yaml.safe_load((STATE / f"models/{model_id}.yaml").read_text())
assert configuration["name"] == model_id and configuration["backend"] == "funasr", configuration
assert configuration["parameters"]["model"] == profile["directory"], "Deployed YAML does not match the selected profile"
assert configuration.get("f16", False) is False, "The selected profile must not request float16"
weights = STATE / "models" / profile["directory"] / "model.pt"
assert (BACKEND / profile["directory"]).resolve() == weights.parent.resolve(), "Backend model symlink does not match the profile"
with weights.open("rb") as f:
    checksum = hashlib.file_digest(f, "sha256").hexdigest()
assert checksum == source["files"]["model.pt"], "Model checksum mismatch"
servicer = backend.BackendServicer()
reply = servicer.LoadModel(backend_pb2.ModelOptions(Model=str(weights.parent), CUDA=False), None)
assert reply.success, reply.message
model = servicer.model.model
types = collections.Counter(str(parameter.dtype) for parameter in model.parameters())
devices = {parameter.device.type for parameter in model.parameters()}
assert set(types) == {"torch." + profile["precision"]}, types
if "parameter_count" in profile:
    assert sum(types.values()) == profile["parameter_count"], types
assert devices == {"cpu"}, devices
assert model.__class__.__name__ == profile["model_class"], type(model)
vad_root = Path(servicer.model.vad_kwargs["init_param"]).parent
for filename, expected in pins["vad"]["files"].items():
    with (vad_root / filename).open("rb") as f:
        assert hashlib.file_digest(f, "sha256").hexdigest() == expected, f"VAD checksum mismatch: {filename}"
report = {"model": model_id, "source_model": source["repo"], "revision": source["revision"],
          "model_class": model.__class__.__name__, "model_directory": profile["directory"],
          "model_sha256": checksum, "parameter_dtypes": dict(types), "device": "cpu",
          "torch": torch.__version__, "native_backend_load_passed": True, "deployed_config_verified": True, "vad_files_verified": True}
(STATE / f"reports/{model_id}-model.json").write_text(json.dumps(report, indent=2) + "\n")
if model_id == "sensevoice-fp32":
    (STATE / "reports/fp32.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
