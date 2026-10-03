import argparse
import html
import json
import os
from pathlib import Path
from .core import Document, EvidencePacker


def demo_documents():
    return [
        Document("guide","The archive retains logs for 30 days. "
                 "The service supports three dashboard themes. "
                 "The search endpoint retries transient failures twice.",
                 "Operations guide",{"language":"en"}),
        Document("policy","日志保留期限为30天。导出日志需要管理员权限。"
                 "日志保留期限为30天。页面主题可以在设置中调整。",
                 "运维规范",{"language":"zh"}),
        Document("release","This release updates button spacing and icon colors. "
                 "The archive retains logs for 30 days.","Release notes")
    ]


def load_documents(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data,list):
        raise ValueError("input must be an array of documents")
    return [Document(**item) for item in data]


def write_result(result, output, docs):
    path = Path(output)
    path.parent.mkdir(parents=True,exist_ok=True)
    payload = result.to_dict()
    payload["source_verified"] = result.verify(docs)
    payload["input_text_bytes"] = sum(len(d.text.encode("utf-8")) for d in docs)
    path.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    page = """<!doctype html><meta charset="utf-8"><title>RAG Evidence Pack</title>
<style>body{font:16px system-ui;max-width:1000px;margin:48px auto;padding:24px;background:#101827;color:#edf2ff}
h1{color:#a4b4ff}article{padding:20px;margin:18px 0;background:#1d2940;border-radius:14px}
pre{white-space:pre-wrap;overflow-wrap:anywhere}small{color:#9baed0}</style><h1>RAG Evidence Pack</h1>"""
    page += f"<p>Budget: {result.used}/{result.budget} {html.escape(result.unit)} · Source verified: {result.verify(docs)}</p>"
    for s in result.spans:
        page += f"<article><small>{html.escape(s.title)} · [{s.start}:{s.end}] · {s.citation}</small><p>{html.escape(s.text)}</p></article>"
    page += "<details><summary>Assembled context</summary><pre>"+html.escape(result.context)+"</pre></details>"
    path.with_suffix(".html").write_text(page,encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Pack evidence under an explicit context budget.")
    sub = parser.add_subparsers(dest="command",required=True)
    demo = sub.add_parser("demo")
    demo.add_argument("--output",default="outputs/demo.json")
    run = sub.add_parser("pack")
    run.add_argument("input")
    run.add_argument("--query",required=True)
    run.add_argument("--budget",type=int,default=2048)
    run.add_argument("--output",default="outputs/pack.json")
    serve = sub.add_parser("serve")
    serve.add_argument("input")
    serve.add_argument("--knowledge-id",default="docs")
    serve.add_argument("--host",default="127.0.0.1")
    serve.add_argument("--port",type=int,default=8787)
    serve.add_argument("--budget",type=int,default=2048)
    args = parser.parse_args(argv)
    try:
        if args.command == "serve":
            from wsgiref.simple_server import make_server
            from .server import create_app
            app = create_app({args.knowledge_id:load_documents(args.input)},
                             os.environ.get("EVIDENCE_API_KEY",""),budget=args.budget)
            print(f"Serving Dify /retrieval on {args.host}:{args.port}")
            with make_server(args.host,args.port,app) as httpd:
                httpd.serve_forever()
            return 0
        docs = demo_documents() if args.command == "demo" else load_documents(args.input)
        query = "日志保留期限 log retention" if args.command == "demo" else args.query
        budget = 220 if args.command == "demo" else args.budget
        result = EvidencePacker().pack(query,docs,budget=budget)
        write_result(result,args.output,docs)
        print(json.dumps({"used":result.used,"budget":budget,"spans":len(result.spans),
                          "source_verified":result.verify(docs)},ensure_ascii=False))
    except (ValueError,TypeError,OSError) as exc:
        parser.error(str(exc))
    return 0
