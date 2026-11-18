"""Fast, read-only navigator labels for Pinbu Note v0.9.2b.

The research and project metadata remain authoritative. No page positions,
rendered bibliography strings, or display preferences are written to SQLite.
A single tree walk calculates every row, avoiding O(pages²) ancestor lookups.
"""
from __future__ import annotations

from html import escape
from pathlib import PurePosixPath

from .research import page_source, render_reference, roman

MODES = ('printed', 'source', 'tree')
DEFAULT_MODES = ('smart',) + MODES + ('off',)
SECONDARY_MODES = ('author', 'tags', 'title', 'none')
HOVER_MODES = ('summary', 'full', 'simple')


def _safe_mode(value, choices, fallback):
    return value if value in choices else fallback


def next_mode(current, available):
    """Cycle only through real page-number types, never bogus printed labels."""
    options = [m for m in MODES if m in available]
    if not options:
        return 'tree'
    if current not in options:
        return options[0]
    return options[(options.index(current) + 1) % len(options)]


def _reference_summary(ref):
    if not ref:
        return ''
    if ref.get('type') in ('film', 'television', 'video'):
        creator = ref.get('title', '')
    else:
        author = (ref.get('authors') or ref.get('editors') or [])
        creator = author[0].split(',')[0].strip() if author else ref.get('organisation') or ref.get('title', '')
        if len(author) > 1:
            creator += ' et al.'
    return f"{creator} ({ref.get('year') or 'no date'})"


def _source_kind(page):
    origin = str(page_source(page) or '').lower().split('?', 1)[0]
    extension = PurePosixPath(origin.replace('\\', '/')).suffix
    if extension in ('.ppt', '.pptx', '.odp', '.key'):
        return 'Slide'
    if extension in ('.png', '.jpg', '.jpeg', '.tiff', '.tif', '.bmp', '.gif', '.webp'):
        return 'Image'
    if extension == '.epub':
        return 'E-book page'
    return 'PDF page' if extension == '.pdf' else 'Source page'


def _rule_label(rule, source_number):
    number = rule['start_label'] + source_number - rule['start_pdf']
    if number < 1:
        return str(source_number)
    scheme = rule['scheme']
    if scheme == 'arabic':
        return str(number)
    if number > 3999:
        return str(source_number)
    text = roman(number)
    return text.lower() if scheme == 'roman-lower' else text


def _tooltip(info, hover):
    title = escape(str(info['title']))
    if hover == 'simple':
        return f'<qt>{title}</qt>'
    pieces = [f'<b>{title}</b>',
              f"{escape(info['number_tooltip'])}"]
    if info['source_number'] is not None:
        pieces.append(f"{escape(info['source_kind'])} {info['source_number']}")
    pieces.append(f"Tree position {info['tree_number']}")
    if info['reference_id'] is not None:
        pieces.append(('Direct page reference' if info['origin'] == 'direct'
                       else 'Inherited reference from ' + escape(info['origin_name'])))
        if hover == 'full' and info['reference_spans']:
            formatted = ''.join(
                '<i>' + escape(span.text) + '</i>' if span.italic else escape(span.text)
                for span in info['reference_spans'])
            pieces.append(formatted)
        elif info['reference_summary']:
            pieces.append(escape(info['reference_summary']))
    if info['tag_names'] and hover != 'simple':
        pieces.append('Tags: ' + escape(', '.join(info['tag_names'][:8])))
    return '<qt>' + '<br>'.join(pieces) + '</qt>'


def build_display_rows(research, tree, pages, *, default='smart', overrides=None,
                       secondary='author', hover='summary',
                       reference_labels=False):
    """Pure presentation data indexed by *stable page ID*.

    Printed page is exposed when a reference is attached, a numbering rule
    applies, or a manual page label exists; otherwise Smart defaults to tree
    order, even when the underlying source_page metadata is non-sequential.
    """
    default = _safe_mode(default, DEFAULT_MODES, 'smart')
    secondary = _safe_mode(secondary, SECONDARY_MODES, 'author')
    hover = _safe_mode(hover, HOVER_MODES, 'summary')
    overrides = overrides or {}
    by_id = {p['id']: p for p in pages}
    refs = research['references']
    groups = research['reference_assignments']['groups']
    direct_refs = research['reference_assignments']['pages']
    numbering = research['numbering']
    group_numbers = numbering['groups']
    manual_numbers = numbering['pages']
    sources = numbering['sources']
    tags = research['tags']
    tag_links = research['tag_assignments']
    tag_masks = research['tag_exclusions']
    out = {}

    def descend(nodes, ancestors, inherited_ref, ref_origin, inherited_tags):
        ordinal = 0  # each group's immediate pages get a separate order
        for node in nodes:
            if node['type'] == 'group':
                gid = node['id']
                reference = inherited_ref
                origin = ref_origin
                if gid in groups:
                    reference = groups[gid]
                    origin = ('group', node['name']) if reference else ('excluded', node['name'])
                new_tags = (inherited_tags - set(tag_masks['groups'].get(gid, ())))
                new_tags |= set(tag_links['groups'].get(gid, ()))
                descend(node['children'], ancestors + [gid], reference, origin, new_tags)
                continue
            ordinal += 1
            pid = node['page_id']
            page = by_id.get(pid)
            if page is None:
                continue
            reference = direct_refs.get(pid, inherited_ref)
            origin = ('direct', 'page') if pid in direct_refs else ref_origin
            ref = refs.get(reference)
            direct = pid in direct_refs and reference is not None
            source_value = page.get('source_page')
            source_number = source_value if type(source_value) is int and source_value > 0 else None
            calc_source = source_number or 1
            manual = manual_numbers.get(pid)
            source_name = page_source(page)
            rule = None
            if source_name:
                for candidate in sources.get(source_name, []):
                    if calc_source >= candidate['start_pdf']:
                        rule = candidate
            for ancestor in ancestors:
                candidate = group_numbers.get(ancestor)
                if candidate and calc_source >= candidate['start_pdf']:
                    rule = candidate
            has_printed = bool(ref is not None or manual is not None or rule is not None)
            printed = (manual if manual is not None else
                       _rule_label(rule, calc_source) if rule is not None else str(calc_source))
            available = (('printed',) if has_printed else ()) + (
                ('source',) if source_number is not None else ()) + ('tree',)
            chosen = overrides.get(pid, default)
            if chosen == 'smart':
                chosen = 'printed' if has_printed else 'tree'
            if chosen not in available and chosen != 'off':
                chosen = 'printed' if has_printed else 'tree'
            labels = {'printed': printed, 'source': str(source_number) if source_number is not None else '',
                      'tree': str(ordinal), 'off': ''}
            names = sorted(tags[tag_id]['name'] for tag_id in
                           ((inherited_tags - set(tag_masks['pages'].get(pid, ())))
                            | set(tag_links['pages'].get(pid, ()))) if tag_id in tags)
            summary = _reference_summary(ref)
            hint = {'printed': 'Printed page (citation locator)',
                    'source': _source_kind(page) + ' (original document position)',
                    'tree': 'Tree order (within this group; changes on reordering)',
                    'off': 'Page number hidden'}[chosen]
            hint += (': ' + labels[chosen]) if labels[chosen] else ''
            spans = (render_reference(ref, parent=refs.get(ref.get('parent_id')))
                     if ref and hover == 'full' else [])
            info = {'id': pid, 'title': page.get('title') or 'Untitled page',
                    'number': labels[chosen], 'number_mode': chosen,
                    'number_tooltip': hint, 'available_modes': available,
                    'printed_number': printed if has_printed else None,
                    'source_number': source_number, 'source_kind': _source_kind(page),
                    'tree_number': ordinal, 'reference_id': reference if ref else None,
                    'origin': origin[0] if ref else 'none',
                    'origin_name': origin[1] if ref else '', 'direct': direct,
                    'reference_summary': summary, 'reference_spans': spans,
                    'tag_names': names}
            info['secondary'] = (
                summary if secondary == 'author' else
                ', '.join(names[:2]) if secondary == 'tags' else
                (ref.get('title', '') if ref else '') if secondary == 'title' else '')
            # Generated titles are strictly visual. The underlying source
            # title and bibliographic reference are never rewritten.
            if reference_labels and ref and summary:
                locator = labels[chosen] or printed or str(calc_source)
                info['display_title'] = f'{summary} · p. {locator}'
            info['tooltip'] = _tooltip(info, hover)
            out[pid] = info

    descend(tree, [], None, ('none', ''), set())
    return out


def group_reference_labels(research, tree, *, enabled=False):
    """Build display names for groups, following inherited references.

    A group can attach a reference directly, inherit the parent group's
    reference, or explicitly suppress inheritance with a null assignment.
    This function mirrors those rules in build_display_rows(), and reads
    only existing dictionaries. The returned labels never enter project data.
    """
    if not enabled:
        return {}
    refs = research['references']
    assignments = research['reference_assignments']['groups']
    labels = {}

    def descend(nodes, inherited):
        for node in nodes:
            if node['type'] != 'group':
                continue
            gid = node['id']
            assigned = assignments[gid] if gid in assignments else inherited
            ref = refs.get(assigned)
            summary = _reference_summary(ref)
            if summary:
                # Keep the original chapter name visible as context, rather
                # than replacing dozens of distinguishable groups with the
                # same author-and-year heading.
                name = node['name']
                labels[gid] = (summary if name.casefold() == summary.casefold()
                               else f'{summary} · {name}')
            descend(node.get('children', ()), assigned)

    descend(tree, None)
    return labels
