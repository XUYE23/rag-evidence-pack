# RAG Evidence Pack

[![Tests](https://github.com/XUYE23/rag-evidence-pack/actions/workflows/ci.yml/badge.svg)](https://github.com/XUYE23/rag-evidence-pack/actions/workflows/ci.yml)

**Fit retrieved evidence into a budget. Keep every selected span traceable.**

A dependency-free extractive packer for English/Chinese retrieval results.
Returns exact source offsets, stable citations, and source hashes. Includes a
Dify external-knowledge adapter.

[简体中文](README.zh-CN.md) · [Dify integration](docs/dify.md)

## Quick start

```sh
git clone https://github.com/XUYE23/rag-evidence-pack.git
cd rag-evidence-pack
python -m pip install .
rag-evidence-pack demo --output outputs/demo.json
rag-evidence-pack pack examples/documents.json --query "日志保留多久" --budget 220
python -m unittest discover -s tests -v
```

Open outputs/demo.html for the evidence cards and their source ranges.

```python
from rag_evidence_pack import Document, EvidencePacker

docs = [Document("manual", "Logs expire after 30 days. Exports require admin access.")]
pack = EvidencePacker().pack("When do logs expire?", docs, budget=180)
assert pack.verify(docs)
assert pack.used <= 180
print(pack.context)
```

## Behavior

1. Split into sentence-like spans, retaining original Python character offsets.
2. Deduplicate exact case/whitespace-normalized spans.
3. Rank using BM25 with Latin tokens and Chinese characters/bigrams.
4. Greedily select by relevance, lexical diversity, and incremental rendered size.
5. Verify complete source hashes and exact span slices.

The budget covers the rendered evidence, including citation markers and separators.
The default unit is **UTF-8 bytes**. For a model token budget, pass a counter:

```python
packer = EvidencePacker(count=lambda s: len(tokenizer.encode(s)), unit="model_tokens")
```

Reserve separate space for system instructions, user question, chat history, and
model output. Punctuation/window splitting can omit nearby qualifications;
inspect selected evidence and evaluate answer quality for your workload.
An extractive citation proves text provenance. It does not prove factual truth,
answer support, or resistance to prompt injection. Treat retrieved content as data.

## Dify

The included WSGI app implements POST /retrieval and Bearer authentication.
See docs/dify.md for request examples, deployment, and metadata-filter support.

## Where this fits

[LLMLingua](https://github.com/microsoft/LLMLingua) provides learned token-level
compression. This package offers a lightweight span-selection workflow with exact
offset verification and configurable budget counting. No trained compressor, model
download, embedding service, or LLM judge is needed by the core.

This initial alpha uses established BM25/diversity heuristics. It has no claim
of better semantic recall or answer accuracy than embedding rerankers or
learned compressors. Chinese/English support is lexical; synonyms and translation
need upstream retrieval or a future scoring adapter.

## Evaluation and roadmap

The demo is a hand-authored documentation fixture. Inspect input_text_bytes,
used, and source_verified in its output. Bytes saved are separate from LLM answer
quality. Future evaluations should hold retrieval inputs fixed, sweep budgets,
compare truncation/BM25/MMR baselines, and measure evidence recall plus answer
accuracy on independently labeled data.

Contributions welcome: reranker adapters, tokenizer integrations, multilingual
fixtures, and full Dify deployment reports. Core API tests include budgets,
Unicode offsets, source changes, deduplication, auth, and request validation.

MIT licensed. Initial implementation developed with AI assistance.

## Recorded local validation

11 tests passed after installation on Windows / Python 3.12.14.
[Validation record](docs/validation.json) · [Demo result](docs/demo-result.json)

The hand-authored bilingual demo packs 359 input text bytes into 105 rendered evidence bytes under a 220-byte budget; 2 spans pass source verification. This is a mechanical fixture result; downstream answer quality was not measured.
