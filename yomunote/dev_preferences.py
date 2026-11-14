"""One-time, read-only import of safe Yomu Note UI preferences into Text Lab.

The development application's QSettings namespace stays separate. A snapshot
of harmless display/input preferences is copied once; no notebook paths,
recent-project lists, backup destinations or other application state are read
into the development settings. Existing Yomu Note settings are never written.
"""
from __future__ import annotations

SEED_KEY = 'integration/preferencesImportedFromYomuNoteV083b'

# Deliberately explicit allowlist: adding a new persistence key elsewhere
# must not silently make the experimental app open real projects.
SAFE_UI_KEYS = frozenset({
    'theme',
    'defaultFont', 'defaultFontSize', 'defaultBold', 'defaultItalic',
    'defaultAlignment', 'showWebLink', 'showJumpEditPosition',
    'annotationPenWidth',
    'reducedMotion', 'previewClarity',
    'readingCelebrationMotion', 'readingCelebrations',
    'readingConfetti', 'readingMilestones',
    'readingViewPersist', 'readingViewRememberScroll',
    'readingViewSharedZoom', 'readingViewStartAtTop',
    'pageNavigatorView', 'showPageNavigator',
    'ocrDpi', 'ocrJoinLines', 'ocrLanguage',
    'focusRepeat', 'focusSounds', 'focusVolume',
    'importCustomLabel', 'importLabelFormat', 'smartImportCollapseGroups',
    'backupCount',
})


def import_from_user_preferences(dev_settings, user_settings) -> int:
    """Seed development UI settings ONCE from production. Return keys copied.

    Both inputs are QSettings-compatible objects; this helper deliberately
    avoids constructing or modifying the production settings itself. If the
    experimental app was already used, its UI keys are deliberately reset
    ONCE to the user's production choices. Later development edits are kept.
    """
    if dev_settings.value(SEED_KEY, False, type=bool):
        return 0
    copied = 0
    for key in sorted(SAFE_UI_KEYS):
        if user_settings.contains(key):
            value = user_settings.value(key)
            if value is not None:
                dev_settings.setValue(key, value)
                copied += 1
    dev_settings.setValue(SEED_KEY, True)
    dev_settings.sync()
    return copied
