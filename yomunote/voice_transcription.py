"""Offline whisper.cpp CLI transcription in a dedicated worker thread.

No network/download code is used.  Audio is read from a saved local WAV.  The
speech model and executable must be selected by the user in Voice Studio.
"""
from __future__ import annotations

from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import threading
from uuid import uuid4
import wave

from PySide6.QtCore import QThread, Signal


def whisper_command(executable: str | Path, model: str | Path, wav: Path,
                    destination_stem: Path) -> list[str]:
    exe, model = Path(executable), Path(model)
    if not exe.is_file():
        raise FileNotFoundError(f'whisper.cpp executable not found: {exe}')
    if not model.is_file():
        raise FileNotFoundError(f'Offline Whisper model not found: {model}')
    return [str(exe), '-m', str(model), '-f', str(wav), '-otxt',
            '-of', str(destination_stem), '-nt']


def format_time(seconds: int) -> str:
    sec = max(0, int(seconds))
    return f'{sec // 3600:02d}:{(sec // 60) % 60:02d}:{sec % 60:02d}'


class OfflineTranscription(QThread):
    """Process bounded audio chunks sequentially; never blocks the Qt GUI.

    Lecture partial transcripts are checkpointed beside the WAV. A failure
    leaves the audio and partial transcript intact for retry and recovery.
    """
    progress = Signal(str)
    completed = Signal(str, str)  # text, saved transcript path (or '')
    failed = Signal(str)

    def __init__(self, wav_path, mode, executable, model, parent=None):
        super().__init__(parent)
        self.wav_path = Path(wav_path)
        self.mode = str(mode)
        self.executable = str(executable)
        self.model = str(model)
        self.cancel = threading.Event()
        self._proc = None

    def request_stop(self):
        self.cancel.set()
        process = self._proc
        if process is not None and process.poll() is None:
            try:
                process.terminate()
            except OSError:
                pass

    def run(self):
        try:
            text, transcript = self._transcribe()
            if not self.cancel.is_set():
                self.completed.emit(text, str(transcript) if transcript else '')
        except Exception as exc:
            if not self.cancel.is_set():
                self.failed.emit(str(exc))

    def _transcribe(self):
        output_path = self.wav_path.with_suffix('.transcript.txt') if self.mode == 'Lecture' else None
        partial = self.wav_path.with_name(self.wav_path.stem + '.transcript.' + uuid4().hex[:8] + '.partial.txt') if output_path else None
        results = []
        with wave.open(str(self.wav_path), 'rb') as source:
            if source.getnchannels() != 1 or source.getsampwidth() != 2 or source.getframerate() != 16000:
                raise ValueError('Voice Studio requires a mono, 16 kHz, PCM16 WAV.')
            samples_per_part = 16000 * (60 if self.mode == 'Lecture' else 120)
            index = 0
            with tempfile.TemporaryDirectory(prefix='pinbu-whisper-') as workspace:
                temporary = Path(workspace)
                while not self.cancel.is_set():
                    audio = source.readframes(samples_per_part)
                    if not audio:
                        break
                    if not any(audio):
                        continue
                    section_path = temporary / f'chunk-{index:05d}.wav'
                    with wave.open(str(section_path), 'wb') as section:
                        section.setnchannels(1)
                        section.setsampwidth(2)
                        section.setframerate(16000)
                        section.writeframes(audio)
                    output_stem = temporary / f'result-{index:05d}'
                    cmd = whisper_command(self.executable, self.model, section_path, output_stem)
                    self.progress.emit(f'Transcribing {format_time(index * (60 if self.mode == "Lecture" else 120))}…')
                    # Never spawn a shell or send recordings to a server.
                    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0) if os.name == 'nt' else 0
                    self._proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                                                  stderr=subprocess.PIPE, creationflags=flags)
                    try:
                        _, error = self._proc.communicate(timeout=600)
                        return_code = self._proc.returncode
                    except subprocess.TimeoutExpired:
                        self._proc.kill()
                        self._proc.communicate()
                        raise TimeoutError('Offline recognition exceeded ten minutes for one segment.')
                    finally:
                        self._proc = None
                    if self.cancel.is_set():
                        return '', None
                    if return_code != 0 or not Path(f'{output_stem}.txt').is_file():
                        raise RuntimeError(f'Whisper could not transcribe the recording: {error.decode("utf-8", "replace")[-600:]}')
                    segment_txt = Path(f'{output_stem}.txt')
                    content = segment_txt.read_text(encoding='utf-8-sig').strip()
                    if content:
                        line = (f'[{format_time(index * 60)}] ' if self.mode == 'Lecture' else '') + content
                        results.append(line)
                        if partial:
                            # Persist after every recognised chunk for crash recovery.
                            with partial.open('a', encoding='utf-8') as out:
                                out.write(line + '\n\n')
                                out.flush()
                                os.fsync(out.fileno())
                    index += 1
        if output_path:
            if partial and partial.is_file():
                os.replace(partial, output_path)
            else:
                output_path.write_text('', encoding='utf-8')
        return '\n\n'.join(results), output_path
