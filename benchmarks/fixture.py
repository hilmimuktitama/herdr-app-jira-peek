"""Entirely fictional loopback Jira. Never reads user configuration or credentials."""
import json
import hashlib
import re
import threading
import shutil
import shlex
import ssl
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs

# The shell baseline retains its normal curl invocation boundary, implemented
# by this fake curl. Both implementations receive the same loopback responses.
FAKE_CURL = r'''#!/usr/bin/env python3
import json, os, pathlib, sys, urllib.request, urllib.error
from urllib.parse import urlsplit
args=sys.argv[1:]; u=urlsplit(args[-1])
url=os.environ["JIRA_PEEK_FIXTURE_HTTP"]+u.path+("?"+u.query if u.query else "")
data=pathlib.Path(args[args.index("--data-binary")+1][1:]).read_bytes() if "--data-binary" in args else None
request=urllib.request.Request(url,data=data,headers={"Content-Type":"application/json"})
try:
    response=urllib.request.urlopen(request,timeout=30); code=response.status; body=response.read()
except urllib.error.HTTPError as e: code=e.code; body=e.read()
if "-o" in args: pathlib.Path(args[args.index("-o")+1]).write_bytes(body); print(code,end="")
else: print(body.decode(),end="")
'''

class Fixture:
    def __init__(self, root, tls=False, populated=False):
        self.root = root
        self.populated = populated
        self.calls = []
        self.lock = threading.Lock()
        self.hook = None
        self.closed = False
        fixture = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def handle(self):
                try: super().handle()
                except (ConnectionError, BrokenPipeError): pass  # Rejected TLS/closed fixture client.
            def do_POST(self): self.do_GET()
            def do_GET(self):
                url=urlsplit(self.path)
                length=int(self.headers.get("Content-Length",0))
                payload=json.loads(self.rfile.read(length)) if length else None
                kind="site" if url.path.endswith("/_edge/tenant_info") else "comments" if url.path.endswith("/comment") else "metadata" if url.path.endswith("/bulkfetch") else "issue"
                match=re.search(r"ABC-\d+",url.path)
                key=match.group() if match else "ABC-1"
                call={"kind":kind,"key":key,"query":parse_qs(url.query)}
                with fixture.lock:
                    fixture.calls.append({**call,"path":url.path,"payload":payload,"auth_digest":hashlib.sha256(self.headers.get("Authorization", "").encode()).hexdigest(),"auth_present":bool(self.headers.get("Authorization")),"auth_is_fixture":self.headers.get("Authorization")=="Basic ZmljdGlvbmFsOmZpY3Rpb25hbA=="})
                    with (root/"rest-calls").open("a") as f: f.write(json.dumps(call)+"\n")
                result=fixture.hook(call) if fixture.hook else None
                code,body=result if result is not None else fixture.response(kind,key,payload)
                content=json.dumps(body).encode()
                self.send_response(code)
                self.send_header("Content-Type","application/json")
                self.send_header("Content-Length",str(len(content)))
                self.end_headers()
                self.wfile.write(content)
        self.server=ThreadingHTTPServer(("127.0.0.1",0),Handler)
        self.certificate = None
        if tls:
            self.certificate = root / "fixture-ca.pem"
            ca_key = root / "fixture-ca-key.pem"
            key = root / "fixture-key.pem"
            cert = root / "fixture-server.pem"
            csr = root / "fixture-server.csr"
            conf = root / "fixture-openssl.cnf"
            conf.write_text("[req]\ndistinguished_name=dn\nx509_extensions=ca\nprompt=no\n[dn]\nCN=Fictional Jira fixture CA\n[ca]\nbasicConstraints=critical,CA:TRUE\nkeyUsage=critical,keyCertSign,cRLSign\n[server]\nsubjectAltName=DNS:jira.example.test,IP:127.0.0.1\nbasicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\n")
            commands=[
                ["openssl","req","-x509","-newkey","rsa:2048","-nodes","-days","1","-config",str(conf),"-keyout",str(ca_key),"-out",str(self.certificate)],
                ["openssl","req","-new","-newkey","rsa:2048","-nodes","-subj","/CN=jira.example.test","-keyout",str(key),"-out",str(csr)],
                ["openssl","x509","-req","-in",str(csr),"-CA",str(self.certificate),"-CAkey",str(ca_key),"-set_serial","1","-days","1","-extfile",str(conf),"-extensions","server","-out",str(cert)]]
            for command in commands: subprocess.run(command,check=True,capture_output=True)
            ca_key.chmod(0o600);key.chmod(0o600)
            context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(cert,key)
            self.server.socket=context.wrap_socket(self.server.socket,server_side=True)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.url=f"{'https' if tls else 'http'}://127.0.0.1:{self.server.server_port}"
    def curl_wrapper(self, path):
        """Exec actual curl; only route the fictional host and trust its local CA."""
        assert self.certificate
        binary=shutil.which("curl")
        if not binary: raise RuntimeError("curl required")
        path.write_text("#!/bin/sh\nexec "+shlex.quote(binary)+' "$@" --noproxy "*" --connect-to '+
            shlex.quote(f"jira.example.test:443:127.0.0.1:{self.server.server_port}")+" --cacert "+shlex.quote(str(self.certificate))+"\n")
        path.chmod(0o700)
        return binary
    def close(self):
        if self.closed: return
        self.closed=True
        self.server.shutdown(); self.server.server_close(); self.thread.join()
    def response(self,kind,key,payload):
        mode=(self.root/"rest-mode").read_text() if (self.root/"rest-mode").exists() else "ok"
        if kind=="site": return 200,{"cloudId":"another-fictional-cloud" if mode=="site-mismatch" else "fictional-cloud-123"}
        if kind=="comments":
            if mode=="comments-denied": return 403,{"errorMessages":["FICTIONAL_RAW_RESPONSE_SENTINEL"]}
            if mode=="comments-malformed": return 200,{"startAt":0,"total":205,"comments":[]}
            return 200,{"startAt":0,"maxResults":100,"total":205,"comments":[{"author":{"displayName":"Fictional Reader","accountId":"PRIVATE_METADATA_SENTINEL"},"body":f"Fictional recent comment {205-i}"} for i in range(100)]}
        if key=="ABC-2" and mode in ("issue-denied","issue-unauthorized"):
            return (403 if mode=="issue-denied" else 401),{"errorMessages":["FICTIONAL_RAW_RESPONSE_SENTINEL"]}
        if (self.root/"override.json").exists():
            issue=json.loads((self.root/"override.json").read_text())
            return 200,({"issues":[issue]} if kind=="metadata" else issue)
        if self.populated:
            def issue(k):
                return {"key":k,"fields":{"summary":f"Fictional delivery plan {k}","status":{"name":"In Progress"},
                    "assignee":{"displayName":"Alex Example"},"updated":"2026-01-01T10:00:00Z",
                    "description":{"type":"doc","content":[{"type":"paragraph","content":[{"type":"text","text":"Fictional validation notes. "*120}]}]}}}
            if kind=="metadata": return 200,{"issues":[issue(k) for k in payload["issueIdsOrKeys"]]}
            return 200,issue(key)
        if kind=="metadata": return 200,{"issues":[]}
        return 200,{"key":key,"fields":{"summary":"Fictional immediate context","description":"Core description","status":{"name":"Open"}}}
