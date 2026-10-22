# Canadian Payment Scam Intelligence Engine

Reads public Canadian fraud data, works out which scams are growing, maps each one to
where it could be stopped, and writes a 4-page executive fraud intelligence brief.

**Output:** [`output/scam-intel-brief-2025-09.pdf`](output/scam-intel-brief-2025-09.pdf)

## What it does

| Step | File | What happens |
|---|---|---|
| 1. Collect | `intel/collect.py` | Downloads 83 Canadian Anti-Fraud Centre (CAFC) scam pages and bulletins |
| 2. Extract | `intel/extract.py` | Claude turns each page into structured intel: scam type, contact channel, payment method, Interac involvement, new tactics |
| 3. Taxonomy | `intel/taxonomy.py` | 15 scam typologies mapped onto a 5-stage **Payment Scam Kill Chain**, each with candidate controls scored on effort / cost / impact |
| 4. Trends | `intel/trends.py` | 266K CAFC reports (2021–Sep 2025): what's growing year over year, median loss per victim, contact-channel shifts, senior exposure |
| 5. Brief | `intel/brief.py` | Ranks controls with a transparent formula, has Claude write the prose from computed numbers only, builds the PDF |
| 6. Ask | `intel/ask.py` | Ask questions of the knowledge base; answers cite source pages |

## Run it

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python run.py brief
.venv\Scripts\python run.py ask "How are scammers abusing e-Transfer against marketplace sellers?"
```

Needs AWS credentials with Bedrock access to Claude (`INTEL_MODEL_ID` to override the model).
The CAFC dataset goes in `data/raw/cafc.csv` (from open.canada.ca, "Canadian Anti-Fraud Centre
Fraud Reporting System Dataset").

## Key findings (Apr–Sep 2025 vs Apr–Sep 2024)

- **Recovery-pitch scams (re-victimization) are the sharpest riser:** losses $3.6M → $15.6M,
  victims with losses 115 → 214, median loss $7.6K → $17.6K. Not driven by outliers.
- **Fewer reports, bigger losses per victim:** investment median $25K → $32K, romance $20.6K → $30K,
  even as report counts fall.
- Investment/crypto scams are 54% of reported losses in the window.
- Text messages are a growing share of how scammers reach people (+2.2 pts).

## Design decisions worth defending

- **Recommendations are ranked by a formula, not the LLM:**
  `(impact ÷ (effort + cost)) × Interac exposure × √(loss share) × (1 + growth)`. The LLM only writes the explanation.
- **Growth must survive outlier removal.** A category only counts as "growing" if it still grows after dropping
  each period's 3 largest reports (seller-side overpayment's +40% failed this test).
- **Counts are treated with suspicion.** Total CAFC report volume fell every year since 2021, so falling counts
  don't mean less fraud. Median loss and mix are used instead.
- **Spear phishing is mapped to business email compromise**, not consumer account takeover. CAFC's spear phishing
  category is targeted business fraud. Ordinary phishing reports record $0 because the loss shows up under other categories.
- The LLM gets a facts JSON and is told never to compute new numbers (an early draft mixed a 6-month figure with a
  12-month total; the fix was to precompute every share).

## Limitations

- The latest CAFC open dataset runs to September 2025; bulletins run to October 2026.
- Only a small share of fraud is reported to the CAFC. Figures show direction and mix, not totals.
- Interac exposure and effort/cost/impact scores are analyst judgements, in `taxonomy.py` so they can be argued with.
- Control ideas are candidates for discussion, not claims about what Interac or any bank does today.

## Next additions

- Reddit (r/PersonalFinanceCanada, r/Scams) via the official Reddit API, for victim-voice signals on e-Transfer scams
- News sources (CBC, CTV) and Competition Bureau / FCAC advisories
- Monthly scheduled run that diffs against last month's brief
