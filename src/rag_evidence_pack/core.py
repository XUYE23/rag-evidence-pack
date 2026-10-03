import hashlib
import json
import math
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Callable


def byte_count(text: str) -> int:
    """Default budget unit: UTF-8 bytes. Supply a tokenizer for token budgets."""
    return len(text.encode("utf-8"))


def terms(text):
    text = text.casefold()
    latin = re.findall(r"[a-z0-9_]+", text)
    cjk_runs = re.findall(r"[\u3400-\u9fff]+", text)
    return latin + [c for run in cjk_runs for c in run] + [
        run[i:i+2] for run in cjk_runs for i in range(len(run)-1)]


@dataclass(frozen=True)
class Document:
    id: str
    text: str
    title: str = ""
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.id,str) or not self.id:
            raise ValueError("document id must be a nonempty string")
        if not isinstance(self.text,str) or not isinstance(self.title,str):
            raise ValueError("document text/title must be strings")
        if not isinstance(self.metadata,dict):
            raise ValueError("metadata must be an object")


@dataclass(frozen=True)
class Span:
    citation: str
    document_id: str
    title: str
    start: int
    end: int
    text: str
    score: float
    source_sha256: str
    metadata: dict

    def render(self):
        return f"[{self.citation}]\n{self.text}"


@dataclass(frozen=True)
class Pack:
    context: str
    spans: list[Span]
    used: int
    budget: int
    unit: str

    def to_dict(self):
        return asdict(self)

    def verify(self, documents):
        """Check citations against current complete source documents."""
        docs = {d.id:d for d in documents}
        for s in self.spans:
            d = docs.get(s.document_id)
            if d is None or hashlib.sha256(d.text.encode("utf-8")).hexdigest() != s.source_sha256:
                return False
            if not 0 <= s.start < s.end <= len(d.text) or d.text[s.start:s.end] != s.text:
                return False
        return self.context == "\n\n".join(s.render() for s in self.spans)


def slices(text, max_chars):
    """Sentence-like segments plus bounded verbatim windows for long segments."""
    for match in re.finditer(r"[^。！？!?\n]+[。！？!?]?|[。！？!?]", text):
        # English sentence boundaries followed by whitespace; leave decimals intact.
        base = match.start()
        fragment = match.group()
        start = 0
        boundaries = [m.end() for m in re.finditer(r"\.(?=\s|$)", fragment)]
        if not boundaries or boundaries[-1] != len(fragment):
            boundaries.append(len(fragment))
        for stop in boundaries:
            left, right = start, stop
            while left < right and fragment[left].isspace():
                left += 1
            while right > left and fragment[right-1].isspace():
                right -= 1
            while left < right:
                end = min(left + max_chars, right)
                yield base+left, base+end
                left = end
            start = stop


class EvidencePacker:
    def __init__(self, *, count: Callable[[str], int] = byte_count,
                 unit="utf8_bytes", max_chars=360, diversity=.35):
        if type(max_chars) is not int or max_chars <= 0:
            raise ValueError("max_chars must be a positive integer")
        if not math.isfinite(diversity) or not 0 <= diversity <= 1:
            raise ValueError("diversity must be in [0,1]")
        self.count, self.unit = count, unit
        self.max_chars, self.diversity = max_chars, diversity

    def pack(self, query, documents, *, budget=2048, top_k=8, score_threshold=0.):
        if not isinstance(query,str) or not query.strip():
            raise ValueError("query must be nonempty")
        if type(budget) is not int or budget < 0 or type(top_k) is not int or top_k < 0:
            raise ValueError("budget/top_k must be nonnegative integers")
        if not math.isfinite(score_threshold) or not 0 <= score_threshold <= 1:
            raise ValueError("score_threshold must be in [0,1]")
        docs = list(documents)
        if len({d.id for d in docs}) != len(docs):
            raise ValueError("document ids must be unique")
        candidates = []
        seen = set()
        for d in docs:
            digest = hashlib.sha256(d.text.encode("utf-8")).hexdigest()
            for start,end in slices(d.text,self.max_chars):
                text = d.text[start:end]
                key = " ".join(text.casefold().split())
                if key in seen:
                    continue
                seen.add(key)
                tokens = terms(text)
                if not tokens:
                    continue
                citation = hashlib.sha256(json.dumps([d.id,digest,start,end],
                                                    ensure_ascii=False).encode()).hexdigest()[:16]
                candidates.append((d,start,end,text,digest,citation,Counter(tokens)))
        if not candidates or not terms(query) or budget == 0 or top_k == 0:
            return Pack("",[],0,budget,self.unit)
        df = Counter(t for c in candidates for t in c[6])
        avg = sum(sum(c[6].values()) for c in candidates)/len(candidates)
        q = set(terms(query))
        ranked = []
        for d,start,end,text,digest,citation,counts in candidates:
            length = sum(counts.values())
            bm25 = sum(math.log(1+(len(candidates)-df[t]+.5)/(df[t]+.5)) *
                       counts[t]*2.2/(counts[t]+1.2*(.25+.75*length/avg))
                       for t in q if counts[t])
            score = bm25/(1+bm25)
            if score > 0 and score >= score_threshold:
                ranked.append((Span(citation,d.id,d.title,start,end,text,score,digest,dict(d.metadata)),
                               set(counts)))
        selected, token_sets = [], []
        context = ""
        while ranked and len(selected) < top_k:
            options = []
            for index,(span,ts) in enumerate(ranked):
                candidate = "\n\n".join(s.render() for s in [*selected,span])
                cost = self.count(candidate)
                if type(cost) is not int or cost < 0:
                    raise ValueError("count function must return a nonnegative integer")
                if cost > budget:
                    continue
                redundancy = max((len(ts & old)/len(ts | old) for old in token_sets),default=0.)
                utility = span.score*(1-self.diversity*redundancy)/max(1,cost-self.count(context))**.5
                options.append((utility,span.score,-index,index,candidate))
            if not options:
                break
            _,_,_,index,context = max(options)
            span,ts = ranked.pop(index)
            selected.append(span)
            token_sets.append(ts)
        return Pack(context,selected,self.count(context),budget,self.unit)
