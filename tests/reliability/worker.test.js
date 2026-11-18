// The Promise row worker is dormant in scenarios.test.js. This file exercises
// the live worker wake and drain path without a synchronous spin.
import test from 'node:test';
import assert from 'node:assert/strict';
import { harness } from './view-harness.js';

const make = () => {
  const h = harness(false, true);
  h.view.demo = false; h.view.model.pinned = true; h.view.search(h.cx);
  return h;
};

test('HC-09 the worker drains a queued action after its wake', async () => {
  const h = make();
  try {
    const key = h.view.model.current.selected;
    h.view.queueRowAction('copy-key', h.view.issueContext());
    await new Promise(resolve => setImmediate(resolve));
    await new Promise(resolve => setImmediate(resolve));
    assert.deepEqual(h.host.clipboard, [key], 'the worker executed the queued copy');
    assert.equal(h.view.rowActions.length, 0, 'the worker drained the queue');
  } finally { await h.view.close(h.cx); }
});
