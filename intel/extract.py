"""Turn each collected bulletin into a structured record with Claude.

The CAFC dataset says *how much* of each scam is reported, but not how the
money moved. The bulletins say *how* scams work. Extraction gives us, per
document: which typologies it describes, the payment methods victims were
told to use, whether Interac e-Transfer is named, and any newer tactics
(deepfakes, OTP theft, etc.). Results are cached in data/extracted/.
"""
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .collect import load_docs
from .llm import chat_json
from .taxonomy import KILL_CHAIN, TYPOLOGIES

OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "extracted"

SYSTEM = (
    "You are a fraud intelligence analyst at a Canadian payments company. "
    "You extract facts from public scam bulletins precisely. Only report what the text says; "
    "never invent details. Reply with JSON only."
)

TYPOLOGY_LIST = "\n".join(f"- {t['id']}: {t['name']}" for t in TYPOLOGIES)
STAGES = ", ".join(key for key, _, _ in KILL_CHAIN)

PROMPT = """Extract structured scam intelligence from this Canadian Anti-Fraud Centre page.

Typology ids you may use:
{typologies}

Return JSON with exactly these keys:
{{
  "typologies": [ids from the list above that the page actually describes],
  "contact_channels": [how scammers reach victims, e.g. "phone call", "text message", "social media ad"],
  "pretexts": [short phrases for the story used, e.g. "caller claims to be bank fraud department"],
  "payment_methods": [how victims are told to pay, e.g. "Interac e-Transfer", "crypto ATM", "gift cards", "cash courier", "wire transfer"],
  "mentions_interac": true/false (the page explicitly names Interac or e-Transfer),
  "interac_context": "one sentence on how e-Transfer/Interac is involved, or empty string",
  "target_groups": [e.g. "seniors", "newcomers", "students", "businesses"],
  "emerging_tactics": [newer techniques if described: deepfakes, AI voice cloning, one-time passcode theft, spoofed caller ID, remote access apps, QR codes, etc.],
  "kill_chain_signals": {{stage: "what in the text describes this stage"}} for stages among: {stages},
  "red_flags": [up to 5 warning signs the page lists],
  "key_quote": "one short sentence (under 25 words) copied from the page that best captures the scam"
}}

Page title: {title}
Page date: {date}

Page text:
{text}"""


def extract_doc(doc: dict) -> dict:
    prompt = PROMPT.format(typologies=TYPOLOGY_LIST, stages=STAGES, title=doc["title"],
                           date=doc["date"] or "unknown", text=doc["text"][:12000])
    record = chat_json(prompt, system=SYSTEM, max_tokens=1500)
    record["typologies"] = [t for t in record.get("typologies", []) if t in {x["id"] for x in TYPOLOGIES}]
    record.update({k: doc[k] for k in ("id", "url", "title", "date", "source")})
    return record


def extract_all(force: bool = False, workers: int = 4) -> list[dict]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    todo = [d for d in load_docs() if force or not (OUT_DIR / f"{d['id']}.json").exists()]
    print(f"  extracting {len(todo)} documents with Claude...")

    def run(doc):
        try:
            rec = extract_doc(doc)
            (OUT_DIR / f"{doc['id']}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
            return f"  ok   {doc['title'][:60]}  -> {rec['typologies']}"
        except Exception as exc:  # keep going; one bad page shouldn't stop the run
            return f"  FAIL {doc['title'][:60]}: {exc}"

    with ThreadPoolExecutor(workers) as pool:
        for line in pool.map(run, todo):
            print(line)
    return load_extracted()


def load_extracted() -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(OUT_DIR.glob("*.json"))]


def summarize(records: list[dict]) -> dict:
    """Roll extracted records up into counts the brief can use."""
    from collections import Counter

    synonyms = {"bitcoin": "cryptocurrency", "crypto": "cryptocurrency", "crypto atm": "cryptocurrency",
                "e-transfer": "interac e-transfer", "email money transfer": "interac e-transfer",
                "multi-factor authentication code theft": "one-time passcode theft",
                "deepfake": "deepfakes", "ai voice cloning": "deepfakes / ai voice cloning",
                "deepfakes": "deepfakes / ai voice cloning", "caller id spoofing": "spoofed caller id"}

    def norm(x):
        x = x.strip().lower()
        return synonyms.get(x, x)

    payment = Counter(norm(p) for r in records for p in r.get("payment_methods", []))
    tactics = Counter(norm(t) for r in records for t in r.get("emerging_tactics", []))
    recent = [r for r in records if (r.get("date") or "") >= "2025-01-01"]
    recent_tactics = Counter(norm(t) for r in recent for t in r.get("emerging_tactics", []))
    interac_docs = [r for r in records if r.get("mentions_interac")]
    by_typology = Counter(t for r in records for t in r.get("typologies", []))
    interac_by_typology = Counter(t for r in interac_docs for t in r.get("typologies", []))
    return {
        "n_docs": len(records),
        "n_recent": len(recent),
        "payment_methods": payment.most_common(15),
        "emerging_tactics": tactics.most_common(15),
        "recent_tactics": recent_tactics.most_common(10),
        "interac_docs": interac_docs,
        "by_typology": by_typology,
        "interac_by_typology": interac_by_typology,
    }
