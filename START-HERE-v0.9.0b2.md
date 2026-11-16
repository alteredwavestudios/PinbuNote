# Pinbu Note v0.9.0b2 — SafeSave source hotfix

This is an experimental source candidate with a corrected close warning and crash recovery. **Do not use your only copy of coursework for initial testing.**

Windows: extract, double-click `run-windows.bat`. macOS: extract and run `./run-mac.command` (use `chmod +x run-mac.command` if your extractor removes executable permissions).

Pinbu automatically saves the working database locally; **Save & Close** or the ordinary **Save** button publishes to your selected `.pinbunote` location. **Close Without Saving** does not publish, but deliberately retains recoverable local work.

If Pinbu dies unexpectedly, the next launch offers a copy of the last committed local save in the OS-local `Pinbu Note/Recovered` folder. Previous v0.9.0b1 sessions can still be accessed manually from File → Recover Local Working Copy.

See `RELEASE_NOTES_v0.9.0b2.md` for test steps, limitations and expected release packages.
