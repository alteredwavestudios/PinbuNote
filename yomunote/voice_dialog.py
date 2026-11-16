"""Opt-in voice dictation and lecture recording for Pinbu Note.

Privacy invariant: constructing this dialog, opening Preferences, choosing a
microphone, or selecting a recogniser NEVER creates QAudioSource or requests
OS permission. A user must press Record/Resume, approve Pinbu's consent prompt,
and have OS permission before QAudioSource.start() is reached. Pausing and
stopping both close the input; no live monitoring outside recording state.
"""
from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QMicrophonePermission, QCoreApplication
from PySide6.QtWidgets import (QApplication, QComboBox, QDialog, QFileDialog,
    QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPlainTextEdit,
    QPushButton, QProgressBar, QVBoxLayout, QWidget)

from .voice_pcm import VoicePcmConverter
from .voice_storage import (RecoverableWaveWriter, ephemeral_dictation_path,
                            recordings_folder, unique_recording_path)
from .voice_transcription import OfflineTranscription


class VoiceStudio(QDialog):
    """Recording stays local; transcription runs only with chosen local files."""

    def __init__(self, settings, insert_into_notes, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setWindowTitle('Pinbu Voice Studio  ·  offline')
        self.resize(610, 560)
        self.settings = settings
        self.insert_into_notes = insert_into_notes
        self._source = None  # QAudioSource exists ONLY while actively recording
        self._device_io = None
        self._writer = None
        self._path = None
        self._converter = None
        self._mode_at_start = None
        self._state = 'idle'  # idle | pending | recording | paused | stopped
        self._worker = None
        self._recording_generation = 0
        self._bytes_since_sync = 0
        self._stopping_audio = False

        root = QVBoxLayout(self)
        root.setSpacing(10)
        lead = QLabel('Record only when you choose · offline, under your control')
        lead.setWordWrap(True)
        root.addWidget(lead)
        choose = QHBoxLayout()
        choose.addWidget(QLabel('Mode'))
        self.mode = QComboBox()
        self.mode.addItems(['Dictation', 'Lecture'])
        choose.addWidget(self.mode, 1)
        root.addLayout(choose)
        self.mode.currentIndexChanged.connect(self._mode_changed)
        root.addWidget(QLabel('Input device (listing devices does not activate the microphone)'))
        devices = QHBoxLayout()
        self.microphone = QComboBox()
        devices.addWidget(self.microphone, 1)
        refresh = QPushButton('Refresh devices')
        refresh.clicked.connect(self._refresh_devices)
        devices.addWidget(refresh)
        root.addLayout(devices)
        self._refresh_devices()

        setup = QGridLayout()
        setup.addWidget(QLabel('Local whisper.cpp program'), 0, 0)
        self.executable = QLineEdit(str(settings.value('voice/whisperExecutable', '') or ''))
        self.executable.setPlaceholderText('Select whisper-cli.exe / whisper-cli')
        setup.addWidget(self.executable, 0, 1)
        choose_exe = QPushButton('Browse…')
        choose_exe.clicked.connect(lambda: self._browse_file(self.executable, 'Select whisper.cpp executable'))
        setup.addWidget(choose_exe, 0, 2)
        setup.addWidget(QLabel('Offline speech model'), 1, 0)
        self.model = QLineEdit(str(settings.value('voice/whisperModel', '') or ''))
        self.model.setPlaceholderText('Select a downloaded ggml-*.bin model')
        setup.addWidget(self.model, 1, 1)
        choose_model = QPushButton('Browse…')
        choose_model.clicked.connect(lambda: self._browse_file(self.model, 'Select local ggml Whisper model'))
        setup.addWidget(choose_model, 1, 2)
        root.addLayout(setup)
        self.executable.editingFinished.connect(self._save_recogniser)
        self.model.editingFinished.connect(self._save_recogniser)

        self.location = QLabel()
        self.location.setWordWrap(True)
        self.location.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        root.addWidget(self.location)
        self.mode_help = QLabel()
        self.mode_help.setWordWrap(True)
        root.addWidget(self.mode_help)
        self._mode_changed()

        self.level = QProgressBar()
        self.level.setRange(0, 100)
        self.level.setValue(0)
        self.level.setFormat('Microphone OFF')
        root.addWidget(self.level)
        controls = QHBoxLayout()
        self.record = QPushButton('● Record')
        self.record.clicked.connect(self._request_start)
        self.pause = QPushButton('Pause')
        self.pause.clicked.connect(self._pause)
        self.stop_button = QPushButton('■ Stop')
        self.stop_button.clicked.connect(self._stop)
        for button in (self.record, self.pause, self.stop_button):
            controls.addWidget(button)
        root.addLayout(controls)

        self.status = QLabel('Idle · microphone disconnected')
        self.status.setWordWrap(True)
        root.addWidget(self.status)
        self.transcript = QPlainTextEdit()
        self.transcript.setPlaceholderText('Your offline transcription appears here after recording.')
        root.addWidget(self.transcript, 1)
        self.transcript.textChanged.connect(self._sync_buttons)
        bottom = QHBoxLayout()
        self.open_recording_button = QPushButton('Open saved WAV…')
        self.open_recording_button.clicked.connect(self._open_saved_recording)
        bottom.addWidget(self.open_recording_button)
        self.transcribe_button = QPushButton('Transcribe saved audio')
        self.transcribe_button.clicked.connect(self._transcribe)
        bottom.addWidget(self.transcribe_button)
        self.insert_button = QPushButton('Insert text into current notes')
        self.insert_button.clicked.connect(self._insert)
        bottom.addWidget(self.insert_button)
        root.addLayout(bottom)
        self._sync_buttons()

    def _refresh_devices(self):
        self.microphone.clear()
        try:
            from PySide6.QtMultimedia import QMediaDevices
            inputs = QMediaDevices.audioInputs()
            for device in inputs:
                self.microphone.addItem(device.description(), device)
            if not inputs:
                self.microphone.addItem('No microphone detected', None)
        except Exception as exc:
            self.microphone.addItem(f'Audio devices unavailable: {exc}', None)
        # QMediaDevices.audioInputs() enumerates hardware; never starts capture.

    def _browse_file(self, field, title):
        name, _ = QFileDialog.getOpenFileName(self, title, field.text())
        if name:
            field.setText(name)
            self._save_recogniser()

    def _save_recogniser(self):
        self.settings.setValue('voice/whisperExecutable', self.executable.text().strip())
        self.settings.setValue('voice/whisperModel', self.model.text().strip())

    def _mode_changed(self, *_):
        mode = self.mode.currentText()
        if mode == 'Lecture':
            self.location.setText(f'Lecture WAV and transcript folder: {recordings_folder(self.settings)}')
            self.mode_help.setText('Lecture: keep a recoverable WAV recording outside the notebook. '
                'After Stop, transcribe in manageable chunks, with a timestamp per chunk. '
                'You can change the default folder in Preferences.')
        else:
            self.location.setText('Dictation audio: temporary local file, deleted when this window closes.')
            self.mode_help.setText('Dictation: speak short passages, then transcribe and '
                'insert the editable result into the currently open notes at the cursor.')

    def _sync_buttons(self):
        self.record.setEnabled(self._state in ('idle', 'paused', 'stopped'))
        self.record.setText('Resume recording' if self._state == 'paused' else '● Record')
        self.pause.setEnabled(self._state == 'recording')
        self.stop_button.setEnabled(self._state in ('recording', 'paused'))
        self.mode.setEnabled(self._state in ('idle', 'stopped'))
        self.microphone.setEnabled(self._state in ('idle', 'paused', 'stopped'))
        self.open_recording_button.setEnabled(self._state in ('idle', 'stopped') and self._worker is None)
        self.transcribe_button.setEnabled(self._state == 'stopped' and self._worker is None
                                          and self._path is not None and self._path.exists())
        self.insert_button.setEnabled(bool(self.transcript.toPlainText().strip()))

    def _request_start(self):
        if self._state not in ('idle', 'paused', 'stopped'):
            return
        if self.microphone.currentData() is None:
            QMessageBox.warning(self, 'No microphone', 'Connect a microphone and refresh the list.')
            return
        if self._worker is not None:
            QMessageBox.information(self, 'Transcription active', 'Finish transcription before recording again.')
            return
        if self._state == 'stopped':
            self._path = None
            self.transcript.clear()
        answer = QMessageBox.question(self, 'Allow microphone for this recording?',
            'Pinbu Note will access the selected microphone ONLY while recording.\n\n'
            'Audio is processed locally. Stop or Pause releases the microphone.\n'
            'Allow and begin recording now?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._state = 'pending'
        self._recording_generation += 1
        generation = self._recording_generation
        self._sync_buttons()
        app = QCoreApplication.instance()
        permission = QMicrophonePermission()
        try:
            state = app.checkPermission(permission)
            if state == Qt.PermissionStatus.Denied:
                self._permission_denied()
            elif state == Qt.PermissionStatus.Granted:
                self._start_capture(generation)
            else:
                self.status.setText('Waiting for operating-system microphone permission…')
                # Asynchronous: capture may start only after explicit OS approval.
                app.requestPermission(permission, self,
                    lambda result: self._permission_result(result, generation))
        except Exception as exc:
            self._state = 'idle'
            self._sync_buttons()
            QMessageBox.warning(self, 'Microphone permission error', str(exc))

    def _permission_denied(self):
        self._state = 'paused' if self._writer is not None else 'idle'
        self._sync_buttons()
        self.status.setText('Microphone denied · nothing recorded')
        QMessageBox.warning(self, 'Microphone access denied',
                            'Allow microphone access in your operating-system privacy settings first.')

    def _permission_result(self, permission, generation):
        if generation != self._recording_generation or self._state != 'pending':
            return
        if permission.status() == Qt.PermissionStatus.Granted:
            self._start_capture(generation)
        else:
            self._permission_denied()

    def _start_capture(self, generation):
        if generation != self._recording_generation or self._state != 'pending':
            return
        audio = None
        try:
            # Deliberately import QAudioSource only at this explicitly authorised point.
            from PySide6.QtMultimedia import QAudioSource, QAudioFormat
            device = self.microphone.currentData()
            fmt = QAudioFormat()
            fmt.setSampleRate(16000)
            fmt.setChannelCount(1)
            fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)
            if not device.isFormatSupported(fmt):
                # Most laptop microphones use 48 kHz stereo Float32; record
                # their preferred native format, then resample locally.
                fmt = device.preferredFormat()
            converter = VoicePcmConverter(
                fmt.sampleRate(), fmt.channelCount(), fmt.sampleFormat().name)
            audio = QAudioSource(device, fmt, self)
            io = audio.start()
            from PySide6.QtMultimedia import QAudio
            if io is None or audio.state() == QAudio.State.StoppedState:
                raise RuntimeError('Could not start microphone capture. Check OS privacy settings.')
            if self._writer is None:
                mode = self.mode.currentText()
                if mode == 'Lecture':
                    folder = recordings_folder(self.settings)
                    folder.mkdir(parents=True, exist_ok=True)
                    path = unique_recording_path(folder, mode='Lecture')
                else:
                    path = ephemeral_dictation_path()
                self._writer = RecoverableWaveWriter(path)
                self._path = path
                self._mode_at_start = mode
            self._source = audio
            self._device_io = io
            self._converter = converter
            io.readyRead.connect(self._drain)
            audio.stateChanged.connect(lambda state, src=audio: self._capture_state_changed(src, state))
            self._state = 'recording'
            self.status.setText('● RECORDING · local audio only · microphone active')
            self.level.setFormat('● MICROPHONE ACTIVE · %p%')
            self._sync_buttons()
        except Exception as exc:
            # Even a disk-write failure after start() must IMMEDIATELY
            # release the microphone. Never leave an orphaned audio source.
            if audio is not None:
                try:
                    audio.stop()
                    audio.deleteLater()
                except RuntimeError:
                    pass
            self._source = None
            self._device_io = None
            self._converter = None
            self.level.setValue(0)
            self.level.setFormat('Microphone OFF')
            self._state = 'paused' if self._writer else 'idle'
            self._sync_buttons()
            self.status.setText('Could not begin recording · microphone OFF')
            QMessageBox.warning(self, 'Recording unavailable', str(exc))

    def _capture_state_changed(self, source, state):
        """Never leave the UI indicating recording after device disconnect."""
        from PySide6.QtMultimedia import QAudio
        if (source is not self._source or self._stopping_audio or
                self._state != 'recording'):
            return
        if state == QAudio.State.StoppedState:
            self._state = 'paused'
            self._stop_audio()  # capture has ended; must release device object
            self.status.setText('Microphone stopped or disconnected · capture OFF. '
                                'You may retry Resume or Stop to save.')
            self._sync_buttons()

    def _drain(self):
        if self._state != 'recording' or self._device_io is None:
            return
        try:
            pcm = self._converter.convert(bytes(self._device_io.readAll()))
            if pcm and self._writer:
                self._writer.write(pcm)
                self._bytes_since_sync += len(pcm)
                if self._bytes_since_sync >= 64000:  # ~2 seconds at 16 kHz/16-bit
                    self._writer.sync()
                    self._bytes_since_sync = 0
                from array import array
                samples = array('h')
                samples.frombytes(pcm[:min(len(pcm), 8192)])
                peak = max((abs(x) for x in samples), default=0)
                self.level.setValue(min(100, int(peak / 32768 * 100)))
        except Exception as exc:
            self._state = 'paused'
            self._stop_audio()
            self.status.setText(f'Recording paused after error: {exc}')
            self._sync_buttons()

    def _stop_audio(self):
        # Release microphone before changing any visible state.
        if self._device_io is not None:
            try:
                self._drain()  # flush queued audio before stopping
            except Exception:
                pass
        if self._source is not None:
            self._stopping_audio = True
            try:
                self._source.stop()
            finally:
                self._source.deleteLater()
                self._stopping_audio = False
        self._source = None
        self._device_io = None
        self._converter = None
        self.level.setValue(0)
        self.level.setFormat('Microphone OFF')
        if self._writer:
            self._writer.sync()
        self._bytes_since_sync = 0

    def _pause(self):
        if self._state != 'recording':
            return
        self._stop_audio()
        self._state = 'paused'
        self.status.setText('Paused · microphone disconnected')
        self._sync_buttons()

    def _stop(self, *, transcribe=True):
        if self._state not in ('recording', 'paused'):
            return
        self._recording_generation += 1
        self._stop_audio()
        if self._writer is not None:
            self._writer.close()
            self._writer = None
        self._state = 'stopped'
        self.status.setText(f'Saved: {self._path}' if self._mode_at_start == 'Lecture'
                            else 'Recording stopped · microphone disconnected')
        self._sync_buttons()
        if transcribe and self.executable.text().strip() and self.model.text().strip():
            self._transcribe()
        elif transcribe:
            self.status.setText(self.status.text() + '\nSelect a local whisper.cpp executable and model, then Transcribe.')

    def _open_saved_recording(self):
        """Recover or re-transcribe a previously saved Pinbu lecture WAV."""
        if self._state not in ('idle', 'stopped') or self._worker is not None:
            return
        chosen, _ = QFileDialog.getOpenFileName(self, 'Open a saved Pinbu lecture WAV',
            str(recordings_folder(self.settings)), 'WAV audio (*.wav)')
        if not chosen:
            return
        path = Path(chosen)
        if not path.is_file():
            QMessageBox.warning(self, 'Recording unavailable', 'That WAV file does not exist.')
            return
        self._path = path
        self._mode_at_start = 'Lecture'
        self.mode.setCurrentText('Lecture')
        self.transcript.clear()
        self._state = 'stopped'
        self.status.setText(f'Loaded saved lecture (microphone OFF): {path}')
        self._sync_buttons()

    def _transcribe(self):
        if self._worker is not None or self._state != 'stopped' or not self._path:
            return
        self._save_recogniser()
        exe, model = self.executable.text().strip(), self.model.text().strip()
        if not Path(exe).is_file() or not Path(model).is_file():
            QMessageBox.warning(self, 'Offline transcription not configured',
                'Choose an existing whisper.cpp whisper-cli program and local ggml model. '
                'Pinbu does not download or upload any audio.')
            return
        self._worker = OfflineTranscription(self._path, self._mode_at_start, exe, model, self)
        worker = self._worker
        worker.progress.connect(self.status.setText)
        worker.completed.connect(self._on_complete)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(self._on_worker_finished)
        self.status.setText('Offline transcription running… microphone OFF')
        self._sync_buttons()
        worker.start()

    def _on_complete(self, text, transcript_path):
        self.transcript.setPlainText(text)
        if transcript_path:
            self.status.setText(f'Lecture transcript saved: {transcript_path}\nMicrophone OFF')
        else:
            self.status.setText('Dictation ready to insert · microphone OFF')
        self._sync_buttons()

    def _on_failed(self, message):
        self.status.setText('Transcription failed · saved lecture audio was preserved')
        QMessageBox.warning(self, 'Offline transcription failed', message)

    def _on_worker_finished(self):
        worker = self._worker
        self._worker = None
        if worker:
            worker.deleteLater()
        self._sync_buttons()

    def _insert(self):
        text = self.transcript.toPlainText().strip()
        if text:
            self.insert_into_notes(text)

    def is_recording(self):
        return self._state in ('recording', 'paused', 'pending')

    def closeEvent(self, event):
        if self.is_recording():
            answer = QMessageBox.question(self, 'Stop the recording?',
                'Closing Voice Studio stops and releases the microphone. '
                'Lecture audio recorded so far remains in your recordings folder. Continue?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self._recording_generation += 1  # invalidate pending OS permission callbacks
            if self._state in ('recording', 'paused'):
                self._stop(transcribe=False)
        if self._worker is not None:
            answer = QMessageBox.question(self, 'Stop transcription?',
                'Stop offline transcription and close? The original lecture audio remains saved.',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self._worker.request_stop()
            if not self._worker.wait(4000):
                event.ignore()
                QMessageBox.warning(self, 'Still stopping', 'Transcription is stopping. Close again once it finishes.')
                return
        if self._source is not None:
            self._stop_audio()
        if self._writer is not None:
            self._writer.close()
            self._writer = None
        if self._mode_at_start == 'Dictation' and self._path:
            try:
                self._path.unlink(missing_ok=True)
            except OSError:
                pass
        event.accept()
