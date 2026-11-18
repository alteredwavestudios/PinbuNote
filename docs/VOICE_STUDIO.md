# Pinbu Voice Studio — v0.9.0a experimental guide

**Privacy first:** Pinbu does not open or monitor your microphone when launching,
selecting a device, opening a notebook, or entering Preferences. Record and
Resume each require a fresh in-app confirmation. The operating system must
also grant microphone permission. Pause/Stop immediately release audio capture.

## Lecture recording files

The default is the platform's own Documents folder, resolved by Qt:

| OS | Typical default path |
| --- | --- |
| Windows | `%USERPROFILE%\Documents\PinbuNotes\Recordings` (may be OneDrive/redirected) |
| macOS | `~/Documents/PinbuNotes/Recordings` |
| Linux | `XDG_DOCUMENTS_DIR/PinbuNotes/Recordings` (fallback `~/Documents/...`) |

**Preferences → Voice Studio** lets you choose a different folder. This
preference is per-user, **not saved in the notebook**. The folder is created
only when a lecture recording begins. Recordings are kept outside `.pinbunote`
and are never embedded in it. Lecture files are WAV (mono PCM16, 16 kHz) and
transcripts are plain text, in the same folder. Do not store sensitive
recordings in a shared or synced folder without considering its privacy.

Pause releases the microphone but leaves the WAV open; Resume re-asks for
permission and continues the same file. A WAV header is updated and flushed
approximately every 2 seconds to make interrupted recordings recoverable.
Always use Stop when possible, so everything is properly closed.

Use **Open saved WAV…** in Voice Studio to retry transcription of an earlier
lecture recording. The original recording remains untouched if recognition
fails. A partial transcript is checkpointed after each successfully
recognised chunk. Retry starts a fresh attempt (so old partial data is kept).

## Transcription setup (offline)

This experimental version does not bundle a recogniser or model. Obtain:

1. The open-source whisper.cpp **whisper-cli** program, from its releases or
   compiled from source: https://github.com/ggml-org/whisper.cpp/releases
2. A local `ggml-*.bin` model, for example `ggml-base.en.bin` (English) or
   a multilingual model, from:
   https://github.com/ggml-org/whisper.cpp/blob/master/models/README.md

On macOS with Homebrew, `brew install whisper.cpp` installs `whisper-cli`;
the model is still separate. Windows users should select `whisper-cli.exe`
from a trusted prebuilt or local compilation; keep accompanying DLLs beside
it. On Linux, compile it with CMake or use a trusted distribution package.

In **Edit → Voice Studio**, use Browse next to **Local whisper.cpp program**
and **Offline speech model**. Paths are stored in your own OS preferences.
No download is performed by Pinbu, and the app makes no transcription network
calls. Choose a whisper.cpp executable you trust (it is an external program).

After **Stop**, if both paths are valid, recognition begins locally; otherwise
use **Transcribe saved audio** after configuring them. Recognition happens
AFTER recording stops in this first version, not in parallel. Long recordings
are split into one-minute excerpts to limit memory; each lecture excerpt is
prefixed with its approximate starting timestamp. Check names, quotations,
punctuation, and page citations: automatic transcription may be inaccurate.

Dictation audio goes to the system temp directory and is deleted on a normal
Voice Studio close. Its resulting text stays in the preview until the user
clicks **Insert text into current notes**, preserving normal notes Undo.
Avoid editing critical coursework with voice input before testing.

## OS permissions and packaging

- macOS `.app` declares `NSMicrophoneUsageDescription` and asks on Record.
- Windows and Linux use Qt's native audio and permission handling; desktop
  portals, OS privacy controls and audio server availability can vary.
- Denied permission must never start capture. Stop and Pause release the input.
- This feature requires testing on real microphone devices in native builds.

Lecture recording is subject to the university's recording policy and the
consent/privacy rights of everyone whose speech may be captured.
