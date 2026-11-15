# Pinbu Note v0.8.7c — Patchwork themes and page centring

Source update based on the user-tested v0.8.7b build. Native Windows/macOS GUI verification is still required.

## New: extra vertical scroll room

- The previous default page-top behaviour is unchanged.
- **View → Allow extra vertical page scrolling** adds scroll room above and below all page previews; **View → Centre current page vertically** centres on demand.
- **Groups right-click → Allow extra page scrolling in this group** enables the same behaviour just for a group, including nested pages; this preference travels in the notebook, participates in Undo/Redo, and survives rearranging groups.
- Page/annotation coordinates, image resolution, OCR geometry, caching and original PDFs are unchanged. The only change is to the QGraphicsScene scrollable rectangle.
- Page scroll memory now retains a bounded signed coordinate for readings beyond the edge; old saved positions remain readable.

## Theme packs

The View > Colour Theme menu now groups existing palettes into Japanese & Kawaii, Pinbu Textiles, French Art Nouveau and Modern & System. Preferences uses the same categories. Previous theme IDs remain unchanged to preserve saved settings.

Added 8 calm three-column palettes: **Appliqué Morning**, **Peachwork Linen**, **Night Quilt**, **Moonlit Sampler**, **Iris & Pearl**, **Ginkgo & Gold**, **Peacock & Brass**, and **Velvet Poppy**. Two light and two dark palettes for each new inspiration.

## Native smoke tests required

1. Open a short landscape slide, enable extra scrolling, scroll upwards until it is vertically centred. Switch away and back; repeat after notebook restart.
2. Right-click a group, enable its own extra scrolling, confirm other groups retain top-aligned behaviour. Undo/Redo and move a page within the group.
3. Fit, zoom with wheel/trackpad, and use OCR or annotation on the slide. Ensure page coordinates are unchanged.
4. Test all newly grouped themes in light and dark mode, including editing, menus, buttons and column rearrangement.
5. Build native Windows installers and macOS app; check startup and old `.yominote` / `.yomunote` notebook files.

## Compatibility

`yomunote` remains the internal Python package until the larger compatibility-preserving package migration. No notebook schemas, source file bytes or OCR assets were renamed.

Expected release assets: `PinbuNote_Setup_v0.8.7c.exe`, `PinbuNote-0.8.7c-macOS-arm64-unsigned.dmg` and `PinbuNote-0.8.7c-macOS-x86_64-unsigned.dmg`.
