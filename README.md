# Canadian Scam Intelligence

Reads public Canadian fraud data, works out which scams are growing, shows how victims are
told to pay, maps where each scam could be stopped, and writes a 4-page executive fraud
intelligence brief.

**Output:** [`output/scam-intel-brief-2025-09.pdf`](output/scam-intel-brief-2025-09.pdf)

## The three questions it answers

| Question | Source |
|---|---|
| Which scams cost Canadians the most, and which are growing? | CAFC fraud reports dataset (scale: losses, victims, trends) |
| How do victims pay: bank transfer, crypto, wire, gift cards, cash? | CAFC scam bulletins (mechanics) |
| What should banks and payment networks do first? | Kill-chain taxonomy + ranked controls |

## How it works

| Step | File | What happens |
|---|---|---|
| 1. Collect | `intel/collect.py` | Downloads 83 Canadian Anti-Fraud Centre (CAFC) scam pages and bulletins |
| 2. Extract | `intel/extract.py` | An LLM turns each page into structured fields: scam type, contact channel, payment methods, new tactics. Payment methods are grouped into bank transfer, crypto, wire, gift cards, cash and card |
| 3. Taxonomy | `intel/taxonomy.py` | 15 scam typologies mapped onto a 5-stage **Payment Scam Kill Chain** (Contact → Pretext → Payment request → Fund movement → Cash-out), each with candidate controls scored on effort / cost / impact |
| 4. Trends | `intel/trends.py` | 266K CAFC reports (2021–Sep 2025): year-over-year growth, median loss per victim, contact-channel shifts, losses among victims 60+ |
| 5. Brief | `intel/brief.py` | Ranks controls with a transparent formula, writes the prose from precomputed numbers only, builds the PDF |
| 6. Ask | `intel/ask.py` | Answers questions from the bulletins, citing the source pages |

## Run it

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python run.py all
.venv\Scripts\python run.py ask "How do overpayment scams target online sellers?"
```

The LLM steps run on Claude through AWS Bedrock and need AWS credentials with Bedrock access
(`INTEL_MODEL_ID` overrides the model). The CAFC dataset goes in `data/raw/cafc.csv`
(open.canada.ca, "Canadian Anti-Fraud Centre Fraud Reporting System Dataset").

## Key findings (Apr–Sep 2025 vs Apr–Sep 2024)

- **Recovery-pitch scams (re-targeting people already scammed) are the sharpest riser:** losses
  $3.6M → $15.6M, victims with losses 115 → 214, median loss $7.6K → $17.6K. Not driven by outliers.
- **Fewer reports, bigger losses per victim:** investment median $25K → $32K, romance $20.6K → $30K,
  even as report counts fall.
- Investment/crypto scams are 54% of reported losses in the window.
- Text messages are a growing share of how scammers first reach people (+2.2 pts).

## Design decisions

- **Recommendations are ranked by a formula, not the LLM:**
  `(impact ÷ (effort + cost)) × bank-transfer exposure × √(loss share) × (1 + growth)`.
  The LLM only writes the explanation.
- **Growth must survive outlier removal.** A category only counts as growing if it still grows after
  dropping each period's 3 largest reports. Seller-side overpayment's +40% failed this test.
- **Counts are treated with suspicion.** Total CAFC report volume fell every year since 2021, so falling
  counts don't mean less fraud. Median loss and loss mix are used instead.
- **Spear phishing is mapped to business email compromise**, not consumer account takeover. CAFC's spear
  phishing category is targeted business fraud. Ordinary phishing reports record $0 because the loss
  appears under other categories.
- **Numbers are computed in code, never by the LLM.** An early draft mixed a 6-month figure with a
  12-month total; the fix was to precompute every share and forbid new arithmetic.

## Limitations

- The latest CAFC open dataset runs to September 2025; bulletins run to October 2026.
- Only a small share of fraud is reported to the CAFC. Figures show direction and mix, not totals.
- Payment-method shares count how many bulletins name each method, not how often each is used.
- Bank-transfer exposure and effort/cost/impact scores are analyst judgements, kept in `taxonomy.py`
  so they can be argued with.
- Control ideas are candidates for discussion, not claims about what any institution does today.

## Next additions

- Reddit (r/PersonalFinanceCanada, r/Scams) via the official Reddit API, for victim-voice signals
- News sources and Competition Bureau / FCAC advisories
- Monthly scheduled run that compares against the previous month's brief
