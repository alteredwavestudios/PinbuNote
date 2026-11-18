# Pinbu v0.9.2b — Navigator display preview 🌸

Use a **copy** of your `.pinbunote` notebook for this experimental build.
Run `run-windows.bat` on Windows or `./run-mac.command` on macOS.

1. Open a book or PDF and select **Groups** in the Page Navigator.
2. The number in the lower-right of each page row shows the preferred
   **printed reference page**, or group-order number when unreferenced.
3. **Click the number** repeatedly: Printed → Original PDF/slide → Tree order.
   Hover directly over the number to see which interpretation is active.
4. The same interaction also works in **Individual** view.
5. ◆ is an individually assigned bibliography record; ◇ comes from a group.
6. Hover over the row to view the title and bibliographic summary. Under
   **Settings → Preferences → Page navigator**, choose full bibliography
   on hover if desired.
7. Right-click the page → **Page number display** to select a mode, or
   Reset to Preferences; pressing Alt+N in Groups cycles the selected page.
8. Test an imported book where PDF page 7 corresponds to printed page 1.
   Confirm the printed badge says 1, the source badge says 7, and the tree
   order says 1, 2, 3… within each group.
9. Finally, use **Copy Reference → In text with printed page**, then cycle
   the badge to tree order. The citation must STILL use the printed number.

Display clicks don't save the document or add SQL metadata. Per-page choices
are small local application preferences; on another computer the default
Smart mode applies. Your existing research data and bibliography are portable.

Notebook container **v7**, tab project **v5**, backup **v1** unchanged from
v0.9.2a. Version 0.9.1 is incompatible with research-enabled v7 notebooks.
