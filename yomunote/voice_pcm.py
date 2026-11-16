"""Small dependency-free, streaming Qt PCM converter for whisper.cpp WAV files.

Input can be a native Qt audio device format (8/16/32-bit integer or Float32,
mono or multichannel at the device's preferred sample rate). Output is signed
16-bit, 16 kHz, mono PCM. State is continuous across callback boundaries.
"""
from __future__ import annotations

from array import array
import math
import sys


SAMPLE_BYTES = {'UInt8': 1, 'Int16': 2, 'Int32': 4, 'Float': 4}


class VoicePcmConverter:
    def __init__(self, sample_rate: int, channels: int, sample_format: str):
        self.rate = int(sample_rate)
        self.channels = int(channels)
        self.format = str(sample_format)
        if self.rate <= 0 or not 1 <= self.channels <= 8 or self.format not in SAMPLE_BYTES:
            raise ValueError('Unsupported microphone format')
        self.frame_bytes = self.channels * SAMPLE_BYTES[self.format]
        self._pending = b''
        self._input_index = 0
        self._next_output_at = 0.0
        self._previous = None

    def _decode(self, data: bytes):
        if self.format == 'UInt8':
            return [(value - 128) / 128.0 for value in data]
        typ = {'Int16': 'h', 'Int32': 'i', 'Float': 'f'}[self.format]
        values = array(typ)
        values.frombytes(data)
        if sys.byteorder != 'little':
            values.byteswap()
        if typ == 'h':
            return (value / 32768.0 for value in values)
        if typ == 'i':
            return (value / 2147483648.0 for value in values)
        return (max(-1., min(1., value)) if math.isfinite(value) else 0.
                for value in values)

    def convert(self, payload: bytes) -> bytes:
        payload = self._pending + bytes(payload)
        frames = len(payload) // self.frame_bytes
        cut = frames * self.frame_bytes
        self._pending = payload[cut:]
        if not frames:
            return b''
        samples = list(self._decode(payload[:cut]))
        mono = samples if self.channels == 1 else (
            sum(samples[i:i+self.channels]) / self.channels
            for i in range(0, len(samples), self.channels))
        output = array('h')
        source_step = self.rate / 16000.0
        for sample in mono:
            n = self._input_index
            if self._previous is None:
                if self._next_output_at == 0.0:
                    output.append(self._int16(sample))
                    self._next_output_at += source_step
            else:
                while self._next_output_at <= n:
                    weight = self._next_output_at - (n - 1)
                    mixed = self._previous + (sample - self._previous) * weight
                    output.append(self._int16(mixed))
                    self._next_output_at += source_step
            self._previous = sample
            self._input_index += 1
        if sys.byteorder != 'little':
            output.byteswap()
        return output.tobytes()

    @staticmethod
    def _int16(value: float) -> int:
        return max(-32768, min(32767, round(float(value) * 32767)))
