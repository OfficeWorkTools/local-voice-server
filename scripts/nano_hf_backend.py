"""LocalAI gRPC adapter for the pinned native Nano HF model, CPU FP32 only."""
import argparse
from concurrent import futures
import json
import os
from pathlib import Path
import signal
import sys
import wave

import grpc
import numpy as np
import torch
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor
import backend_pb2 as pb
import backend_pb2_grpc as rpc
from transcription_conversion import convert_text

ROOT = Path(os.environ['LOCALAI_ASR_ROOT'])
STATE = ROOT / '.localai'
PIN = json.loads((ROOT / 'config/versions.json').read_text())['nano_hf']
sys.path.insert(0, str(Path(__file__).parent / 'common'))
from grpc_auth import get_auth_interceptors


def language_mode(value):
    mode = (value or '').strip().lower()
    mode = {'': 'auto', 'zh-tw': 'zh', 'zh-cn': 'zh', 'en-us': 'en'}.get(mode, mode)
    if mode not in ('auto', 'zh', 'en', 'ja'):
        raise ValueError('Use language=auto, zh, en or ja')
    return None if mode == 'auto' else mode


def read_audio(path):
    with wave.open(str(path), 'rb') as audio:
        if (audio.getframerate(), audio.getnchannels(), audio.getsampwidth()) != (16000, 1, 2):
            raise ValueError('Expected 16 kHz mono PCM16 WAV')
        if audio.getnframes() > 60 * 16000:
            raise ValueError('Nano HF profile accepts at most 60 seconds per recording')
        return np.frombuffer(audio.readframes(audio.getnframes()), dtype='<i2').astype(np.float32) / 32768


class BackendServicer(rpc.BackendServicer):
    def Health(self, request, context):
        return pb.Reply(message=b'OK')

    def LoadModel(self, request, context):
        try:
            if request.CUDA:
                raise ValueError('Nano HF profile is CPU-only')
            expected = (STATE / 'models' / PIN['directory']).resolve()
            candidate = Path(request.Model)
            if not candidate.is_absolute():
                candidate = STATE / 'models' / candidate
            if candidate.resolve() != expected:
                raise ValueError('Unknown Nano HF model path')
            torch.set_num_threads(PIN['threads'])
            torch.manual_seed(0)
            self.processor = AutoProcessor.from_pretrained(str(expected), local_files_only=True, trust_remote_code=False)
            self.model = AutoModelForSpeechSeq2Seq.from_pretrained(
                str(expected), local_files_only=True, trust_remote_code=False, dtype=torch.float32,
            ).to('cpu').eval()
            devices = sorted({p.device.type for p in self.model.parameters()})
            dtypes = sorted({str(p.dtype) for p in self.model.parameters()})
            if devices != ['cpu'] or dtypes != ['torch.float32'] or getattr(self.model.config, 'quantization_config', None):
                raise RuntimeError('Nano HF must load unquantized on CPU float32')
            self.evidence = {'model': PIN['model_id'], 'engine_class': type(self.model).__name__,
                             'processor_class': type(self.processor).__name__, 'device': 'cpu',
                             'parameter_devices': devices, 'parameter_dtypes': dtypes, 'trust_remote_code': False}
            (STATE / 'reports/nano-hf-load.json').write_text(json.dumps(self.evidence, indent=2) + '\n')
            return pb.Result(success=True, message='Loaded Nano HF on CPU float32')
        except Exception as error:
            print('Nano HF LoadModel failed:', repr(error), file=sys.stderr, flush=True)
            return pb.Result(success=False, message=str(error))

    def AudioTranscription(self, request, context):
        try:
            mode = language_mode(request.language)
            if request.translate or request.timestamp_granularities:
                raise ValueError('Nano HF profile provides transcription text, without translation or timestamps')
            audio = read_audio(request.dst)
            if not audio.size or not np.any(audio):
                return pb.TranscriptResult(text='', segments=[])
            inputs = self.processor.apply_transcription_request(
                audio=audio, language=mode, prompt=request.prompt or None,
                processor_kwargs={'return_tensors': 'pt', 'audio_kwargs': {'sampling_rate': 16000},
                                  'text_kwargs': {'padding': True}},
            )
            with torch.inference_mode():
                generated = self.model.generate(**inputs, max_new_tokens=PIN['max_new_tokens'], do_sample=False)
            tokens = generated[:, inputs.input_ids.shape[1]:]
            eos = self.model.generation_config.eos_token_id
            if int(tokens[0, -1]) not in (eos if isinstance(eos, list) else [eos]):
                raise RuntimeError('Nano HF reached its output limit; retry with a shorter recording')
            text = convert_text(self.processor.batch_decode(tokens, skip_special_tokens=True)[0].strip())
            if not text:
                raise RuntimeError('Nano HF returned empty text for non-silent audio')
            return pb.TranscriptResult(text=text, segments=[pb.TranscriptSegment(id=0, start=0, end=0, text=text)])
        except Exception as error:
            print('Nano HF transcription failed:', repr(error), file=sys.stderr, flush=True)
            if context is None:
                raise
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(error))


def serve(address):
    if not address.startswith(('127.0.0.1:', 'localhost:')):
        raise ValueError('Nano HF gRPC must bind loopback')
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=1),
                         interceptors=get_auth_interceptors())
    rpc.add_BackendServicer_to_server(BackendServicer(), server)
    if not server.add_insecure_port(address):
        raise RuntimeError('Cannot bind Nano HF gRPC')
    server.start()
    def stop(signum, frame):
        server.stop(0)
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    server.wait_for_termination()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--addr', default='127.0.0.1:50051')
    serve(parser.parse_args().addr)
