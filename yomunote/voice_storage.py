"""Private local voice file locations and crash-recoverable PCM WAV output.

No folders or files are created by import, constructing preferences, or listing
microphones. File writes begin only after a user explicitly starts recording.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import os
import struct
import tempfile
from uuid import uuid4


def default_recordings_folder(documents: str | Path | None = None) -> Path:
    """Respect Windows known folders, macOS Documents, and Linux XDG dirs.

    The Qt path resolver uses Windows Shell folders and Linux XDG user dirs.
    The fallback only applies if that resolver reports no usable path.
    """
    if documents is None:
        from PySide6.QtCore import QStandardPaths
        documents = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.DocumentsLocation)
    root = Path(documents).expanduser() if documents else Path.home() / 'Documents'
    return root / 'PinbuNotes' / 'Recordings'


def recordings_folder(settings) -> Path:
    chosen = str(settings.value('voice/recordingsFolder', '') or '').strip()
    return Path(chosen).expanduser() if chosen else default_recordings_folder()


def unique_recording_path(folder: Path, *, mode: str, now: datetime | None = None) -> Path:
    now = now or datetime.now()
    return Path(folder) / (f'Pinbu_{mode}_{now:%Y-%m-%d_%H-%M-%S}_'
                           f'{uuid4().hex[:8]}.wav')


def ephemeral_dictation_path() -> Path:
    return Path(tempfile.gettempdir()) / f'pinbu-dictation-{uuid4().hex}.wav'


class RecoverableWaveWriter:
    """Mono signed PCM16 WAV; update the header periodically for crash recovery.

    A partial audio capture remains playable up to the most recent sync.  WAV
    uses 32-bit RIFF lengths, so one file must stay below 4 GiB.
    """
    def __init__(self, path: str | Path, sample_rate: int = 16000):
        self.path = Path(path)
        self.sample_rate = int(sample_rate)
        if self.sample_rate <= 0:
            raise ValueError('Invalid sample rate')
        self._out = self.path.open('xb+')
        self.data_bytes = 0
        self._out.write(self._header(0))
        self.sync()

    def _header(self, length: int) -> bytes:
        return struct.pack('<4sI4s4sIHHIIHH4sI',
                           b'RIFF', 36 + length, b'WAVE', b'fmt ', 16,
                           1, 1, self.sample_rate, self.sample_rate * 2,
                           2, 16, b'data', length)

    def write(self, pcm: bytes) -> None:
        if not pcm:
            return
        if len(pcm) % 2:
            raise ValueError('Audio samples must contain complete Int16 values')
        if self.data_bytes + len(pcm) > 0xFFFFFFFF - 36:
            raise OSError('WAV is near the 4 GiB limit; stop and start a new recording')
        self._out.write(pcm)
        self.data_bytes += len(pcm)

    def sync(self) -> None:
        if self._out.closed:
            return
        pos = self._out.tell()
        self._out.seek(0)
        self._out.write(self._header(self.data_bytes))
        self._out.seek(pos)
        self._out.flush()
        os.fsync(self._out.fileno())

    def close(self) -> None:
        if not self._out.closed:
            try:
                self.sync()
            finally:
                self._out.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
