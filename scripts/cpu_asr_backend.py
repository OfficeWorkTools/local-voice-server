"""CPU-only LocalAI ASR: native audio.cpp Qwen and official FireRed AED, with s2t."""
import argparse
import atexit
from concurrent import futures
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import wave

import grpc
import backend_pb2 as pb
import backend_pb2_grpc as rpc
from transcription_conversion import convert_text

ROOT = Path(os.environ['LOCALAI_ASR_ROOT'])
STATE = ROOT / '.localai'
PIN = json.loads((ROOT / 'config/versions.json').read_text())['modern_cpu_asr']
sys.path.insert(0, str(Path(__file__).parent / 'common'))
from grpc_auth import get_auth_interceptors


def language_mode(value, profile):
    value = (value or '').strip().lower()
    value = {'': 'auto', 'zh-tw': 'zh', 'zh-cn': 'zh', 'en-us': 'en'}.get(value, value)
    if value not in profile['languages']:
        raise ValueError('This CPU profile supports language=' + ','.join(profile['languages']) + '; use Auto-detect for FireRed')
    return value


class BackendServicer(rpc.BackendServicer):
    def __init__(self):
        self.child = self.channel = self.log = None
        self.model = self.profile = None
        self.evidence = {}
        atexit.register(self.close)

    def close(self):
        if self.channel:
            self.channel.close()
            self.channel = None
        if self.child and self.child.poll() is None:
            self.child.terminate()
            try:
                self.child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.child.kill()
                self.child.wait(timeout=5)
        self.child = None
        if self.log:
            self.log.close()
            self.log = None

    def Health(self, request, context):
        return pb.Reply(message=b'OK')

    def LoadModel(self, request, context):
        try:
            if request.CUDA:
                raise ValueError('This backend is CPU-only')
            for model_id, profile in PIN['profiles'].items():
                expected = (STATE / 'models' / profile['directory']).resolve()
                candidate = Path(request.Model)
                if not candidate.is_absolute():
                    candidate = STATE / 'models' / candidate
                if candidate.resolve() == expected:
                    break
            else:
                raise ValueError('Unknown CPU model path')
            self.profile, self.model_id = profile, model_id
            self.evidence = {'model': model_id, 'engine': profile['engine'], 'device': 'cpu', 'precision': profile['precision']}
            if profile['engine'] == 'audio-cpp':
                if self.child:
                    raise ValueError('Load only one model per backend process')
                with socket.socket() as sock:
                    sock.bind(('127.0.0.1', 0))
                    address = '127.0.0.1:' + str(sock.getsockname()[1])
                native = STATE / 'backends' / PIN['audio_cpp']['backend_name']
                self.log = (STATE / 'reports' / f'{model_id}-native-{os.getpid()}.log').open('w')
                self.child = subprocess.Popen([str(native / 'run.sh'), '--addr', address], cwd=native,
                    stdout=self.log, stderr=self.log,
                    env={**os.environ, 'CUDA_VISIBLE_DEVICES': '', 'AUDIOCPP_DEFAULT_BACKEND': 'cpu'})
                self.channel = grpc.insecure_channel(address, options=[('grpc.max_receive_message_length', 50 * 1024 * 1024)])
                grpc.channel_ready_future(self.channel).result(timeout=30)
                self.stub = rpc.BackendStub(self.channel)
                token = os.environ.get('LOCALAI_GRPC_AUTH_TOKEN', '')
                self.headers = [('authorization', 'Bearer ' + token)] if token else []
                load = pb.ModelOptions()
                load.CopyFrom(request)
                # Keep the controller identity; only the local file path changes.
                load.ModelFile = str(expected)
                load.CUDA = False
                del load.Options[:]
                load.Options.extend(['family:qwen3_asr', 'task:asr', 'backend:cpu', 'threads:8'])
                result = self.stub.LoadModel(load, metadata=self.headers, timeout=180)
                if not result.success:
                    raise RuntimeError(result.message)
                self.evidence.update(engine_class='audio.cpp/qwen3_asr', options=list(load.Options), native_pid=self.child.pid)
            elif profile['engine'] == 'sherpa-onnx':
                sys.path.insert(0, str(Path(__file__).parent / 'vendor'))
                import sherpa_onnx
                self.model = sherpa_onnx.OfflineRecognizer.from_sense_voice(
                    model=str(expected / 'model.onnx'), tokens=str(expected / 'tokens.txt'),
                    provider='cpu', num_threads=PIN['threads'], language='auto', use_itn=profile['use_itn'])
                if self.model.config.model_config.provider != 'cpu':
                    raise RuntimeError('Sherpa did not load with CPU provider')
                self.evidence.update(engine_class=type(self.model).__name__, provider='cpu',
                                     sherpa_onnx=sherpa_onnx.__version__, use_itn=profile['use_itn'])
            else:
                import torch
                torch.set_num_threads(PIN['threads'])
                torch.set_num_interop_threads(1)
                torch.manual_seed(0)
                sys.path.insert(0, str(Path(__file__).parent / 'vendor'))
                source = Path(__file__).parent / 'firered-source' / PIN['firered_source']['directory']
                sys.path.insert(0, str(source / 'fireredasr2s'))
                from fireredasr2 import FireRedAsr2, FireRedAsr2Config
                config = FireRedAsr2Config(use_gpu=False, use_half=False, beam_size=3, nbest=1, return_timestamp=False)
                self.model = FireRedAsr2.from_pretrained('aed', str(expected), config)
                parameters = list(self.model.model.parameters())
                devices = sorted({p.device.type for p in parameters})
                dtypes = sorted({str(p.dtype) for p in parameters})
                if devices != ['cpu'] or dtypes != ['torch.float32']:
                    raise RuntimeError('FireRed did not load as CPU float32')
                self.evidence.update(engine_class=type(self.model.model).__name__, parameter_devices=devices, parameter_dtypes=dtypes)
            (STATE / 'reports' / (model_id + '-load.json')).write_text(json.dumps(self.evidence, indent=2) + '\n')
            return pb.Result(success=True, message='Loaded ' + model_id + ' on CPU')
        except Exception as error:
            self.close()
            print('CPU LoadModel failed:', repr(error), file=sys.stderr, flush=True)
            return pb.Result(success=False, message=str(error))

    def AudioTranscription(self, request, context):
        try:
            mode = language_mode(request.language, self.profile)
            with wave.open(request.dst, 'rb') as audio:
                if (audio.getframerate(), audio.getnchannels(), audio.getsampwidth()) != (16000, 1, 2):
                    raise ValueError('Expected 16 kHz mono PCM16 WAV')
                if audio.getnframes() == 0:
                    return pb.TranscriptResult(text='', segments=[])
            if self.profile['engine'] == 'audio-cpp':
                forwarded = pb.TranscriptRequest()
                forwarded.CopyFrom(request)
                forwarded.language = {'auto': '', 'zh': 'Chinese', 'en': 'English'}[mode]
                result = self.stub.AudioTranscription(forwarded, metadata=self.headers, timeout=180)
                if result.segments:
                    for segment in result.segments:
                        segment.text = convert_text(segment.text)
                        for word in segment.words:
                            word.text = convert_text(word.text)
                    result.text = ''.join(s.text for s in result.segments)
                else:
                    result.text = convert_text(result.text)
                return result
            if self.profile['engine'] == 'sherpa-onnx':
                import numpy as np
                with wave.open(request.dst, 'rb') as audio:
                    samples = np.frombuffer(audio.readframes(audio.getnframes()), dtype='<i2').astype(np.float32) / 32768
                self.model.config.model_config.sense_voice.language = mode
                self.model.recognizer.set_config(self.model.config)
                stream = self.model.create_stream()
                stream.accept_waveform(16000, samples)
                self.model.decode_stream(stream)
                text = convert_text(stream.result.text)
                return pb.TranscriptResult(text=text, segments=[pb.TranscriptSegment(id=0, start=0, end=0, text=text)])
            results = self.model.transcribe(['audio'], [request.dst])
            if len(results) != 1:
                raise RuntimeError('FireRed returned no transcription')
            text = convert_text(results[0]['text'])
            return pb.TranscriptResult(text=text, segments=[pb.TranscriptSegment(id=0, start=0, end=0, text=text)])
        except Exception as error:
            print('CPU transcription failed:', repr(error), file=sys.stderr, flush=True)
            if context is None:
                raise
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(error))


def serve(address):
    if not address.startswith(('127.0.0.1:', 'localhost:')):
        raise ValueError('CPU gRPC must bind loopback')
    service = BackendServicer()
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=1),
        options=[('grpc.max_receive_message_length', 50 * 1024 * 1024)], interceptors=get_auth_interceptors())
    rpc.add_BackendServicer_to_server(service, server)
    server.add_insecure_port(address)
    server.start()
    def stop(signum, frame):
        server.stop(0)
        service.close()
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    server.wait_for_termination()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--addr', default='127.0.0.1:50051')
    serve(parser.parse_args().addr)
