# Pinbu Note v0.9.2a — Research Foundation (experimental source candidate)

**Please use copies of your notebooks when testing this early development build.**
This release is not yet a published, cross-platform tested release; it builds on
v0.9.1 SafeSave (with optional second backup and health verification).

## What's included

- **Navigator-first referencing:** Right-click a group, subgroup or page in
  Page Navigator → **Research · References & Tags**. Create, assign, select or
  edit bibliographic source information, with a small live Harvard preview.
- **Copy formatted references:** **Copy Reference → In text (with or without
  page), Narrative, or Bibliography.** Clipboard includes escaped HTML for
  italic titles in rich-text editors, plus a plain-text fallback. Copy never
  modifies the notebook. Missing reference-list fields are flagged.
- **First Cite Them Right Harvard (13th-edition) templates:** books, chapters in
  edited books, journals, websites, films, television and online video.
  Basic examples and punctuation are covered by automated tests. Complex
  special cases and institutional variations need further review before
  production academic submission; compare with official Cite Them Right.
- **Book/chapter linking:** A chapter reference can choose a parent edited book,
  sharing the book's publisher, editor and title without repeating them.
- **Per-page and group metadata:** One reference record is stored per work;
  group/page assignments are sparse. Page citations inherit the nearest group
  reference unless the page supplies an override or explicit "no reference".
- **Printed-page mapping:** Defaults to PDF page numbers. Right-click a group to
  set a bulk printed-page offset (Arabic or Roman); right-click a page to
  override its printed number individually. Page numbers track the source PDF
  page index, not rearranged navigator positions.
- **Research tags:** Create/apply tags to groups or pages, inherit tags through
  the navigator, and explicitly mask tags inherited from a parent. Right-click
  the navigator background to find pages by tag or linked reference.
- **Undo and page reorganisation:** Edits participate in per-tab Undo; moving,
  ungrouping or transferring pages preserves their effective citation, tags and
  printed-page labels. Tab-exchange and SafeSave transfer the research records
  along with the ordinary tab project.json.

## Storage and compatibility

Research data stays **inside the existing portable SQLite notebook**, in the
per-tab `project.json` row of the `files` table (not an extra external
sidecar). `research.references` contains unique-ID bibliographic records;
`reference_assignments` maps sparse group/page IDs to source IDs;
`numbering` stores group/source range rules and per-page exceptions;
`tags`, `tag_assignments` and `tag_exclusions` store compact tag definitions
and inclusion/exclusion rules. Data is validated on load and save. HTML is
never persisted as the source-of-truth for bibliography formatting.

**Notebook container format is now v7; tab project manifest format is v5.**
Older v5/v6 notebooks are readable and upgrade upon saving. v0.9.1 and earlier
must NOT be used to edit v7 notebooks; version guards will reject incompatible
format versions. SafeSave backup format remains v1 and previous histories are
retained. Keep a copy of a v0.9.1 notebook for rollback.

## Deliberately still to come

- Full bibliography compilation across all tabs and reference-list generation
- Comprehensive Cite Them Right specialty sources / disambiguation rules
- Multi-select bulk chapter-reference application / Smart Import hints
- Citation chips linked inside the notes editor; RIS/BibTeX/CSL imports
- More powerful search and tag management for notes and annotations
- Proven native Windows/macOS GUI and installer validation

Windows installer staging filename: `PinbuNote_Setup_v0.9.2a.exe`
macOS candidate DMGs: `PinbuNote-0.9.2a-macOS-arm64-unsigned.dmg` and
`PinbuNote-0.9.2a-macOS-x86_64-unsigned.dmg`.

## Research guidance consulted

Cite Them Right, 13th edition (Pears and Shields, 2025) and contemporary UK
university guidance, including:
- https://www.ncl.ac.uk/mediav8/academic-skills-kit/file-downloads/manage-info/2025%20Cite%20Them%20Right%20Harvard%20Style%20Sheet.pdf
- https://dmu-ac-uk.libanswers.com/ref/faq/241706
- https://dmu-ac-uk.libanswers.com/ref/faq/241703

These are references for implementing templates, not a claim that the prototype
already covers every entry in the official style guide.
