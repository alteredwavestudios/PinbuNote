"""v0.9.2b: navigator numbers and reference origins are READ-ONLY projections.

No Qt is needed: the same projection backs both Qt navigator widgets.
"""
import copy
import json
from uuid import uuid4

from yomunote.navigator_research_display import (
    MODES, DEFAULT_MODES, next_mode, build_display_rows,
)
from yomunote.page_groups import page_node, group_node
from yomunote.research import empty_research, new_reference, set_assignment, make_tag, set_tag


def fixture():
    ids = [uuid4().hex for _ in range(4)]
    pages = [{'id': i, 'title': f'Page {index+1}', 'kind': 'pdf',
              'source_page': index+7, 'source': 'originals/book.pdf'}
             for index, i in enumerate(ids)]
    chapter = group_node('Chapter 1', [page_node(ids[0]), page_node(ids[1]), page_node(ids[2])])
    other = group_node('Chapter 2', [page_node(ids[3])])
    return empty_research(), [chapter, other], pages, ids, chapter['id'], other['id']


def test_no_research_starts_at_tree_order_and_preserves_pdf_number():
    research, tree, pages, ids, _, _ = fixture()
    before = json.dumps(research, sort_keys=True)
    rows = build_display_rows(research, tree, pages)
    assert [rows[i]['number'] for i in ids] == ['1', '2', '3', '1']
    assert rows[ids[0]]['available_modes'] == ('source', 'tree')
    assert rows[ids[0]]['source_number'] == 7
    assert rows[ids[0]]['reference_id'] is None
    assert rows[ids[0]]['origin'] == 'none'
    assert 'Bibliographic reference' not in rows[ids[0]]['tooltip']
    assert json.dumps(research, sort_keys=True) == before


def test_group_book_ref_makes_printed_preferred_and_inherited():
    research, tree, pages, ids, gid, _ = fixture()
    rid = new_reference(research, {'type':'book', 'title':'The Study',
        'authors':['Davis, S.'], 'year':'2021', 'publisher':'Acme'})
    set_assignment(research, 'groups', gid, rid)
    rows = build_display_rows(research, tree, pages)
    assert rows[ids[0]]['number'] == '7'
    assert rows[ids[0]]['origin'] == 'group'
    assert rows[ids[0]]['direct'] is False
    assert rows[ids[0]]['reference_summary'] == 'Davis (2021)'
    assert rows[ids[1]]['available_modes'] == ('printed', 'source', 'tree')
    assert rows[ids[3]]['number'] == '1'


def test_page_override_and_explicit_no_reference_differ():
    research, tree, pages, ids, gid, _ = fixture()
    one = new_reference(research, {'type': 'book', 'title': 'The Book'})
    two = new_reference(research, {'type': 'book', 'title': 'The Exception'})
    set_assignment(research, 'groups', gid, one)
    set_assignment(research, 'pages', ids[1], two)
    set_assignment(research, 'pages', ids[2], None)
    rows = build_display_rows(research, tree, pages)
    assert rows[ids[1]]['reference_id'] == two
    assert rows[ids[1]]['direct'] is True
    assert rows[ids[2]]['reference_id'] is None
    assert rows[ids[2]]['number'] == '3'
    assert rows[ids[0]]['direct'] is False


def test_roman_group_offset_manual_override_and_pagination_are_independent():
    research, tree, pages, ids, gid, _ = fixture()
    research['numbering']['groups'][gid] = {
        'start_pdf': 7, 'start_label': 1, 'scheme': 'roman-lower'}
    research['numbering']['pages'][ids[1]] = 'A-7'
    rows = build_display_rows(research, tree, pages)
    assert [rows[i]['number'] for i in ids] == ['i', 'A-7', 'iii', '1']
    assert rows[ids[1]]['tree_number'] == 2
    assert rows[ids[1]]['source_number'] == 8
    assert rows[ids[1]]['printed_number'] == 'A-7'
    overridden = build_display_rows(research, tree, pages, overrides={ids[1]: 'tree'})
    assert overridden[ids[1]]['number'] == '2'
    assert research['numbering']['pages'][ids[1]] == 'A-7'


def test_source_rule_no_ref_still_has_bibliographical_number():
    research, tree, pages, ids, gid, _ = fixture()
    research['numbering']['sources']['originals/book.pdf'] = [
        {'start_pdf': 7, 'start_label': 101, 'scheme':'arabic'}]
    rows = build_display_rows(research, tree, pages)
    assert rows[ids[0]]['number'] == '101'
    assert rows[ids[1]]['number'] == '102'


def test_nearest_group_reference_and_group_numbering_priority():
    research, tree, pages, ids, root, _ = fixture()
    child = group_node('Subchapter', [page_node(ids[0])])
    tree[0]['children'] = [child, page_node(ids[1]), page_node(ids[2])]
    a = new_reference(research, {'type':'book', 'title':'Outer'})
    b = new_reference(research, {'type':'chapter', 'title':'Inner'})
    set_assignment(research, 'groups', root, a)
    set_assignment(research, 'groups', child['id'], b)
    research['numbering']['groups'][root] = {
        'start_pdf':7, 'start_label':1, 'scheme':'arabic'}
    research['numbering']['groups'][child['id']] = {
        'start_pdf':7, 'start_label':70, 'scheme':'arabic'}
    rows = build_display_rows(research, tree, pages)
    assert rows[ids[0]]['number'] == '70'
    assert rows[ids[0]]['reference_id'] == b
    assert rows[ids[0]]['origin_name'] == 'Subchapter'
    assert rows[ids[1]]['number'] == '2'
    assert rows[ids[1]]['reference_id'] == a
    assert rows[ids[1]]['tree_number'] == 1


def test_cycle_skips_missing_and_respects_modes():
    assert next_mode('printed', ('printed', 'source', 'tree')) == 'source'
    assert next_mode('source', ('printed', 'source', 'tree')) == 'tree'
    assert next_mode('tree', ('printed', 'source', 'tree')) == 'printed'
    assert next_mode('tree', ('source', 'tree')) == 'source'
    assert next_mode('source', ('source', 'tree')) == 'tree'
    assert next_mode('tree', ('tree',)) == 'tree'
    assert next_mode('nonexistent', ('source', 'tree')) == 'source'


def test_hover_full_is_html_escaped_and_has_italics():
    research, tree, pages, ids, gid, _ = fixture()
    rid = new_reference(research, {'type':'book', 'title':'<Study> & Methods',
        'authors':['S. James'], 'year':'2022', 'publisher':'Oxford'})
    set_assignment(research,'groups',gid,rid)
    rows = build_display_rows(research,tree,pages,hover='full')
    assert '&lt;Study&gt; &amp; Methods' in rows[ids[0]]['tooltip']
    assert '<i>&lt;Study&gt; &amp; Methods</i>' in rows[ids[0]]['tooltip']
    assert '<Study>' not in rows[ids[0]]['tooltip']
    simple = build_display_rows(research,tree,pages,hover='simple')
    assert '<i>' not in simple[ids[0]]['tooltip']


def test_tags_summary_and_hidden_number_do_not_modify_source():
    research, tree, pages, ids, gid, _ = fixture()
    t = make_tag(research, 'Essay evidence')
    set_tag(research, 'groups', gid, t, True)
    saved = copy.deepcopy(research)
    rows = build_display_rows(research,tree,pages,secondary='tags',default='off')
    assert rows[ids[0]]['number'] == ''
    assert rows[ids[0]]['secondary'] == 'Essay evidence'
    assert research == saved


def test_partial_missing_source_and_slide_kind():
    research, tree, pages, ids, _, _ = fixture()
    pages[0]['source'] = 'originals/Lecture.pptx'
    pages[1].pop('source_page')
    rows = build_display_rows(research,tree,pages)
    assert rows[ids[0]]['source_kind'] == 'Slide'
    assert rows[ids[1]]['available_modes'] == ('tree',)
    assert rows[ids[1]]['number'] == '2'


def test_display_preference_invalid_values_fallback_to_safe_defaults():
    research, tree, pages, ids, _, _ = fixture()
    rows = build_display_rows(research,tree,pages,default='nonexistent',
                              secondary='bad',hover='bad',overrides={ids[0]:'foo'})
    assert rows[ids[0]]['number'] == '1'
    assert rows[ids[0]]['number_mode'] == 'tree'
    assert 'Page 1' in rows[ids[0]]['tooltip']


def test_no_extra_sqlite_tables_or_project_fields_are_needed():
    from yomunote.notebook import NOTEBOOK_VERSION
    from yomunote.project import FORMAT_VERSION
    assert NOTEBOOK_VERSION == 7
    assert FORMAT_VERSION == 5
    assert 'number_mode' not in empty_research()
    assert 'display_rows' not in empty_research()
