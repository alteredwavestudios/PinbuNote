"""Pinbu v0.9.2a research structure + Cite Them Right first templates.

Tests deliberately avoid Qt: SafeSave must protect research metadata even
when the UI process crashes or is not installed on the test machine.
"""
from copy import deepcopy
import json
import sqlite3
from pathlib import Path
import uuid
import pytest

from yomunote.notebook import Notebook, NOTEBOOK_VERSION
from yomunote.project import Project, FORMAT_VERSION
from yomunote.page_groups import group_node, page_node, ungroup, move_pages_to_root
from yomunote.research import (
    empty_research, validate_research, new_reference, set_assignment, make_tag,
    set_tag, effective_reference, effective_tags, effective_page_label,
    preserve_on_tree_change, render_reference, render_in_text, to_plain,
    to_html, missing_required, roman,
)


def ident(): return uuid.uuid4().hex


def two_page_project(tmp_path):
    p = Project.create(tmp_path, 'Research')
    a, b = ident(), ident()
    p.pages = [{'id':a,'title':'A','kind':'blank','source_page':7},
               {'id':b,'title':'B','kind':'blank','source_page':8}]
    book = group_node('Book', [page_node(a),page_node(b)])
    p.page_groups = [book]
    p.save()
    return p, book['id'], a, b


def test_default_research_is_empty_and_no_bibliography_is_fabricated(tmp_path):
    p=Project.create(tmp_path,'Empty')
    assert p.research == empty_research()
    assert validate_research(None) == empty_research()
    assert p.save() is None
    assert Project.load(p.path).research == empty_research()


def test_single_book_reference_is_shared_across_group_pages(tmp_path):
    p,g,a,b=two_page_project(tmp_path)
    r=new_reference(p.research,{'type':'book','title':'Leviathan','year':'1651',
                                'authors':['Hobbes, T.'],'publisher':'Andrew Crooke'})
    set_assignment(p.research,'groups',g,r)
    assert effective_reference(p.research,p.page_groups,a)==r
    assert effective_reference(p.research,p.page_groups,b)==r
    assert p.research['reference_assignments']['pages']=={}
    p.save(); loaded=Project.load(p.path)
    assert loaded.research==p.research
    assert len(loaded.research['references'])==1


def test_page_override_and_explicitly_no_reference(tmp_path):
    p,g,a,b=two_page_project(tmp_path)
    r=new_reference(p.research,{'type':'book','title':'Original'})
    r2=new_reference(p.research,{'type':'book','title':'Different'})
    set_assignment(p.research,'groups',g,r)
    set_assignment(p.research,'pages',a,r2)
    set_assignment(p.research,'pages',b,None)
    assert effective_reference(p.research,p.page_groups,a)==r2
    assert effective_reference(p.research,p.page_groups,b) is None
    p.save(); loaded=Project.load(p.path)
    assert loaded.research['reference_assignments']['pages'][b] is None


def test_ungroup_preserves_reference_tags_and_printed_locator(tmp_path):
    p,g,a,b=two_page_project(tmp_path)
    r=new_reference(p.research,{'type':'book','title':'Leviathan'})
    set_assignment(p.research,'groups',g,r)
    tag=make_tag(p.research,'Essay evidence')
    set_tag(p.research,'groups',g,tag,True)
    p.research['numbering']['groups'][g]={'start_pdf':7,'start_label':1,'scheme':'arabic'}
    new_tree=ungroup(p.page_groups,g)
    changed=preserve_on_tree_change(p.research,p.page_groups,new_tree,p.pages)
    assert effective_reference(changed,new_tree,a)==r
    assert effective_reference(changed,new_tree,b)==r
    assert tag in effective_tags(changed,new_tree,a)
    assert tag in effective_tags(changed,new_tree,b)
    assert effective_page_label(changed,new_tree,p.pages[0])=='1'
    assert effective_page_label(changed,new_tree,p.pages[1])=='2'
    assert g not in {n['id'] for n in new_tree if n['type']=='group'}


def test_move_preserves_original_ref_and_only_materialises_when_needed(tmp_path):
    p,g,a,b=two_page_project(tmp_path)
    another=group_node('Other',[])
    p.page_groups.append(another)
    r=new_reference(p.research,{'type':'book','title':'Source'})
    other=new_reference(p.research,{'type':'book','title':'Destination'})
    set_assignment(p.research,'groups',g,r)
    set_assignment(p.research,'groups',another['id'],other)
    tree=move_pages_to_root(p.page_groups,[a])
    changed=preserve_on_tree_change(p.research,p.page_groups,tree,p.pages)
    assert changed['reference_assignments']['pages'][a]==r
    assert a not in p.research['reference_assignments']['pages']
    assert b not in changed['reference_assignments']['pages']


def test_numbering_pdf_default_group_offset_and_roman(tmp_path):
    p,g,a,b=two_page_project(tmp_path)
    assert effective_page_label(p.research,p.page_groups,p.pages[0])=='7'
    p.research['numbering']['groups'][g]={'start_pdf':7,'start_label':1,'scheme':'roman-lower'}
    assert effective_page_label(p.research,p.page_groups,p.pages[0])=='i'
    assert effective_page_label(p.research,p.page_groups,p.pages[1])=='ii'
    p.research['numbering']['pages'][a]='A-3'
    assert effective_page_label(p.research,p.page_groups,p.pages[0])=='A-3'
    assert roman(4)=='IV' and roman(3999)=='MMMCMXCIX'
    p.save()
    assert Project.load(p.path).research==p.research


def test_tag_dedup_and_effective_group_page_union(tmp_path):
    p,g,a,b=two_page_project(tmp_path)
    x=make_tag(p.research,'Important','#AA3355')
    y=make_tag(p.research,'Essay evidence','#334455')
    set_tag(p.research,'groups',g,x,True)
    set_tag(p.research,'pages',a,y,True)
    set_tag(p.research,'pages',a,y,True)
    assert effective_tags(p.research,p.page_groups,a)=={x,y}
    assert effective_tags(p.research,p.page_groups,b)=={x}
    assert len(p.research['tag_assignments']['pages'][a])==1



def test_inherited_tag_can_be_masked_and_move_does_not_add_destination_tags(tmp_path):
    p,g,a,b=two_page_project(tmp_path)
    t1=make_tag(p.research,'A')
    t2=make_tag(p.research,'B')
    set_tag(p.research,'groups',g,t1,True)
    set_tag(p.research,'pages',a,t1,False)
    assert t1 not in effective_tags(p.research,p.page_groups,a)
    assert t1 in effective_tags(p.research,p.page_groups,b)
    other=group_node('Destination',[])
    p.page_groups.append(other)
    set_tag(p.research,'groups',other['id'],t2,True)
    from yomunote.page_groups import move_pages_to_group
    destination=move_pages_to_group(p.page_groups,[b],other['id'])
    changed=preserve_on_tree_change(p.research,p.page_groups,destination,p.pages)
    assert effective_tags(changed,destination,b)=={t1}
    p.research=changed
    p.page_groups=destination
    p.save()
    assert Project.load(p.path).research==p.research

def test_formatting_book_chapter_article_with_rich_italics():
    book={'type':'book','title':'Leviathan','year':'1651','authors':['Hobbes, T.'],
          'publisher':'Andrew Crooke'}
    spans=render_reference(book)
    assert to_plain(spans)=='Hobbes, T. (1651) Leviathan. Andrew Crooke.'
    assert '<em>Leviathan</em>' in to_html(spans)
    chapter={'type':'chapter','title':'Labour and power','year':'2020',
             'authors':['Smith, A.'],'editors':['Jones, B.'],
             'container_title':'Critical sociology','publisher':'Routledge','pages':'40-68'}
    result=to_html(render_reference(chapter))
    assert '‘Labour and power’' in result
    assert '<em>Critical sociology</em>' in result
    assert 'pp. 40–68' in result
    article={'type':'journal','title':'Work and value','year':'2023',
             'authors':['Allen, A.'],'container_title':'Sociology Review',
             'volume':'14','issue':'2','pages':'4-12','doi':'10.1000/sample'}
    rendered=to_html(render_reference(article))
    assert '<em>Sociology Review</em>' in rendered
    assert 'https://doi.org/10.1000/sample' in rendered


def test_formatting_web_and_film_citations_and_sanitised_html():
    web={'type':'website','title':'Research & <Privacy>', 'year':'2024',
         'authors':['Library, A.'],'url':'https://example.org',
         'accessed':'14 November 2026'}
    out=to_html(render_reference(web))
    assert '<em>Research &amp; &lt;Privacy&gt;</em>' in out
    assert 'Accessed: 14 November 2026' in out
    assert '<Privacy>' not in out
    film={'type':'film','title':'Xala','year':'1975','director':'O. Sembène',
          'medium':'DVD'}
    result=render_reference(film)
    assert '<em>Xala</em>' in to_html(result)
    assert 'Directed by O. Sembène' in to_plain(result)
    assert '<em>Xala</em>' in to_html(render_in_text(film))
    assert '(Hobbes, 1651, p. 137)'==to_plain(render_in_text({
        'type':'book','authors':['Hobbes, T.'],'year':'1651','title':'Leviathan'},page='137'))
    assert 'pp. 137–139' in to_plain(render_in_text({
        'type':'book','authors':['Hobbes, T.'],'year':'1651','title':'Leviathan'},page='137–139'))


def test_chapter_can_inherit_edited_book_metadata():
    parent={'type':'book','title':'Social theory reader','year':'2020',
            'publisher':'Sage','editors':['Jones, B.']}
    chapter={'type':'chapter','title':'Power','year':'2020','authors':['Hill, A.'],
             'pages':'17–45'}
    rendered=to_html(render_reference(chapter,parent=parent))
    assert 'B. Jones (ed.)' in rendered
    assert '<em>Social theory reader</em>' in rendered
    assert 'Sage' in rendered
    assert not missing_required(chapter,parent=parent)


def test_reject_corrupt_unknown_future_research_without_erasing_notes(tmp_path):
    p,g,a,b=two_page_project(tmp_path)
    p.notes_html='<p>KEEP MY ESSAY</p>'
    p.save()
    path=p.path/'project.json'
    data=json.loads(path.read_text())
    data['research']={'schema':99,'references':{}}
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='schema'):
        Project.load(p.path)
    assert 'KEEP MY ESSAY' in path.read_text()


def test_sqlite_save_reopen_and_tab_share_retain_research(tmp_path):
    notebook=Notebook.create(tmp_path,'University Research')
    page=ident()
    project=notebook.project(notebook.active_id)
    project.pages=[{'id':page,'title':'Page one','kind':'blank','source_page':7}]
    project.page_groups=[page_node(page)]
    ref=new_reference(project.research,{'type':'book','title':'Leviathan','year':'1651',
        'authors':['Hobbes, T.'],'publisher':'Andrew Crooke'})
    set_assignment(project.research,'pages',page,ref)
    project.research['numbering']['pages'][page]='1'
    project.notes_html='<p>Keep my footnotes</p>'
    project.save();notebook.save();location=notebook.path
    with sqlite3.connect(location) as conn:
        manifest=json.loads(conn.execute("SELECT value FROM meta WHERE key='manifest'").fetchone()[0])
        assert manifest['version']==NOTEBOOK_VERSION==7
    notebook.close()
    reopened=Notebook.load(location)
    try:
        loaded=reopened.project(reopened.active_id)
        assert loaded.research['references'][ref]['title']=='Leviathan'
        assert loaded.research['numbering']['pages'][page]=='1'
        assert '<p>Keep my footnotes</p>' in loaded.notes_html
        assert FORMAT_VERSION==5
    finally: reopened.close()


def test_cross_tab_move_materialises_effective_metadata_and_undo(tmp_path):
    notebook=Notebook.create(tmp_path,'Transferring Research')
    source_id=notebook.active_id
    target_id=notebook.add_tab('Other tab')
    source=notebook.project(source_id)
    page=ident()
    source.pages=[{'id':page,'title':'Reading','kind':'blank','source_page':7}]
    group=group_node('Book',[page_node(page)])
    source.page_groups=[group]
    ref=new_reference(source.research,{'type':'book','title':'The Book'})
    set_assignment(source.research,'groups',group['id'],ref)
    tag=make_tag(source.research,'Evidence')
    set_tag(source.research,'groups',group['id'],tag,True)
    source.research['numbering']['groups'][group['id']]={
        'start_pdf':7,'start_label':1,'scheme':'arabic'}
    source.save();notebook.save()
    count, change=notebook.transfer_pages(source_id,target_id,[page],move=True,return_change=True)
    assert count==1
    transferred=notebook.project(target_id)
    newpage=transferred.pages[0]
    assert effective_reference(transferred.research,transferred.page_groups,newpage['id'])==ref
    assert effective_page_label(transferred.research,transferred.page_groups,newpage)=='1'
    assert tag in effective_tags(transferred.research,transferred.page_groups,newpage['id'])
    notebook.replay_page_transfer(change,undo=True)
    restored=notebook.project(source_id)
    assert effective_reference(restored.research,restored.page_groups,page)==ref
    notebook.close()


def test_second_backup_restore_keeps_research_and_note_text(tmp_path):
    from yomunote.safe_backup import restore_snapshot
    from yomunote.backup_health import inspect_store, verify_history
    path=tmp_path/'source'
    nb=Notebook.create(path,'Safe Research',extension='.pinbunote')
    original=nb.path
    nb.close()
    session=Notebook.open_session(original,tmp_path/'working')
    try:
        project=session.project(session.active_id)
        project.pages=[{'id':ident(),'title':'Book page','kind':'blank','source_page':9}]
        project.page_groups=[page_node(project.pages[0]['id'])]
        rid=new_reference(project.research,{'type':'book','title':'Protected Reference',
            'year':'2026','authors':['O’Reilly, N.'],'publisher':'Research Press'})
        set_assignment(project.research,'pages',project.pages[0]['id'],rid)
        project.notes_html='<p>NEVER LOSE THIS TEXT</p>'
        project.save()
        backup_path=tmp_path/'second drive'
        snapshot=session.safesave_backup(backup_path,force=True,reason='test')
        assert snapshot and snapshot.is_file()
        status=inspect_store(backup_path,session.identifier,session.name,session.display_path)
        assert verify_history(Path(status.marker))==(1,1)
        output=tmp_path/'Restored copy.pinbunote'
        restore_snapshot(Path(status.marker),output)
        restored=Notebook.load(output)
        try:
            saved=restored.project(restored.active_id)
            assert saved.research['references'][rid]['title']=='Protected Reference'
            assert 'NEVER LOSE THIS TEXT' in saved.notes_html
        finally:restored.close()
    finally:session.close()


def test_webpage_uses_organisation_in_text():
    record={'type':'website','title':'Public report','year':'2025',
        'organisation':'National Archives','url':'https://example.org'}
    assert to_plain(render_in_text(record))=='(National Archives, 2025)'


def test_parent_citation_cycles_rejected_without_mutation():
    store=empty_research()
    a=new_reference(store,{'type':'book','title':'A'})
    b=new_reference(store,{'type':'book','title':'B','parent_id':a})
    before=deepcopy(store)
    store['references'][a]['parent_id']=b
    with pytest.raises(ValueError,match='Cyclic'):
        validate_research(store)
    assert before['references'][a].get('parent_id') is None


def test_older_notebook_page_ids_need_not_be_uuid(tmp_path):
    p=Project.create(tmp_path,'Legacy page ids')
    p.pages=[{'id':'first','title':'Old Page','kind':'blank','source_page':42}]
    p.page_groups=[page_node('first')]
    ref=new_reference(p.research,{'type':'book','title':'Legacy Work'})
    set_assignment(p.research,'pages','first',ref)
    tag=make_tag(p.research,'Legacy tag')
    set_tag(p.research,'pages','first',tag,True)
    p.research['numbering']['pages']['first']='39'
    p.save()
    out=Project.load(p.path)
    assert effective_reference(out.research,out.page_groups,'first')==ref
    assert effective_page_label(out.research,out.page_groups,out.pages[0])=='39'
    assert effective_tags(out.research,out.page_groups,'first')=={tag}
