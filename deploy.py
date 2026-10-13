#!/usr/bin/env python3
"""Install the pinned LocalAI CPU service; all runtime files stay in .localai."""
import argparse
import hashlib
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATE = ROOT / ".localai"
BACKEND = STATE / "backends/cpu-funasr"
MODEL = STATE / "models/SenseVoiceSmall-official"
UNIT = "localai-sensevoice-fp32.service"
UNIT_PATH = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "systemd/user" / UNIT
PINS = json.loads((ROOT / "config/versions.json").read_text())


def run(*args, **kwargs):
    subprocess.run([str(a) for a in args], check=True, **kwargs)


def digest(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def download(url, target, expected):
    if target.exists() and digest(target) == expected:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".part")
    run("curl", "--fail", "--location", "--retry", "3", "--retry-all-errors",
        "--connect-timeout", "30", "--max-time", "900", "--proto", "=https", "--proto-redir", "=https",
        "--output", temporary, "--url", url)
    if digest(temporary) != expected:
        raise RuntimeError(f"SHA256 mismatch: {target.name}; the existing file was not replaced")
    temporary.replace(target)


def environment():
    return {**os.environ, "MODELSCOPE_CACHE": str(STATE / "cache/modelscope"),
            "HF_HOME": str(STATE / "cache/huggingface"),
            "OMP_NUM_THREADS": "8", "MKL_NUM_THREADS": "8"}


def port():
    return json.loads((STATE / "install.json").read_text())["port"]


def ensure_owner():
    if UNIT_PATH.exists() and f"WorkingDirectory={STATE}\n" not in UNIT_PATH.read_text():
        raise RuntimeError(f"{UNIT} belongs to another checkout; refusing to overwrite or control it")


def repair_link():
    link = BACKEND / "SenseVoiceSmall-official"
    if link.is_symlink():
        link.unlink()
    elif link.exists():
        raise RuntimeError(f"Refusing to replace a real directory: {link}")
    link.symlink_to("../../models/SenseVoiceSmall-official", target_is_directory=True)


def write_unit(service_port):
    # Paths are validated before generation; keep systemd command lines literal.
    binary = STATE / "bin/local-ai"
    command = [str(binary), "run", "--address", f"127.0.0.1:{service_port}",
               "--models-path", str(STATE / "models"), "--backends-path", str(STATE / "backends"),
               "--data-path", str(STATE / "data"), "--galleries=[]", "--threads", "8",
               "--load-to-memory", "sensevoice-fp32", "--max-active-backends", "1"]
    UNIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    UNIT_PATH.write_text(f"""[Unit]
Description=LocalAI SenseVoiceSmall CPU FP32

[Service]
Type=simple
WorkingDirectory={STATE}
ExecStart={' '.join(command)}
ExecStartPost={sys.executable} {ROOT / 'scripts/check_api.py'} --warmup
Environment=MODELSCOPE_CACHE={STATE / 'cache/modelscope'}
Environment=HF_HOME={STATE / 'cache/huggingface'}
Environment=OMP_NUM_THREADS=8
Environment=MKL_NUM_THREADS=8
Environment=GOMAXPROCS=4
Environment=GOMEMLIMIT=1GiB
Restart=on-failure
RestartSec=5
TimeoutStartSec=180
TimeoutStopSec=45

[Install]
WantedBy=default.target
""")


def install(service_port):
    if sys.version_info < (3, 11):
        raise RuntimeError("Python 3.11 or newer is required")
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise RuntimeError("Only Linux x86_64 is supported")
    if any(c.isspace() or c in '\"$%\\' for c in str(ROOT) + sys.executable):
        raise RuntimeError("Use a checkout and Python path without whitespace, quotes, $, %, or backslashes")
    for command in ("curl", "ffmpeg", "systemctl"):
        if not shutil.which(command):
            raise RuntimeError(f"Missing prerequisite: {command}")
    ensure_owner()
    run("systemctl", "--user", "show-environment", stdout=subprocess.DEVNULL)
    if subprocess.run(["systemctl", "--user", "is-active", "--quiet", UNIT]).returncode == 0:
        run("systemctl", "--user", "stop", UNIT)
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", service_port))
    if shutil.disk_usage(ROOT).free < 6 * 1024**3:
        raise RuntimeError("At least 6 GiB free disk space is required")
    available = next(int(line.split()[1]) for line in Path("/proc/meminfo").read_text().splitlines()
                     if line.startswith("MemAvailable:"))
    if available < 4 * 1024**2:
        raise RuntimeError("At least 4 GiB available RAM is required; stop other heavy models first")
    for name in ("bin", "models", "backends", "data", "samples", "reports"):
        (STATE / name).mkdir(parents=True, exist_ok=True)
    binary = STATE / "bin/local-ai"
    download(PINS["localai"]["url"], binary, PINS["localai"]["sha256"])
    binary.chmod(0o755)
    metadata = BACKEND / "metadata.json"
    if not metadata.exists():
        for attempt in range(3):
            try:
                run(binary, "backends", "install", PINS["backend"]["uri"], "cpu-funasr", "funasr",
                    "--backend-galleries=[]", "--backends-path", STATE / "backends", cwd=STATE)
                break
            except subprocess.CalledProcessError:
                if attempt == 2:
                    raise
                time.sleep(2)
    if json.loads(metadata.read_text())["digest"] != PINS["backend"]["digest"]:
        raise RuntimeError("Installed backend digest differs from the pinned version")
    if digest(BACKEND / "backend.py") != PINS["backend"]["backend_py_sha256"]:
        raise RuntimeError("Installed backend.py differs from the verified official backend")
    model = PINS["model"]
    for filename, expected in model["files"].items():
        download(f"https://huggingface.co/{model['repo']}/resolve/{model['revision']}/{filename}",
                 MODEL / filename, expected)
    chinese = PINS["samples"]["chinese"]
    download(chinese["url"], STATE / "samples/chinese.wav", chinese["sha256"])
    mixed = PINS["samples"]["mixed"]
    mixed_file = STATE / "samples/mixed-source.wav"
    if not mixed_file.exists() or digest(mixed_file) != mixed["sha256"]:
        with urllib.request.urlopen(mixed["metadata_url"], timeout=30) as response:
            source = json.load(response)["rows"][0]["row"]["audio"][0]["src"]
        if not source.startswith("https://datasets-server.huggingface.co/cached-assets/"):
            raise RuntimeError("Unexpected mixed-sample download host")
        download(source, mixed_file, mixed["sha256"])
    run("ffmpeg", "-nostdin", "-v", "error", "-y", "-i", mixed_file,
        "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", "-bitexact", STATE / "samples/mixed.wav")
    shutil.copyfile(ROOT / "config/sensevoice-fp32.yaml", STATE / "models/sensevoice-fp32.yaml")
    repair_link()
    (STATE / "install.json").write_text(json.dumps({"port": service_port}) + "\n")
    # The official entrypoint relocates the bundled Python before direct verification.
    run(BACKEND / "run.sh", "--help", cwd=BACKEND, env=environment(), stdout=subprocess.DEVNULL)
    # Validate actual loaded parameters before starting this checkout's service.
    run(BACKEND / "venv/bin/python", ROOT / "scripts/verify_fp32.py", env=environment())
    write_unit(service_port)
    run("systemctl", "--user", "daemon-reload")
    run("systemctl", "--user", "enable", "--now", UNIT)
    run(sys.executable, ROOT / "scripts/check_api.py")
    print(f"GUI: http://127.0.0.1:{service_port}/app/models?view=installed&model=sensevoice-fp32")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["install", "start", "stop", "restart", "status", "logs", "test", "verify-fp32", "repair-link"])
    parser.add_argument("--port", type=int, help="Installation port; default 8767 on a fresh checkout")
    args = parser.parse_args()
    if args.command != "install" and args.port is not None:
        parser.error("--port is only accepted with install")
    if args.command == "install":
        service_port = args.port if args.port is not None else (port() if (STATE / "install.json").exists() else 8767)
        if not 1024 <= service_port <= 65535:
            parser.error("Use a port from 1024 to 65535")
        install(service_port)
    elif args.command == "test":
        run(sys.executable, ROOT / "scripts/check_api.py")
    elif args.command == "verify-fp32":
        run(BACKEND / "run.sh", "--help", cwd=BACKEND, env=environment(), stdout=subprocess.DEVNULL)
        run(BACKEND / "venv/bin/python", ROOT / "scripts/verify_fp32.py", env=environment())
    elif args.command == "repair-link":
        repair_link()
    else:
        ensure_owner()
        if args.command == "logs":
            run("journalctl", "--user", "-u", UNIT, "-n", "60", "--no-pager")
        else:
            run("systemctl", "--user", args.command, UNIT, *( ["--no-pager"] if args.command == "status" else []))


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, subprocess.CalledProcessError) as error:
        print(f"Deployment failed: {error}", file=sys.stderr)
        sys.exit(1)
