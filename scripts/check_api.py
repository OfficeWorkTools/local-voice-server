"""Warm up or test the real loopback multipart API using downloaded samples."""
import argparse
import json
import time
import urllib.error
import urllib.request
import uuid
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".localai"
PORT = json.loads((STATE / "install.json").read_text())["port"]
BASE = f"http://127.0.0.1:{PORT}"


def transcribe(filename, language):
    path = STATE / "samples" / filename
    with wave.open(str(path)) as wav:
        assert (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) == (16000, 1, 2)
    boundary = uuid.uuid4().hex
    body = bytearray()
    fields = {"model": "sensevoice-fp32"}
    if language is not None:
        fields["language"] = language
    for key, value in fields.items():
        body.extend(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode())
    body.extend(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="audio.wav"\r\nContent-Type: audio/wav\r\n\r\n'.encode())
    body.extend(path.read_bytes())
    body.extend(f"\r\n--{boundary}--\r\n".encode())
    request = urllib.request.Request(BASE + "/v1/audio/transcriptions", data=body,
                                     headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    start = time.perf_counter()
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.load(response)
    assert result.get("text") and "<|" not in result["text"], result
    if filename == "chinese.wav":
        assert "交易" in result["text"], result
    return {"sample": filename, "language": language, "http_seconds": round(time.perf_counter() - start, 3),
            "text": result["text"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--warmup", action="store_true")
    args = parser.parse_args()
    for attempt in range(60):
        try:
            with urllib.request.urlopen(BASE + "/readyz", timeout=1) as response:
                assert response.status == 200
            break
        except (urllib.error.URLError, TimeoutError):
            time.sleep(1)
    else:
        raise RuntimeError("LocalAI did not become ready on loopback")
    if args.warmup:
        print(json.dumps(transcribe("chinese.wav", "zh"), ensure_ascii=False))
        return
    with urllib.request.urlopen(BASE + "/v1/models", timeout=5) as response:
        assert any(model["id"] == "sensevoice-fp32" for model in json.load(response)["data"])
    with urllib.request.urlopen(BASE + "/app/models?view=installed", timeout=5) as response:
        assert response.status == 200
    results = [transcribe(sample, language) for sample in ("chinese.wav", "mixed.wav")
               for language in ("zh", "auto", "", None)]
    report = {"port": PORT, "model": "sensevoice-fp32", "ui_and_model_list": "passed", "results": results,
              "mixed_reference": "放進你的 training 裡面",
              "mixed_english_recovered": ["training" in row["text"].lower() for row in results if row["sample"] == "mixed.wav"]}
    (STATE / "reports/api.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
