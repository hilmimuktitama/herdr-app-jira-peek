import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const source = readFileSync(new URL('../../mods/jira-peek/main.js', import.meta.url), 'utf8');
const method = source.slice(source.indexOf('  async setupHelper('), source.indexOf('  newSetupInput('));
function helper(exec) {
  return new Function('exec', 'appHome', 'ROOT', `return ({${method}}).setupHelper`)(exec, () => '/fictional/app home', 'mods/jira-peek');
}

test('setup dispatch uses the bundled runtime and argument arrays', async () => {
  const calls = [];
  const run = helper(async (...args) => { calls.push(args); return { code: 0, stdout: '{"ok":true}' }; });
  const owner = { setupRoot: () => '/fictional/app home/data/jira-peek/connection' };
  for (const operation of ['inspect', 'prepare', 'save', 'cancel']) {
    await run.call(owner, operation, 'fictional-ticket-or-revision');
    assert.deepEqual(calls.at(-1), ['/fictional/app home/mods/jira-peek/runtime/jira-peek-bridge', ['setup', operation, owner.setupRoot(), 'fictional-ticket-or-revision']]);
  }
});

test('setup dispatch exposes only known errors', async () => {
  for (const [result, expected] of [
    [{code: 1, stdout: 'fictional diagnostic'}, 'setup_failed'],
    [{code: 0, stdout: 'not JSON'}, 'setup_failed'],
    [{code: 0, stdout: '{"ok":false,"error":"fictional private diagnostic"}'}, 'setup_failed'],
    [{code: 0, stdout: '{"ok":false,"error":"config_changed"}'}, 'config_changed'],
  ]) {
    await assert.rejects(helper(async () => result).call({setupRoot: () => '/fictional'}, 'save'), {message: expected});
  }
});
