# Dify external knowledge integration

Contract reference, checked 2026-10-03:
https://docs.dify.ai/en/cloud/use-dify/knowledge/external-knowledge-api

1. Install the package. Set EVIDENCE_API_KEY in the server environment.
2. Run rag-evidence-pack serve examples/documents.json --knowledge-id docs.
3. For local protocol testing, send examples/dify-request.json to
   http://127.0.0.1:8787/retrieval with Authorization: Bearer <your key>.
4. Configure Dify External Knowledge with the base endpoint (omit /retrieval),
   the matching API key, and knowledge ID docs.

Dify running in Docker needs a reachable host address. Bind to a suitable
interface only when needed. Use a production WSGI server and an authenticated
TLS reverse proxy for network deployment; wsgiref is a local development server.

Request: knowledge_id, query, retrieval_setting {top_k,score_threshold}.
Response: records [{content,score,title,metadata}]. The lexical score is
BM25/(1+BM25), a bounded relevance heuristic, not a probability. Scores across
different corpora are not calibrated. Start with score_threshold=0.

Metadata filters support is, in, contains, combined with and/or. Unsupported
operators return HTTP 400; no silent filter bypass. The server rejects unknown
knowledge IDs, invalid schemas, nonfinite scores, and bodies over 1 MB.
The source collection lives in memory. User data is neither fetched nor uploaded.

Metadata includes evidence_pack {document_id,start,end,citation,source_sha256}.
The server's byte budget is conservative for returned content because it includes
internal citation markers as well. Dify may add its own surrounding formatting;
budget that overhead separately.

Validation: local WSGI protocol tests cover authentication, request/response
fields, collection isolation, filtering and error paths. A live Dify deployment
has not been validated by the initial offline test suite.
