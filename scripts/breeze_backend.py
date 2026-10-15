"""LocalAI gRPC adapter for official Breeze 25/26 converted to CPU INT8."""
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
from faster_whisper import WhisperModel
import backend_pb2 as pb
import backend_pb2_grpc as rpc
from transcription_conversion import convert_text

ROOT = Path(os.environ['LOCALAI_ASR_ROOT'])
STATE = ROOT / '.localai'
PIN = json.loads((ROOT / 'config/versions.json').read_text())['breeze_cpu']
sys.path.insert(0, str(Path(__file__).parent / 'common'))
from grpc_auth import get_auth_interceptors


def language_mode(value):
    mode = (value or '').strip().lower()
    mode = {'': 'auto', 'zh-tw': 'zh', 'zh-cn': 'zh', 'en-us': 'en'}.get(mode, mode)
    if mode not in ('auto', 'zh', 'en'):
        raise ValueError('Use language=auto, zh or en; Breeze 26 Taigi is intended for Chinese output')
    return None if mode == 'auto' else mode


def read_audio(path):
    with wave.open(str(path), 'rb') as audio:
        if (audio.getframerate(), audio.getnchannels(), audio.getsampwidth()) != (16000, 1, 2):
            raise ValueError('Expected 16 kHz mono PCM16 WAV')
        if audio.getnframes() > 60 * 16000:
            raise ValueError('Breeze CPU profile accepts at most 60 seconds per recording')
        return np.frombuffer(audio.readframes(audio.getnframes()), dtype='<i2').astype(np.float32) / 32768


class BackendServicer(rpc.BackendServicer):
    def Health(self, request, context):
        return pb.Reply(message=b'OK')

    def LoadModel(self, request, context):
        try:
            if request.CUDA:
                raise ValueError('Breeze profiles are CPU-only')
            candidate = Path(request.Model)
            if not candidate.is_absolute():
                candidate = STATE / 'models' / candidate
            for model_id, profile in PIN['profiles'].items():
                expected = (STATE / 'models' / profile['directory']).resolve()
                if candidate.resolve() == expected:
                    break
            else:
                raise ValueError('Unknown Breeze CPU model path')
            self.model = WhisperModel(str(expected), device='cpu', compute_type=PIN['compute_type'],
                                      cpu_threads=PIN['threads'], num_workers=1, local_files_only=True)
            native = self.model.model
            if native.device != 'cpu' or native.compute_type not in ('int8', 'int8_float32'):
                raise RuntimeError('Breeze did not load on CPU with INT8 weights')
            self.evidence = {'model': model_id, 'engine_class': type(native).__name__,
                             'wrapper_class': type(self.model).__name__, 'device': native.device,
                             'compute_type': native.compute_type, 'source_model': profile['repo']}
            (STATE / 'reports' / (profile['report_prefix'] + '-load.json')).write_text(json.dumps(self.evidence, indent=2) + '\n')
            return pb.Result(success=True, message='Loaded ' + model_id + ' on CPU INT8')
        except Exception as error:
            print('Breeze LoadModel failed:', repr(error), file=sys.stderr, flush=True)
            return pb.Result(success=False, message=str(error))

    def AudioTranscription(self, request, context):
        try:
            mode = language_mode(request.language)
            if request.translate:
                raise ValueError('Breeze profiles provide ASR, not the Whisper translation task')
            audio = read_audio(request.dst)
            if not audio.size or not np.any(audio):
                return pb.TranscriptResult(text='', segments=[])
            segments, info = self.model.transcribe(audio, language=mode, task='transcribe', beam_size=5,
                temperature=0, condition_on_previous_text=False, initial_prompt=request.prompt or None,
                word_timestamps='word' in request.timestamp_granularities)
            result = pb.TranscriptResult()
            for segment in segments:
                item = result.segments.add(id=segment.id, start=int(segment.start * 1e9), end=int(segment.end * 1e9),
                                           text=convert_text(segment.text))
                for word in segment.words or []:
                    item.words.add(start=int(word.start * 1e9), end=int(word.end * 1e9), text=convert_text(word.word))
            result.text = ''.join(s.text for s in result.segments)
            return result
        except Exception as error:
            print('Breeze transcription failed:', repr(error), file=sys.stderr, flush=True)
            if context is None:
                raise
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(error))


def serve(address):
    if not address.startswith(('127.0.0.1:', 'localhost:')):
        raise ValueError('Breeze gRPC must bind loopback')
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=1), interceptors=get_auth_interceptors())
    rpc.add_BackendServicer_to_server(BackendServicer(), server)
    if not server.add_insecure_port(address):
        raise RuntimeError('Cannot bind Breeze gRPC')
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
