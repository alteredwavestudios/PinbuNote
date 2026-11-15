"""Plan stable, undo-friendly plain-text bullet edits for sticky notes.

No Qt or HTML required: the model stores ordinary Unicode lines. The composer
applies these edits in reverse source order using one QTextCursor edit block.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BulletEdit:
    start: int
    end: int
    replacement: str


def plan_bullet_toggle(text: str, selection_start: int, selection_end: int) -> list[BulletEdit]:
    """Toggle current/selected lines, preserving indentation and existing bullets.

    A range ending exactly at the next line's beginning excludes that next line.
    Empty lines can start a bullet; mixed selections gain only missing bullets.
    """
    if not isinstance(text, str):
        raise TypeError('text must be a string')
    start = min(max(0, selection_start), len(text))
    end = min(max(start, selection_end), len(text))
    # Search from real start; if selection ends on a following line boundary,
    # the last touched character still belongs to the previous line.
    start_line = text.count('\n', 0, start)
    last_character = max(start, end - 1) if end > start else start
    end_line = text.count('\n', 0, last_character)
    positions = []
    offset = 0
    for number, line in enumerate(text.split('\n')):
        if start_line <= number <= end_line:
            indent_len = len(line) - len(line.lstrip(' \t'))
            prefix_at = offset + indent_len
            has_bullet = line[indent_len:].startswith('• ')
            positions.append((prefix_at, has_bullet))
        offset += len(line) + 1
    remove = bool(positions) and all(has for _,has in positions)
    return [BulletEdit(pos, pos+2, '') if remove else BulletEdit(pos, pos, '• ')
            for pos, has in positions if (has if remove else not has)]
