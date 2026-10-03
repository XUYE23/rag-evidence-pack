"""Small authenticated WSGI adapter for Dify's external knowledge API."""
import hmac
import json
import math
from .core import Document, EvidencePacker


def matches(metadata, condition):
    if condition is None:
        return True
    if not isinstance(condition,dict):
        raise ValueError("metadata_condition must be an object")
    op = condition.get("logical_operator","and")
    if op not in {"and","or"}:
        raise ValueError("logical_operator must be and/or")
    clauses = condition.get("conditions")
    if not isinstance(clauses,list):
        raise ValueError("conditions must be an array")
    values = []
    for c in clauses:
        if not isinstance(c,dict) or not isinstance(c.get("name"),str):
            raise ValueError("each metadata condition requires a name")
        actual, expected = metadata.get(c["name"]), c.get("value")
        cmp = c.get("comparison_operator")
        if cmp == "is":
            values.append(actual == expected)
        elif cmp == "in" and isinstance(expected,list):
            values.append(actual in expected)
        elif cmp == "contains" and isinstance(expected,str):
            values.append(isinstance(actual,str) and expected in actual)
        else:
            raise ValueError("supported metadata operators: is, in, contains")
    return (all(values) if op == "and" else any(values)) if values else True


def create_app(knowledge, api_key, *, budget=2048, max_body=1_000_000):
    if not isinstance(api_key,str) or not api_key:
        raise ValueError("a nonempty API key is required")
    packer = EvidencePacker()
    # Freeze document inventory at startup; unknown knowledge IDs fail closed.
    collections = {key:list(docs) for key,docs in knowledge.items()}

    def app(environ, start_response):
        def respond(status, payload):
            body = json.dumps(payload,ensure_ascii=False,allow_nan=False).encode("utf-8")
            start_response(status,[("Content-Type","application/json; charset=utf-8"),
                                   ("Content-Length",str(len(body)))])
            return [body]
        if environ.get("PATH_INFO") != "/retrieval":
            return respond("404 Not Found",{"error_msg":"unknown route"})
        if environ.get("REQUEST_METHOD") != "POST":
            return respond("405 Method Not Allowed",{"error_msg":"POST required"})
        auth = environ.get("HTTP_AUTHORIZATION","")
        if not hmac.compare_digest(auth.encode("utf-8"),("Bearer "+api_key).encode("utf-8")):
            return respond("401 Unauthorized",{"error_code":1002,"error_msg":"authorization failed"})
        try:
            length = int(environ.get("CONTENT_LENGTH") or "0")
            if not 0 < length <= max_body:
                return respond("413 Payload Too Large",{"error_msg":"invalid or oversized body"})
            raw = environ["wsgi.input"].read(length)
            if len(raw) != length:
                raise ValueError("incomplete request body")
            request = json.loads(raw)
            if not isinstance(request,dict):
                raise ValueError("request must be an object")
            kid = request.get("knowledge_id")
            if not isinstance(kid,str) or kid not in collections:
                return respond("404 Not Found",{"error_code":2001,"error_msg":"knowledge source not found"})
            settings = request.get("retrieval_setting")
            if not isinstance(settings,dict) or "top_k" not in settings or "score_threshold" not in settings:
                raise ValueError("retrieval_setting requires top_k and score_threshold")
            top_k, threshold = settings["top_k"], settings["score_threshold"]
            if type(top_k) is not int or not 0 <= top_k <= 100:
                raise ValueError("top_k must be an integer from 0 to 100")
            if type(threshold) not in (int,float) or not math.isfinite(threshold) or not 0 <= threshold <= 1:
                raise ValueError("score_threshold must be finite and in [0,1]")
            condition = request.get("metadata_condition")
            matches({},condition)  # validate even for an empty collection
            docs = [d for d in collections[kid] if matches(d.metadata,condition)]
            result = packer.pack(request.get("query"),docs,budget=budget,
                                 top_k=top_k,score_threshold=threshold)
            records = [{"content":s.text,"score":s.score,"title":s.title,
                        "metadata":{**s.metadata,"evidence_pack":{
                            "document_id":s.document_id,"start":s.start,"end":s.end,
                            "citation":s.citation,"source_sha256":s.source_sha256}}}
                       for s in result.spans]
            return respond("200 OK",{"records":records})
        except (ValueError,TypeError,KeyError,UnicodeError) as exc:
            return respond("400 Bad Request",{"error_msg":str(exc)})
    return app
