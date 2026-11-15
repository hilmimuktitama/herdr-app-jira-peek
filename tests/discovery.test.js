import test from "node:test";
import assert from "node:assert/strict";
import { DiscoveryModel } from "../mods/jira-peek/model.js";
const config = {context:"fictional",base:"https://jira.example.test",projects:["ABC"],ttl:0,limit:20};
const row = n => ({key:`ABC-${n}`,summary:`Fictional orchard ${n}`,status:"Open"});
const page = (rows, next = "") => ({rows,nextPageToken:next,isLast:!next});

test("discovery is separate from terminal sessions and typing is not submitting", () => {
 const m = new DiscoveryModel(config,"text"); m.draft="orchard";
 assert.equal(m.source,null); assert.equal(m.submitted,""); assert.equal(m.status,"idle");
 const t=m.begin(); assert.equal(t.query,"orchard"); assert.equal(m.toggleIssuePin("ABC-1"),false);
});
test("new query, cancellation and failed newer attempts retire pages", () => {
 const m=new DiscoveryModel(config,"text"); m.draft="old"; const old=m.begin();
 m.draft="new"; const newer=m.begin(); m.status="request_failed";
 assert.equal(m.acceptPage(old,page([row(1)])),false);
 m.cancel(); assert.equal(m.acceptPage(newer,page([row(2)])),false);
 assert.deepEqual(m.current.keys,[]);
});
test("pagination deduplicates stable order and caps retention at 200", () => {
 const m=new DiscoveryModel(config,"mine"); let t=m.begin();
 for(let p=0;p<5;p++) {
  m.acceptPage(t,page(Array.from({length:50},(_,i)=>row(p*49+i)),`page-${p}`));
  if(p<4) t=m.begin(true);
 }
 assert.equal(m.current.keys.length,200); assert.equal(new Set(m.current.keys).size,200);
 assert.equal(m.begin(true),null);
});
test("empty pages, repeated tokens and foreign keys are validated", () => {
 const m=new DiscoveryModel(config,"mine"); const t=m.begin();
 assert.throws(()=>m.acceptPage(t,page([{key:"XYZ-1"}],"p")));
 m.acceptPage(t,page([],"p")); const next=m.begin(true);
 assert.throws(()=>m.acceptPage(next,page([],"p")));
 m.acceptPage(next,page([])); assert.equal(m.nextPageToken,"");
});
test("refresh failure retains results; success replaces them and TTL zero retires old bodies", () => {
 const m=new DiscoveryModel(config,"mine"); m.acceptPage(m.begin(),page([row(1),row(2)]));
 m.select("ABC-1"); m.accept({...row(1),description:"Invented"});
 const refresh=m.begin(); m.status="request_failed";
 assert.deepEqual(m.current.keys,["ABC-1","ABC-2"]);
 m.acceptPage(refresh,page([row(2)])); assert.equal(m.details.size,0);
 assert.deepEqual(m.current.keys,["ABC-2"]);
});


test("empty changing cursors cannot grow an unbounded pagination history", () => {
 const m=new DiscoveryModel(config,"mine"); let token=m.begin();
 for(let i=0;i<200;i++) {
  assert.ok(token); m.acceptPage(token,page([],`cursor-${i}`)); token=m.begin(true);
 }
 assert.equal(token,null); assert.equal(m.seenTokens.size,199);
});

test("collection refresh updates filtering independently of cached and later-arriving bodies", () => {
 const m=new DiscoveryModel({...config,ttl:10},"mine");
 m.acceptPage(m.begin(),page([{key:"ABC-1",summary:"Old",status:"Open"}]),100);
 m.select("ABC-1"); m.accept({key:"ABC-1",summary:"Old",status:"Open",description:"Retained body",fetchedAt:100},100);
 m.acceptPage(m.begin(),page([{key:"ABC-1",summary:"New",status:"Done"}]),200);
 assert.equal(m.details.get("ABC-1").description,"Retained body");
 assert.equal(m.metadata.get("ABC-1").summary,"New");
 m.filter("Done"); assert.deepEqual(m.rows(),["ABC-1"]);
 m.filter("Open"); assert.deepEqual(m.rows(),[]);
 m.accept({key:"ABC-1",summary:"Cached old",status:"Open",fetchedAt:150},250);
 assert.equal(m.metadata.get("ABC-1").status,"Done");
 m.accept({key:"ABC-1",summary:"Fresh detail",status:"Review",fetchedAt:300},300);
 assert.equal(m.metadata.get("ABC-1").status,"Review");
 assert.equal(m.fetchedAt,200);
});

test("collection pages cannot undo denial while an explicit issue retry is pending", () => {
 const m=new DiscoveryModel(config,"mine"); m.acceptPage(m.begin(),page([row(1)]));
 const pending=m.begin(); m.failIssue("ABC-1",true); m.retryIssue("ABC-1",{manual:true});
 m.acceptPage(pending,page([row(1)]));
 assert.equal(m.denied.has("ABC-1"),true); assert.equal(m.metadata.has("ABC-1"),false);
 m.accept({key:"ABC-1",summary:"Access restored",status:"Open"});
 assert.equal(m.denied.has("ABC-1"),false); assert.equal(m.metadata.get("ABC-1").summary,"Access restored");
});

test("changed queries retain denials during loading and prune unreturned keys after settlement", () => {
 const m=new DiscoveryModel(config,"text"); m.draft="orchard";
 m.acceptPage(m.begin(),page([row(1)])); m.failIssue("ABC-1",true);
 m.draft="fruit"; const pending=m.begin(); m.prune();
 assert.equal(m.denied.has("ABC-1"),true);
 m.acceptPage(pending,page([row(1)]));
 assert.equal(m.metadata.has("ABC-1"),false); assert.equal(m.failures.has("ABC-1"),true);
 assert.equal(m.rowStates.get("ABC-1").status,"denied");
 m.draft="empty orchard"; m.acceptPage(m.begin(),page([]));
 assert.equal(m.denied.size,0,"unretained keys do not accumulate across settled queries");
});
