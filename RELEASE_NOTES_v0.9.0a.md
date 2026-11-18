# Pinbu Note v0.9.0a — Voice Studio experiment

Based on the tested v0.8.7c source. This is an **experimental source build**.

## New

- Edit → Voice Studio: Dictation and Lecture modes with explicit record action.
- In-app and OS consent are required before microphone capture starts; no
  automatic microphone monitoring on startup or while configuring devices.
- Pause/Stop release microphone access; Voice Studio close asks before stopping.
- Lecture WAV files (not in .pinbunote) stored in OS Documents/PinbuNotes/Recordings;
  Preferences lets users pick another local folder.
- Recoverable PCM WAV with frequently updated headers and 2-second disk sync.
- Offline whisper.cpp transcription, user-selected executable and local model.
- Lecture transcripts transcribed **after recording stops**, with chunk timestamps,
  saved as separate .txt files beside recordings. Failed runs leave a .partial
  transcript and the original WAV for recovery.
- Dictation text inserts using the existing rich-text editor's cursor and Undo.
- 48 kHz Float32 / stereo microphone fallback resamples locally to 16 kHz mono.
- macOS app requests microphone permission with NSMicrophoneUsageDescription.

## Limitations and important testing

This candidate does not bundle the whisper.cpp CLI or ggml recognition models.
Recording works independently of transcription. A user must select both local
files before transcription can run. Long lecture transcription is offline and
post-recording (not real-time). Chunk timestamps are approximate minute starts.
A macOS/Windows native interactive test is required before a public release.
No uploads, network APIs or automatic model downloads are used by Voice Studio.

Other features, notebook formats and old project compatibility are unchanged.

## Expected locally built artifacts (not yet native-verified)

- Windows: `PinbuNote_Setup_v0.9.0a.exe`
- macOS: `PinbuNote-0.9.0a-macOS-arm64-unsigned.dmg`
- macOS: `PinbuNote-0.9.0a-macOS-x86_64-unsigned.dmg`
