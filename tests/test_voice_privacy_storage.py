"""v0.9.0a: voice storage paths, WAV durability, and capture privacy contract."""
from __future__ import annotations

from array import array
import ast
from pathlib import Path
import sys
import wave

from yomunote.voice_storage import (RecoverableWaveWriter,
                                    default_recordings_folder,
                                    unique_recording_path, recordings_folder)
from yomunote.voice_pcm import VoicePcmConverter


class Settings:
    def __init__(self, location=''):
        self.location = location
    def value(self, key, default=''):
        return self.location if key == 'voice/recordingsFolder' else default


def test_recording_folder_defaults_to_os_documents_without_creating_it(tmp_path):
    docs = tmp_path / 'My Documents'
    chosen = default_recordings_folder(docs)
    assert chosen == docs / 'PinbuNotes' / 'Recordings'
    assert not docs.exists(), 'Reading a setting cannot create folders.'
    assert recordings_folder(Settings(str(tmp_path / 'custom'))) == tmp_path / 'custom'
    assert not (tmp_path / 'custom').exists()


def test_unique_recordings_are_outside_notebook_and_safe(tmp_path):
    a = unique_recording_path(tmp_path, mode='Lecture')
    b = unique_recording_path(tmp_path, mode='Lecture')
    assert a != b and a.suffix == '.wav'
    assert a.parent == tmp_path
    assert not a.exists() and not b.exists()


def test_wav_header_is_recoverable_even_before_close(tmp_path):
    wav = tmp_path / 'lecture.wav'
    writer = RecoverableWaveWriter(wav)
    writer.write(b'\x00\x00' * 1600)
    writer.sync()
    # Simulate a reader opening the file while a session is in progress.
    with wave.open(str(wav), 'rb') as reader:
        assert reader.getnframes() == 1600
        assert reader.getframerate() == 16000
        assert reader.readframes(1600) == b'\x00\x00' * 1600
    writer.write(b'\x00\x00' * 800)
    writer.close()
    with wave.open(str(wav), 'rb') as reader:
        assert reader.getnframes() == 2400


def test_pcm_resampler_streaming_float_stereo():
    import struct
    converter = VoicePcmConverter(48000, 2, 'Float')
    data = b''.join(struct.pack('<ff', 0.1, 0.5) for _ in range(4800))
    output = b''.join(converter.convert(data[i:i+137]) for i in range(0, len(data), 137))
    samples = array('h')
    samples.frombytes(output)
    if sys.byteorder != 'little':
        samples.byteswap()
    assert len(samples) == 1600
    assert 9700 < samples[20] < 9950  # stereo mix 0.3, within rounding


def test_pcm_converter_handles_partial_frames():
    convert = VoicePcmConverter(16000, 1, 'Int16')
    assert convert.convert(b'\x01') == b''
    assert convert.convert(b'\x00') == b'\x01\x00'


def test_audio_capture_only_constructed_in_explicit_record_callback():
    path = Path(__file__).resolve().parents[1] / 'yomunote' / 'voice_dialog.py'
    code = path.read_text(encoding='utf-8')
    module = ast.parse(code)
    cls = next(n for n in module.body if isinstance(n, ast.ClassDef) and n.name == 'VoiceStudio')
    calls = []
    for fn in cls.body:
        if isinstance(fn, ast.FunctionDef):
            for node in ast.walk(fn):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'QAudioSource':
                    calls.append(fn.name)
    assert calls == ['_start_capture']
    assert 'QMicrophonePermission()' in code
    assert "QMessageBox.question(self, 'Allow microphone for this recording?'" in code
    assert 'self._source.stop()' in code


def test_build_declares_macos_microphone_usage():
    root = Path(__file__).resolve().parents[1]
    build = (root / 'build-mac.command').read_text(encoding='utf-8')
    assert 'NSMicrophoneUsageDescription' in build
