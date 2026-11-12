// Entirely fictional deterministic interleavings. These cases are scored
// separately from the original passing suite; native paint still needs QA.
import test from 'node:test';
import assert from 'node:assert/strict';
import { harness, childText } from './view-harness.js';
import { harness as controller, config, turn } from './controller-harness.js';

const make = () => {
  const h = harness(false, true);
  h.view.demo = false; h.view.model.pinned = true; h.view.search(h.cx);
  return h;
};

test('HC-01 selected pin clicks retain intent while worker is dormant', async () => {
  // No Promise turns between clicks and native wake. A second activation of
  // the still-painted Pin must never be interpreted as Unpin on execution.
  const h = make();
  try {
    const key = h.view.model.current.selected;
    for (const desired of [true, false, true]) {
      h.host.virtualStart = 2; h.host.virtualCount = 3; h.render();
      h.host.virtualStart = 0;
      h.view.selectedRow.release(); h.view.pinnedSelectedRow.release();
      const pin = h.render().get('quick-pin').events.on_change;
      pin(desired, h.cx); pin(desired, h.cx);
      h.view.rowWakeTimer.fire();
      assert.equal(h.view.model.current.pinnedIssueKey, desired ? key : null,
        'queued activations must preserve Pin/Unpin intent');
      h.view.drainRowActions(h.cx); h.view.rowWakeTimer.fire();
      assert.equal(h.view.model.current.pinnedIssueKey, desired ? key : null);
    }
  } finally { await h.view.close(h.cx); }
});

test('HC-02 queued selected actions reject obsolete lifetimes', async () => {
  for (const rowKey of [undefined, 'DEMO-1042']) for (const boundary of ['filter', 'clear', 'reconnect', 'source', 'auxiliary', 'auxiliary-roundtrip', 'help-roundtrip']) {
    const h = make();
    try {
      const context = h.view.issueContext();
      h.view.rowActions.push({action:'copy-key',context,rowKey}, {action:'pin',context,rowKey});
      if (boundary === 'filter') h.view.input.edit('no fictional matches');
      if (boundary === 'clear') h.view.model.clearList();
      if (boundary === 'reconnect') h.view.invalidate(h.cx);
      if (boundary === 'source') {
        h.view.model.useSource('fictional-second'); h.view.model.merge([context.key]);
        h.view.model.useSource('t-demo');
      }
      if (boundary.startsWith('auxiliary')) h.view.openOptions(h.cx);
      if (boundary === 'auxiliary-roundtrip') h.view.closeOptions(h.cx);
      if (boundary === 'help-roundtrip') { h.view.openHelp(h.cx); h.view.closeHelp(h.cx); }
      h.view.rowWakeTimer.fire(); h.view.drainRowActions(h.cx);
      assert.deepEqual(h.host.clipboard, [], boundary);
      assert.equal(h.view.model.current?.pinnedIssueKey ?? null, null, boundary);
      assert.ok(h.view.note, boundary + ' supplies rejection feedback');
    } finally { await h.view.close(h.cx); }
  }
});

test('HC-03 A B A cached rows align painted description and action targets after retirement', async () => {
  const h = make();
  try {
    const a = 'DEMO-1042', b = 'DEMO-1038';
    for (const key of [a,b,a]) {
      h.view.selectedRow.release(); h.view.pinnedSelectedRow.release();
      h.view.select(key, h.cx, false, false);
      const frame = h.render(), issue = h.view.model.details.get(key);
      assert.ok(childText(frame.get('jira-selected-result')).includes(key));
      assert.ok(childText(frame.get('jira-selected-result')).includes(issue.summary));
      assert.ok(childText(frame.get('jira-selected-result')).includes(issue.status));
      assert.ok(h.host.textViews.some(v => v.properties.textViewText.includes(issue.description)));
      frame.get('quick-copy-key').events.on_click({},h.cx); h.view.rowWakeTimer.fire();
      assert.equal(h.host.clipboard.at(-1),key);
      h.render().get('open').events.on_click({},h.cx); h.view.rowWakeTimer.fire();
      assert.equal(h.host.urls.at(-1),`https://jira.example.test/browse/${key}`);
      let target; h.view.refresh = () => { target=h.view.issueActionKey(); };
      h.render().get('quick-refresh').events.on_click({},h.cx); h.view.rowWakeTimer.fire();
      assert.equal(target,key);
    }
    h.view.toggleIssuePin(h.cx); const pin=h.view.model.current.pinnedIssueKey;
    h.view.hide(h.cx); h.view.search(h.cx);
    assert.equal(h.view.model.current.pinnedIssueKey,pin);
  } finally { await h.view.close(h.cx); }
});

test('HC-04 delayed detail metadata comments cannot contaminate rapid A B A', async t => {
  t.mock.method(Date, 'now', () => 100000);
  const {view,state,cx}=controller(); view.now=()=>100000;
  view.model.merge(['ABC-1','ABC-2']);
  view.model.accept({key:'ABC-1',summary:'Fictional orchard',status:'Ready',description:'Orchard body',commentsDeferred:true});
  view.loadComments(cx); const comments=state.requests[0];
  view.pump(cx); const metadata=state.requests[1];
  assert.equal(metadata.args[0],'metadata');
  view.select('ABC-2',cx,false); const detail=state.requests[2];
  view.select('ABC-1',cx,false);
  detail.resolve({ok:true,context:config.context,issue:{key:'ABC-2',summary:'Fictional harbor',description:'Harbor body'}}); await turn();
  metadata.resolve({ok:true,context:config.context,rows:[{key:'ABC-2',summary:'Obsolete harbor'}]}); await turn();
  comments.resolve({ok:true,context:config.context,comments:{key:'ABC-1',comments:[{body:'Orchard comment'}],commentsTotal:1}}); await turn();
  assert.equal(view.issueActionKey(),'ABC-1');
  assert.equal(view.model.details.get('ABC-1').description,'Orchard body');
  assert.equal(view.model.metadata.get('ABC-2').summary,'Fictional harbor');
  assert.equal(view.model.details.get('ABC-1').comments[0].body,'Orchard comment');
  view.copyIssue(false,cx); assert.equal(state.clipboard.at(-1),'ABC-1');
  assert.ok(state.requests.length===3,'no duplicate reads');
});

test('HC-05 failed refresh retains body fetch time and explicit recovery', async t => {
  t.mock.method(Date, 'now', () => 100000);
  const {view,state,cx}=controller(); view.now=()=>100000;
  view.model.merge(['ABC-1']); view.pump(cx);
  state.requests[0].resolve({ok:true,context:config.context,issue:{key:'ABC-1',summary:'Fictional orchard',description:'Retained orchard',fetchedAt:1000}}); await turn();
  view.refresh(cx);
  state.requests[1].resolve({ok:false,error:'request_failed'}); await turn();
  assert.equal(view.model.details.get('ABC-1').description,'Retained orchard');
  assert.equal(view.model.details.get('ABC-1').fetchedAt,1000);
  assert.match(view.note,/retry/i);
  view.refresh(cx);
  assert.equal(state.requests[2].args.at(-1),'refresh');
  state.requests[2].resolve({ok:true,context:config.context,issue:{key:'ABC-1',summary:'Fictional orchard',description:'Recovered orchard',fetchedAt:2000}}); await turn();
  assert.equal(view.model.details.get('ABC-1').description,'Recovered orchard');
  assert.equal(view.model.details.get('ABC-1').fetchedAt,2000);
  assert.equal(view.model.failures.has('ABC-1'),false); assert.equal(view.note,'');
});

test('HC-06 cumulative row churn exceeds 10000 with bounded live actions', async () => {
  const h=make();
  try {
    h.view.model.merge(Array.from({length:200},(_,i)=>`DEMO-${6000+i}`));
    h.host.virtualCount=6; const keys=h.view.model.rows();
    for(let i=0;i<1800;i++) {
      h.host.virtualStart=(i*7)%190;
      h.view.select(keys[i%keys.length],h.cx,false,false);
      if(i%9===0) for(const row of h.host.nestedViews) row.release();
      h.render(); h.view.rowWakeTimer.fire();
      assert.ok(h.view.resultActionRows.size<=7);
      assert.ok(h.host.nestedViews.filter(row=>!row.released).length<=9);
    }
    assert.ok(h.host.nestedViews.length>10000);
    h.view.issuesExpanded=false; h.render();
    assert.equal(h.view.resultActionRows.size,0);
  } finally { await h.view.close(h.cx); }
});
