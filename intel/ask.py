"""Ask questions of the fraud knowledge base and get answers with citations.

Retrieval is plain BM25 over paragraph chunks: no vector database needed
at this size, and every answer can be traced back to a source page.
"""
import math
import re
from collections import Counter

from .collect import load_docs
from .llm import chat

TOKEN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
STOP = set("the a an and or of to in for on is are be by with your you it this that as at from can will if not".split())


def _tokens(text: str) -> list[str]:
    return [t for t in TOKEN.findall(text.lower()) if t not in STOP]


def _chunks(doc: dict, size: int = 900) -> list[dict]:
    paras, buf, out = doc["text"].split("\n"), "", []
    for p in paras:
        if len(buf) + len(p) > size and buf:
            out.append(buf)
            buf = ""
        buf += p + "\n"
    if buf.strip():
        out.append(buf)
    return [{"doc": doc, "text": c} for c in out]


class KnowledgeBase:
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.chunks = [c for d in load_docs() for c in _chunks(d)]
        self.tf = [Counter(_tokens(c["doc"]["title"] + " " + c["text"])) for c in self.chunks]
        self.lens = [sum(t.values()) for t in self.tf]
        self.avg = sum(self.lens) / max(len(self.lens), 1)
        df = Counter(term for t in self.tf for term in t)
        n = len(self.chunks)
        self.idf = {term: math.log(1 + (n - f + 0.5) / (f + 0.5)) for term, f in df.items()}
        self.k1, self.b = k1, b

    def search(self, query: str, k: int = 6) -> list[dict]:
        q = _tokens(query)
        scores = []
        for i, tf in enumerate(self.tf):
            s = 0.0
            for term in q:
                if term in tf:
                    f = tf[term]
                    s += self.idf[term] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * self.lens[i] / self.avg))
            scores.append(s)
        top = sorted(range(len(scores)), key=scores.__getitem__, reverse=True)[:k]
        return [self.chunks[i] for i in top if scores[i] > 0]

    def expand(self, question: str) -> str:
        """Keyword search misses synonyms ('safe account' vs 'protect your account'), so let Claude add search terms."""
        terms = chat("List 10 search keywords and short phrases (synonyms, scam names, how fraud bulletins would "
                     f"phrase it) for finding documents that answer: {question}\nReply with the terms only, comma-separated.",
                     max_tokens=120)
        return f"{question} {terms}"

    def ask(self, question: str) -> str:
        hits = self.search(self.expand(question))
        if not hits:
            return "Nothing in the knowledge base matches that question."
        sources, seen = [], {}
        for h in hits:
            url = h["doc"]["url"]
            if url not in seen:
                seen[url] = len(seen) + 1
            sources.append(f"[{seen[url]}] {h['doc']['title']} ({h['doc']['date'] or 'undated'})\n{h['text']}")
        prompt = (
            "Answer the question for a fraud strategy team using ONLY the sources below. "
            "Cite sources inline like [1]. If the sources don't cover something, say so. "
            "Be concise: a short answer, then bullet points if useful.\n\n"
            f"Question: {question}\n\nSources:\n\n" + "\n\n".join(sources)
        )
        answer = chat(prompt, max_tokens=800)
        cited = {int(n) for group in re.findall(r"\[([\d,\s]+)\]", answer) for n in re.findall(r"\d+", group)}
        refs = "\n".join(f"[{n}] {url}" for url, n in seen.items() if n in cited)
        return f"{answer}\n\nSources:\n{refs}"
