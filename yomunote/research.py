"""Pinbu 0.9.2a: offline research metadata for a tab's existing SQLite-backed project.

No media is copied and no formatting HTML is persisted. Stable reference/tag
IDs and sparse group/page assignments live in project.json and therefore use
all existing notebook/backup/restore pipelines. This module deliberately has
NO Qt imports: it can be independently tested and audited.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from html import escape
import re
from uuid import uuid4

SCHEMA = 1
SOURCE_TYPES = ('book', 'chapter', 'journal', 'website', 'film', 'television', 'video')
SAFE_ID = re.compile(r'^[a-f0-9]{32}$')
HEX_COLOUR = re.compile(r'^#[a-fA-F0-9]{6}$')


def valid_target(kind, ident):
    # The modern navigator always creates UUID group IDs, but legacy page
    # IDs are not all UUIDs. Requiring UUIDs for pages would lock a user out
    # of adding citations to an old notebook, despite its stable page ID.
    if kind == 'groups':
        return isinstance(ident, str) and SAFE_ID.fullmatch(ident) is not None
    return (isinstance(ident, str) and 1 <= len(ident) <= 200
            and not any(ord(char) < 32 for char in ident))

REF_FIELDS = frozenset(('type', 'title', 'year', 'authors', 'editors', 'publisher',
    'edition', 'container_title', 'volume', 'issue', 'pages', 'url', 'doi',
    'accessed', 'director', 'medium', 'platform', 'episode', 'notes',
    'organisation', 'parent_id'))


def empty_research():
    return {'schema': SCHEMA, 'references': {},
            'reference_assignments': {'groups': {}, 'pages': {}},
            'numbering': {'groups': {}, 'sources': {}, 'pages': {}},
            'tags': {}, 'tag_assignments': {'groups': {}, 'pages': {}},
            'tag_exclusions': {'groups': {}, 'pages': {}}}


def _ids_from_tree(tree):
    groups, pages = set(), set()
    def walk(nodes):
        for node in nodes:
            if node['type'] == 'group':
                groups.add(node['id'])
                walk(node['children'])
            else:
                pages.add(node['page_id'])
    walk(tree)
    return groups, pages


def validate_research(value, *, tree=None):
    """Strict, lossless validation. Never silently discard malformed citations.

    Older projects have no research field at all, which is the only automatic
    migration. Existing orphan IDs can remain for in-session Undo, but are
    bounded. Unknown formats are rejected, not rewritten by an old app.
    """
    if value is None:
        return empty_research()
    if not isinstance(value, dict) or value.get('schema') != SCHEMA:
        raise ValueError('Unsupported research metadata schema; upgrade Pinbu Note.')
    if set(value) != set(empty_research()):
        raise ValueError('Unexpected research metadata fields; refusing a lossy save.')
    r = deepcopy(value)
    refs = r['references']
    if not isinstance(refs, dict) or len(refs) > 10000:
        raise ValueError('Too many or malformed bibliographic references.')
    for ident, ref in refs.items():
        if not SAFE_ID.fullmatch(ident) or not isinstance(ref, dict):
            raise ValueError('Invalid bibliographic record ID.')
        if set(ref) - REF_FIELDS or ref.get('type') not in SOURCE_TYPES:
            raise ValueError('Unsupported bibliographic fields or source type.')
        if not isinstance(ref.get('title'), str) or not 1 <= len(ref['title'].strip()) <= 1000:
            raise ValueError('Reference title is missing or too long.')
        for key, val in ref.items():
            if key in ('authors', 'editors'):
                if not isinstance(val, list) or len(val) > 64 or any(
                        not isinstance(name, str) or not 1 <= len(name.strip()) <= 200
                        for name in val):
                    raise ValueError(f'Invalid {key} in reference.')
            elif key != 'type' and key != 'parent_id' and (not isinstance(val, str) or len(val) > 4000):
                raise ValueError(f'Invalid {key} in reference.')
        if 'parent_id' in ref and (not SAFE_ID.fullmatch(str(ref['parent_id']))
                                   or ref['parent_id'] == ident):
            raise ValueError('Invalid parent reference.')
    for ident, ref in refs.items():
        seen = {ident}
        current = ref
        while current.get('parent_id'):
            parent_id = current['parent_id']
            if parent_id not in refs:
                raise ValueError('Linked parent book reference is missing.')
            if parent_id in seen:
                raise ValueError('Cyclic parent reference relationship.')
            seen.add(parent_id)
            current = refs[parent_id]
    def validate_assignments(block, *, tags=False):
        if not isinstance(block, dict) or set(block) != {'groups', 'pages'}:
            raise ValueError('Invalid research target assignments.')
        for kind in ('groups', 'pages'):
            part = block[kind]
            if not isinstance(part, dict) or len(part) > 20000:
                raise ValueError('Invalid research assignments.')
            for ident, target in part.items():
                if not valid_target(kind, ident):
                    raise ValueError('Invalid research target ID.')
                if tags:
                    if not isinstance(target, list) or len(target) > 100 or any(
                            not isinstance(tid, str) or tid not in r['tags']
                            for tid in target):
                        raise ValueError('Invalid tag assignment.')
                elif target is not None and target not in refs:
                    raise ValueError('Assignment refers to missing reference.')
    validate_assignments(r['reference_assignments'])
    tags = r['tags']
    if not isinstance(tags, dict) or len(tags) > 2000:
        raise ValueError('Invalid tag definitions.')
    for ident, tag in tags.items():
        if (not SAFE_ID.fullmatch(ident) or not isinstance(tag, dict)
            or set(tag) != {'name', 'colour'} or not isinstance(tag['name'], str)
            or not 1 <= len(tag['name'].strip()) <= 80
            or not isinstance(tag['colour'], str)
            or not HEX_COLOUR.fullmatch(tag['colour'])):
            raise ValueError('Invalid tag definition.')
    validate_assignments(r['tag_assignments'], tags=True)
    validate_assignments(r['tag_exclusions'], tags=True)
    numbering = r['numbering']
    if not isinstance(numbering, dict) or set(numbering) != {'groups', 'sources', 'pages'}:
        raise ValueError('Invalid printed-page numbering.')
    for kind in ('groups', 'sources', 'pages'):
        part = numbering[kind]
        if not isinstance(part, dict) or len(part) > 20000:
            raise ValueError('Invalid page numbering map.')
        for ident, value in part.items():
            if kind != 'sources' and not valid_target(kind, ident):
                raise ValueError('Invalid numbering target.')
            if kind == 'sources' and (not isinstance(ident, str) or
                                      not 1 <= len(ident) <= 4000 or '..' in ident.split('/')):
                raise ValueError('Unsafe numbering source key.')
            if kind == 'pages':
                if not isinstance(value, str) or not 1 <= len(value) <= 60:
                    raise ValueError('Invalid custom page label.')
            else:
                rules = value if kind == 'sources' else [value]
                if not isinstance(rules, list) or len(rules) > 100:
                    raise ValueError('Invalid numbering segments.')
                for rule in rules:
                    if (not isinstance(rule, dict) or set(rule) != {'start_pdf', 'start_label', 'scheme'}
                        or type(rule['start_pdf']) is not int or not 1 <= rule['start_pdf'] <= 20000
                        or type(rule['start_label']) is not int or not 1 <= rule['start_label'] <= 1000000
                        or rule['scheme'] not in ('arabic', 'roman-lower', 'roman-upper')):
                        raise ValueError('Invalid page-number offset rule.')
    # Tree membership is intentionally NOT a validation precondition: group
    # deletion can be undone and deleted pages may remain in history.
    return r


def new_reference(research, record):
    identifier = uuid4().hex
    candidate = deepcopy(research)
    candidate['references'][identifier] = deepcopy(record)
    validate_research(candidate)
    research.clear(); research.update(candidate)
    return identifier


def set_assignment(research, kind, identifier, ref_id):
    if kind not in ('groups', 'pages') or not valid_target(kind, identifier):
        raise ValueError('Cannot assign a reference to this item.')
    if ref_id is not None and ref_id not in research['references']:
        raise ValueError('Reference does not exist.')
    research['reference_assignments'][kind][identifier] = ref_id


def ancestors(tree, page_id):
    """Group IDs from outermost to innermost for one stable page ID."""
    def walk(nodes, stack):
        for node in nodes:
            if node['type'] == 'page' and node['page_id'] == page_id:
                return stack
            if node['type'] == 'group':
                found = walk(node['children'], stack + [node['id']])
                if found is not None:
                    return found
        return None
    return walk(tree, []) or []


def effective_reference(research, tree, page_id):
    refs = research['reference_assignments']
    if page_id in refs['pages']:
        return refs['pages'][page_id]
    for group in reversed(ancestors(tree, page_id)):
        if group in refs['groups']:
            return refs['groups'][group]
    return None


def effective_tags(research, tree, page_id):
    a = research['tag_assignments']
    masked = research['tag_exclusions']
    result = set()
    for group in ancestors(tree, page_id):
        result.difference_update(masked['groups'].get(group, []))
        result.update(a['groups'].get(group, []))
    result.difference_update(masked['pages'].get(page_id, []))
    result.update(a['pages'].get(page_id, []))
    return result


def set_tag(research, kind, identifier, tag_id, enabled):
    if kind not in ('groups', 'pages') or tag_id not in research['tags']:
        raise ValueError('Invalid tag target.')
    values = research['tag_assignments'][kind]
    exclusions = research['tag_exclusions'][kind]
    direct = set(values.get(identifier, []))
    masked = set(exclusions.get(identifier, []))
    if enabled:
        direct.add(tag_id)
        masked.discard(tag_id)
    else:
        direct.discard(tag_id)
        # Explicitly disabling a tag must mask an inherited parent tag.
        masked.add(tag_id)
    if direct:
        values[identifier] = sorted(direct)
    else:
        values.pop(identifier, None)
    if masked:
        exclusions[identifier] = sorted(masked)
    else:
        exclusions.pop(identifier, None)


def make_tag(research, name, colour='#c74879'):
    identifier = uuid4().hex
    research['tags'][identifier] = {'name': name.strip(), 'colour': colour}
    validate_research(research)
    return identifier


def roman(number):
    if not 1 <= number <= 3999:
        raise ValueError('Roman page number must be between 1 and 3999.')
    chunks = ((1000,'M'),(900,'CM'),(500,'D'),(400,'CD'),(100,'C'),(90,'XC'),
              (50,'L'),(40,'XL'),(10,'X'),(9,'IX'),(5,'V'),(4,'IV'),(1,'I'))
    result = ''
    for size, text in chunks:
        q, number = divmod(number, size)
        result += text * q
    return result


def page_source(page):
    return page.get('source') or page.get('render_source') or page.get('file') or ''


def effective_page_label(research, tree, page):
    """PDF page is default, source/group offsets only change the printed locator."""
    pid = page['id']
    manual = research['numbering']['pages'].get(pid)
    if manual is not None:
        return manual
    pdf_page = page.get('source_page') or 1
    n = research['numbering']
    rules = []
    source = page_source(page)
    if source:
        rules.extend(n['sources'].get(source, []))
    for gid in ancestors(tree, pid):
        if gid in n['groups']:
            rules.append(n['groups'][gid])
    applicable = [rule for rule in rules if pdf_page >= rule['start_pdf']]
    if not applicable:
        return str(pdf_page)
    rule = applicable[-1]  # closest group takes precedence over source rule
    number = rule['start_label'] + pdf_page - rule['start_pdf']
    if number < 1:
        return str(pdf_page)
    if rule['scheme'] == 'arabic':
        return str(number)
    if number > 3999:
        return str(pdf_page)
    result = roman(number)
    return result.lower() if rule['scheme'] == 'roman-lower' else result


def preserve_on_tree_change(research, before, after, pages):
    """Materialise ONLY changed effective values before moving/ungrouping.

    Copy-on-change means reordering unaffected pages doesn't duplicate refs.
    A moved page retains its old reference, tags and printed page label even
    if the destination group has a different parent. This modifies a COPY.
    """
    result = deepcopy(research)
    remaining = {x['page_id'] for x in _walk_pages(after)}
    for page in pages:
        pid = page['id']
        if pid not in remaining:
            continue
        old_ref = effective_reference(research, before, pid)
        new_ref = effective_reference(result, after, pid)
        if old_ref != new_ref:
            result['reference_assignments']['pages'][pid] = old_ref
        old_tags = effective_tags(research, before, pid)
        new_tags = effective_tags(result, after, pid)
        missing = old_tags - new_tags
        if missing:
            direct = set(result['tag_assignments']['pages'].get(pid, []))
            result['tag_assignments']['pages'][pid] = sorted(direct | missing)
            masks = set(result['tag_exclusions']['pages'].get(pid, [])) - missing
            if masks:
                result['tag_exclusions']['pages'][pid] = sorted(masks)
            else:
                result['tag_exclusions']['pages'].pop(pid, None)
        extra = new_tags - old_tags
        if extra:
            direct = set(result['tag_assignments']['pages'].get(pid, [])) - extra
            if direct:
                result['tag_assignments']['pages'][pid] = sorted(direct)
            else:
                result['tag_assignments']['pages'].pop(pid, None)
            masks = set(result['tag_exclusions']['pages'].get(pid, [])) | extra
            result['tag_exclusions']['pages'][pid] = sorted(masks)
        old_label = effective_page_label(research, before, page)
        new_label = effective_page_label(result, after, page)
        if old_label != new_label:
            result['numbering']['pages'][pid] = old_label
    return result


def _walk_pages(tree):
    for node in tree:
        if node['type'] == 'page':
            yield node
        elif node['type'] == 'group':
            yield from _walk_pages(node['children'])


@dataclass(frozen=True)
class Span:
    text: str
    italic: bool = False


def _authors(values, *, in_text=False, reverse=False):
    if not values:
        return ''
    names = [x.strip() for x in values]
    if in_text:
        names = [n.split(',', 1)[0].strip() for n in names]
    elif reverse:
        names = [((n.split(',',1)[1].strip() + ' ' + n.split(',',1)[0].strip())
                  if ',' in n else n) for n in names]
    if len(names) >= 4:
        return names[0] + ' et al.'
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return ' and '.join(names)
    return ', '.join(names[:-1]) + ' and ' + names[-1]


def _year(record):
    return record.get('year', '').strip() or 'no date'


def _title_source(record):
    return record.get('title', 'Untitled')


def render_reference(record, *, parent=None):
    """Generate typographic spans: no user HTML is trusted or persisted.

    First supported Cite Them Right Harvard 13 templates. Incomplete fields
    aren't fabricated; validate completeness separately in the UI.
    """
    kind = record['type']; title = _title_source(record)
    author = _authors(record.get('authors', [])) or record.get('organisation', '') or title
    if kind == 'book' and not record.get('authors') and record.get('editors'):
        editors=record['editors']
        author = _authors(editors) + (' (ed.)' if len(editors)==1 else ' (eds.)')
    year = _year(record) if record.get('year') or not parent else _year(parent)
    chunks = []
    def t(value):
        if value: chunks.append(Span(str(value)))
    def i(value):
        if value: chunks.append(Span(str(value), True))
    def finish(extra=''):
        if extra: t(extra)
        # normalize last period and whitespace without changing italics
        if chunks and not chunks[-1].text.rstrip().endswith('.'):
            t('.')
        return chunks
    if kind == 'book':
        t(f'{author} ({year}) '); i(title); t('.')
        edition=record.get('edition','').strip()
        if edition and edition.lower() not in ('1', '1st', 'first', 'first edition'):
            t(' ' + edition + ('' if 'ed' in edition.lower() else ' edn.') )
        if record.get('publisher'):t(' ' + record['publisher'].strip() + '.')
    elif kind == 'chapter':
        parent = parent or {}
        t(f'{author} ({year}) ‘{title}’, in ')
        editors=record.get('editors') or parent.get('editors') or []
        if editors:
            t(_authors(editors, reverse=True) + (' (ed.) ' if len(editors)==1 else ' (eds.) '))
        book=record.get('container_title') or parent.get('title','')
        i(book)
        t('.')
        publisher=record.get('publisher') or parent.get('publisher','')
        if publisher:t(' ' + publisher + '.')
        if record.get('pages'):t(' pp. ' + record['pages'].strip().replace('-', '–') + '.')
    elif kind == 'journal':
        t(f'{author} ({year}) ‘{title}’, ')
        i(record.get('container_title',''))
        if record.get('volume'):t(', ' + record['volume'].strip())
        if record.get('issue'):t('(' + record['issue'].strip() + ')')
        if record.get('pages'):t(', pp. ' + record['pages'].strip().replace('-', '–'))
        t('.')
    elif kind == 'website':
        t(f'{author} ({year}) '); i(title); t('.')
    elif kind in ('film', 'television', 'video'):
        i(title); t(f' ({year})')
        if kind == 'film' and record.get('director'):
            t('. Directed by ' + record['director'].strip())
        if record.get('publisher'):
            t('. ' + record['publisher'].strip())
        if record.get('medium') and not record.get('url'):
            t('. ' + record['medium'].strip())
        t('.')
    doi=record.get('doi','').strip()
    url=record.get('url','').strip()
    if doi or url:
        u=('https://doi.org/' + doi.removeprefix('https://doi.org/').removeprefix('doi:')) if doi else url
        t(' Available at: ' + u)
        if record.get('accessed') and not doi:t(' (Accessed: ' + record['accessed'].strip() + ')')
        t('.')
    elif record.get('platform'):
        t(' Available at: ' + record['platform'].strip())
        if record.get('accessed'):t(' (Accessed: ' + record['accessed'].strip() + ')')
        t('.')
    return finish()


def render_in_text(record, *, page=None, narrative=False):
    kind=record['type']
    name=(_title_source(record) if kind in ('film','television','video') else
          (_authors(record.get('authors', []), in_text=True)
           or record.get('organisation','')
           or _authors(record.get('editors', []), in_text=True)
           or _title_source(record)))
    year=_year(record)
    locator = (', pp. ' + page if '–' in page or '-' in page or ',' in page
               else ', p. ' + page) if page else ''
    if kind in ('film','television','video'):
        # italicise title in an in-text reference, too
        return ([Span('(')] if not narrative else []) + [Span(name, True)] + [Span(f', {year}{locator})' if not narrative else f' ({year}{locator})')]
    if narrative:
        return [Span(f'{name} ({year}{locator})')]
    return [Span(f'({name}, {year}{locator})')]


def to_plain(spans):
    return ''.join(p.text for p in spans)


def to_html(spans):
    """Safe rich-text clipboard HTML; don't trust imported bibliographic text."""
    return '<html><body><p>' + ''.join(
        f'<em>{escape(p.text)}</em>' if p.italic else escape(p.text)
        for p in spans) + '</p></body></html>'


def missing_required(record, *, parent=None):
    """Inform users what's incomplete. Never invent a publication detail."""
    kind=record['type']
    def present(key):
        if record.get(key):
            return True
        if key == 'container_title' and parent and parent.get('title'):
            return True
        if key == 'authors' and record.get('type') == 'book' and record.get('editors'):
            return True
        if key == 'authors' and record.get('organisation'):
            return True
        return bool(parent and parent.get(key))
    keys={'book':('authors','year','title','publisher'),
          'chapter':('authors','year','title','container_title','editors','publisher','pages'),
          'journal':('authors','year','title','container_title','volume'),
          'website':('year','title','url','accessed'),
          'film':('year','title','director'),
          'television':('year','title'),
          'video':('year','title','url')}.get(kind,('title',))
    return [key.replace('_',' ') for key in keys if not present(key)]
