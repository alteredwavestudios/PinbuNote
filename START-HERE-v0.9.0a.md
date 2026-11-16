# Pinbu Note v0.9.0a: Voice Studio testing

Keep v0.8.7c installed as your stable version and use a disposable notebook.

**Windows:** run `run-windows.bat` for source mode. To make an installer,
run `build-windows.ps1` then `build-installer-windows.ps1` in PowerShell.

**macOS:** run `run-mac.command`; then `build-mac.command` to package the app.
macOS requires the app's Info.plist microphone privacy declaration (included).

1. Open Edit → Voice Studio, observe the microphone is OFF.
2. In Preferences, verify the default lecture folder under OS Documents.
   Optionally set a different folder. Opening Preferences MUST NOT record.
3. Choose a microphone, pick Dictation, click Record and grant permission.
   Speak, Pause (microphone off), Resume (permission asked), Stop.
4. Select your **local** whisper.cpp `whisper-cli` and offline `ggml-*.bin`
   model. These are NOT bundled. Click Transcribe if not automatic after Stop.
   Click Insert to insert recognised text into the active notes at the caret.
5. Switch to Lecture, record and Stop. Check `.wav` is under Documents/
   PinbuNotes/Recordings, plus `.transcript.txt` after recognition finishes.
   Large recordings are transcribed in minute-long chunks on a worker thread.
6. Disconnect the microphone, deny OS permission, try an invalid recordings
   directory, and close mid-recording; in all cases no input may remain open.
7. Test a Windows frozen installer and macOS `.app` before distribution.

**Privacy:** Audio is local; Pinbu makes no transcription network calls.
Lecture audio is intentionally retained, including if transcription fails.
Dictation audio is temporary and deleted on closing Voice Studio.
