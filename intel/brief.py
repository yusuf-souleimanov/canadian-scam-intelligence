"""Build the executive fraud intelligence brief (PDF).

Numbers come from trends.py (CAFC data) and extract.py (bulletins).
Recommendations are ranked by a transparent formula, not by the LLM:

    priority = control value  x  Interac exposure  x  size of losses  x  growth

Claude only writes the prose (key judgements and the "why" for each
recommendation), and is told to use only the numbers it is given.
"""
import json
import math
from datetime import date
from pathlib import Path

from reportlab.graphics.charts.barcharts import HorizontalBarChart
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle)

from . import trends
from .extract import load_extracted, summarize
from .llm import chat_json
from .taxonomy import KILL_CHAIN, STAGE_NAMES, TYPOLOGY_BY_ID, control_score

OUT_DIR = Path(__file__).resolve().parent.parent / "output"

INK = colors.HexColor("#1b1f24")
MUTED = colors.HexColor("#5b6470")
ACCENT = colors.HexColor("#d4a017")  # gold
RULE = colors.HexColor("#d9dde2")
EXPOSURE_COLOR = {"High": colors.HexColor("#b4441f"), "Medium": colors.HexColor("#d4a017"), "Low": colors.HexColor("#9aa3ad")}
EXPOSURE_WEIGHT = {"High": 1.0, "Medium": 0.7, "Low": 0.4}
SERIES_COLORS = [colors.HexColor(c) for c in ("#b4441f", "#2f6db5", "#d4a017", "#3c8d5a")]


# ---------- analysis -> facts ----------

def rank_controls(tr) -> list[dict]:
    total_loss = tr["loss"].sum()
    ranked = []
    for tid, row in tr.iterrows():
        t = TYPOLOGY_BY_ID[tid]
        share = row["loss"] / total_loss if total_loss else 0
        # outlier-resistant growth: losses excluding each period's 3 largest reports
        growth = row["loss_ex_top3_yoy"] if not math.isnan(row["loss_ex_top3_yoy"]) else 0
        for c in t["controls"]:
            priority = (control_score(c) * EXPOSURE_WEIGHT[t["interac_exposure"]]
                        * math.sqrt(share) * (1 + max(-0.5, min(growth, 1.0))))
            ranked.append({**c, "typology": tid, "typology_name": t["name"],
                           "interac_exposure": t["interac_exposure"], "loss_share": share,
                           "loss_yoy": growth, "priority": priority})
    return sorted(ranked, key=lambda r: r["priority"], reverse=True)


def build_facts(df, tr, channels, intel) -> dict:
    head = trends.headline_numbers(df)

    def pct(x):
        return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(x * 100, 1)

    return {
        "headline_12m": {**head, "loss_millions": round(head["loss"] / 1e6, 1),
                         "senior_loss_share_pct": pct(head["senior_loss_share"])},
        "comparison": f"{tr.attrs['window']} vs {tr.attrs['prev_window']}",
        "typology_figures_cover": f"the 6 months {tr.attrs['window']} only (not the 12-month headline)",
        "window_total_loss_millions": round(tr["loss"].sum() / 1e6, 1),
        "reporting_note": "Total CAFC report volumes have fallen every year since 2021, so falling report counts "
                          "do not necessarily mean less fraud; loss mix and median loss per victim are more reliable. "
                          "Only call growth real when growth_is_robust is true.",
        "typologies": [
            {"name": r["name"], "interac_exposure": r["interac_exposure"],
             "reports": int(r["reports"]), "reports_yoy_pct": pct(r["reports_yoy"]),
             "loss_millions": round(r["loss"] / 1e6, 2), "loss_yoy_pct": pct(r["loss_yoy"]),
             "share_of_window_losses_pct": pct(r["loss"] / tr["loss"].sum()),
             "loss_yoy_excluding_top3_reports_pct": pct(r["loss_ex_top3_yoy"]),
             "growth_is_robust": bool(r["robust_growth"]),
             "median_loss_per_victim": round(r["median_loss"]), "median_loss_prev": round(r["median_loss_prev"]),
             "senior_loss_share_pct": pct(r["senior_loss_share"])}
            for _, r in tr.iterrows()
        ],
        "channel_shift_pts": {k: round(v, 1) for k, v in channels["change_pts"].items()},
        "bulletins": {
            "documents_analysed": intel["n_docs"],
            "documents_naming_interac": len(intel["interac_docs"]),
            "top_payment_methods": intel["payment_methods"][:8],
            "recent_tactics_2025_on": intel["recent_tactics"][:8],
        },
    }


WRITER_SYSTEM = (
    "You write concise fraud intelligence for a Canadian payments network's Fraud Strategy leadership. "
    "Plain, confident, specific: short sentences an executive can read in 10 seconds. "
    "Use ONLY numbers present in the facts JSON; never add, divide or otherwise compute new figures, "
    "and never mix the 12-month headline with the 6-month typology figures. If a number isn't in the facts, leave it out. "
    "Format money like $15.6M or $32K and percentages as whole numbers (+336%). "
    "Do not claim causes the facts don't show; say 'suggests' when inferring. "
    "Typologies with $0 losses record reports only (losses land in other categories); never cite their loss figures. "
    "Reply with JSON only."
)


def write_prose(facts: dict, recs: list[dict]) -> dict:
    prompt = f"""Facts (CAFC reports, Canada only; reported fraud is a small share of actual fraud):
{json.dumps(facts, indent=1, default=str)}

Top-ranked candidate controls (already chosen by a scoring model; do not reorder):
{json.dumps([{k: r[k] for k in ('typology_name', 'stage', 'control', 'owner', 'effort', 'cost', 'impact', 'interac_exposure')} for r in recs], indent=1)}

Write JSON:
{{
  "bottom_line": "2 short sentences (max 45 words total): the single most important takeaway for an Interac fraud strategy leader",
  "key_judgements": ["4 bullets, each one sentence with a specific number from the facts"],
  "watch_list": ["2-3 bullets on emerging tactics from the bulletins worth monitoring, one sentence each: what the tactic is and which typologies it could affect; no claims about demographics or causes"],
  "recommendation_rationales": ["one 1-2 sentence 'why this, why now' per control above, in the same order, citing the numbers"]
}}"""
    return chat_json(prompt, system=WRITER_SYSTEM, max_tokens=1800)


# ---------- charts ----------

def loss_bar_chart(tr, width=6.8 * inch, height=3.0 * inch) -> Drawing:
    data = tr.sort_values("loss").tail(10)
    d = Drawing(width, height)
    ch = HorizontalBarChart()
    ch.x, ch.y, ch.width, ch.height = 2.3 * inch, 0.25 * inch, width - 2.6 * inch, height - 0.4 * inch
    ch.data = [[v / 1e6 for v in data["loss"]]]
    ch.categoryAxis.categoryNames = [n if len(n) < 38 else n[:36] + "…" for n in data["name"]]
    ch.categoryAxis.labels.fontName, ch.categoryAxis.labels.fontSize = "Helvetica", 7.5
    ch.categoryAxis.labels.fillColor = INK
    ch.categoryAxis.strokeColor = RULE
    ch.valueAxis.labels.fontSize = 7
    ch.valueAxis.labels.fillColor = MUTED
    ch.valueAxis.strokeColor = RULE
    ch.valueAxis.valueMin = 0
    ch.valueAxis.labelTextFormat = "$%dM"
    ch.bars.strokeColor = None
    ch.barWidth = 9
    for i, exp in enumerate(data["interac_exposure"]):
        ch.bars[(0, i)].fillColor = EXPOSURE_COLOR[exp]
    d.add(ch)
    return d


def monthly_line_chart(series, names, width=6.8 * inch, height=2.4 * inch) -> Drawing:
    d = Drawing(width, height)
    lp = LinePlot()
    lp.x, lp.y, lp.width, lp.height = 0.5 * inch, 0.35 * inch, width - 2.6 * inch, height - 0.5 * inch
    cols = list(series.columns)
    lp.data = [[(i, float(series[c].iloc[i])) for i in range(len(series))] for c in cols]
    for i, _ in enumerate(cols):
        lp.lines[i].strokeColor = SERIES_COLORS[i % len(SERIES_COLORS)]
        lp.lines[i].strokeWidth = 1.6
    months = [str(m) for m in series.index]
    lp.xValueAxis.valueSteps = list(range(0, len(months), 6))
    lp.xValueAxis.labelTextFormat = lambda v: months[int(v)] if int(v) < len(months) else ""
    lp.xValueAxis.labels.fontSize = 6.5
    lp.xValueAxis.labels.fillColor = MUTED
    lp.yValueAxis.labels.fontSize = 7
    lp.yValueAxis.labels.fillColor = MUTED
    lp.yValueAxis.labelTextFormat = "$%dM"
    lp.yValueAxis.valueMin = 0
    lp.xValueAxis.strokeColor = lp.yValueAxis.strokeColor = RULE
    d.add(lp)
    for i, c in enumerate(cols):  # legend
        y = height - 0.4 * inch - i * 14
        d.add(String(width - 1.95 * inch, y, "■", fillColor=SERIES_COLORS[i % 4], fontSize=10))
        d.add(String(width - 1.8 * inch, y, names[c].split(" (")[0][:34], fillColor=INK, fontSize=7, fontName="Helvetica"))
    return d


# ---------- PDF ----------

def _styles():
    ss = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("t", parent=ss["Title"], fontName="Helvetica-Bold", fontSize=19, leading=23, textColor=INK, alignment=0, spaceAfter=2),
        "sub": ParagraphStyle("s", fontName="Helvetica", fontSize=9, textColor=MUTED, spaceAfter=10),
        "h": ParagraphStyle("h", fontName="Helvetica-Bold", fontSize=11.5, textColor=INK, spaceBefore=10, spaceAfter=5),
        "body": ParagraphStyle("b", fontName="Helvetica", fontSize=9, leading=12.5, textColor=INK),
        "bl": ParagraphStyle("bl", fontName="Helvetica-Bold", fontSize=10.5, leading=14.5, textColor=INK, backColor=colors.HexColor("#fbf3dc"), borderPadding=8, spaceAfter=10, spaceBefore=4),
        "bullet": ParagraphStyle("bu", fontName="Helvetica", fontSize=9, leading=12.5, textColor=INK, leftIndent=10, bulletIndent=0, spaceAfter=3),
        "small": ParagraphStyle("sm", fontName="Helvetica", fontSize=7.5, leading=10, textColor=MUTED),
        "cell": ParagraphStyle("c", fontName="Helvetica", fontSize=7.8, leading=10, textColor=INK),
        "cellb": ParagraphStyle("cb", fontName="Helvetica-Bold", fontSize=7.8, leading=10, textColor=INK),
    }


def _table(rows, widths, header_bg=INK):
    t = Table(rows, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), header_bg), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 7.8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 1), (-1, -1), 0.4, RULE),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def _fmt_pct(x):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "n/a"
    return f"{x * 100:+.0f}%"


def _level(n):
    return {1: "Low", 2: "Med", 3: "High"}[n]


def build_pdf(path, df, tr, channels, intel, prose, recs, series, facts):
    s = _styles()
    head = facts["headline_12m"]
    story = []
    on_page = _footer(head["data_through"])

    # Page 1: bottom line + key judgements + where the money goes
    story += [
        Paragraph("Canadian Payment Scam Intelligence Brief", s["title"]),
        Paragraph(f"Data through {head['data_through']} · CAFC Fraud Reporting System + {intel['n_docs']} CAFC bulletins · "
                  f"Prepared {date.today():%B %d, %Y} · Independent analysis of public data", s["sub"]),
        Paragraph(prose["bottom_line"], s["bl"]),
    ]
    kpis = [["Reports (12 mo)", "Victim reports", "Reported losses", "Losses: victims 60+"],
            [f"{head['reports']:,}", f"{head['victims']:,}", f"${head['loss_millions']:,.0f}M", f"{head['senior_loss_share_pct']:.0f}%"]]
    kt = Table(kpis, colWidths=[1.7 * inch] * 4)
    kt.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica"), ("FONTSIZE", (0, 0), (-1, 0), 7.5), ("TEXTCOLOR", (0, 0), (-1, 0), MUTED),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"), ("FONTSIZE", (0, 1), (-1, 1), 16), ("TEXTCOLOR", (0, 1), (-1, 1), INK),
        ("LINEABOVE", (0, 0), (-1, 0), 2, ACCENT), ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 1), (-1, 1), 8),
    ]))
    story += [kt, Paragraph(f"Period: {head['period']}.", s["small"]), Paragraph("Key judgements", s["h"])]
    story += [Paragraph(k, s["bullet"], bulletText="•") for k in prose["key_judgements"]]
    story += [
        Paragraph("Where reported losses concentrate (last 12 months)", s["h"]),
        loss_bar_chart(trends.typology_trends(df, months=12)),
        Paragraph('Bar colour = likely Interac exposure: <font color="#b4441f">■ High</font>  '
                  '<font color="#d4a017">■ Medium</font>  <font color="#9aa3ad">■ Low</font>. '
                  "Exposure is an analyst judgement of how often the scam's money moves over e-Transfer/debit rather than crypto, cards or gift cards.", s["small"]),
        PageBreak(),
    ]

    # Page 2: what's growing
    story.append(Paragraph(f"What's growing: {facts['comparison']} (same months a year earlier)", s["h"]))
    rows = [["Typology", "Interac exp.", "Reports", "Rpts YoY", "Losses", "Losses YoY", "Median loss", "60+ share"]]
    for _, r in tr.iterrows():
        loss_yoy = _fmt_pct(r["loss_yoy"]) + ("" if r["robust_growth"] or not (r["loss_yoy"] >= 0.2) else "*")
        median = "n/a" if not r["median_loss"] else f"${r['median_loss'] / 1e3:,.1f}K"
        rows.append([Paragraph(r["name"], s["cell"]), r["interac_exposure"], f"{int(r['reports']):,}",
                     _fmt_pct(r["reports_yoy"]), f"${r['loss'] / 1e6:,.1f}M", loss_yoy, median,
                     "n/a" if math.isnan(r["senior_loss_share"]) else f"{r['senior_loss_share'] * 100:.0f}%"])
    t = _table(rows, [2.2 * inch, 0.7 * inch, 0.6 * inch, 0.65 * inch, 0.65 * inch, 0.7 * inch, 0.75 * inch, 0.65 * inch])
    for i, (_, r) in enumerate(tr.iterrows(), start=1):
        if r["robust_growth"]:
            t.setStyle(TableStyle([("TEXTCOLOR", (5, i), (5, i), EXPOSURE_COLOR["High"]), ("FONTNAME", (5, i), (5, i), "Helvetica-Bold"),
                                   ("BACKGROUND", (0, i), (-1, i), colors.HexColor("#fbf3dc"))]))
    story += [t, Paragraph("Highlighted rows: loss growth of 20%+ that still holds after removing each period's 3 largest reports. "
                           "* = growth driven by a few very large reports; treat with caution. Report counts are falling across "
                           "almost all categories as overall CAFC volumes decline, so median loss and mix are the better signals.",
                           s["small"]), Spacer(1, 6)]
    names = {tid: TYPOLOGY_BY_ID[tid]["name"] for tid in series.columns}
    story += [Paragraph("Monthly reported losses, largest High-exposure typologies", s["h"]),
              monthly_line_chart(series, names, height=1.9 * inch)]

    ch_rows = [["How scammers make contact", "Share now", "vs year ago"]]
    for name, r in channels.head(6).iterrows():
        ch_rows.append([name, f"{r['share'] * 100:.0f}%", f"{r['change_pts']:+.1f} pts"])
    left = _table(ch_rows, [1.75 * inch, 0.7 * inch, 0.85 * inch])
    wl = [Paragraph("Watch list (from bulletins)", s["cellb"])] + [Paragraph("• " + w, s["cell"]) for w in prose["watch_list"]]
    right = Table([[p] for p in wl], colWidths=[3.2 * inch])
    right.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    story += [Spacer(1, 6), Table([[left, right]], colWidths=[3.65 * inch, 3.3 * inch], style=[("VALIGN", (0, 0), (-1, -1), "TOP")]),
              PageBreak()]

    # Page 3: kill chain + recommendations
    story.append(Paragraph("The Payment Scam Kill Chain: where each scam can be broken", s["h"]))
    story.append(Paragraph(" → ".join(f"<b>{n}</b>" for _, n, _ in KILL_CHAIN) +
                           ". Each scam passes through these stages; a control at any stage breaks the chain. "
                           "Controls nearer the payment stage are where a payments network has the most direct leverage.", s["body"]))
    story.append(Spacer(1, 5))
    kc = [["Typology"] + [n for _, n, _ in KILL_CHAIN]]
    for tid in tr.index:
        t = TYPOLOGY_BY_ID[tid]
        if not t["controls"]:
            continue
        cells = {k: [] for k, _, _ in KILL_CHAIN}
        for c in t["controls"]:
            cells[c["stage"]].append(c["control"])
        kc.append([Paragraph(f"<b>{t['name']}</b>", s["cell"])] +
                  [Paragraph("<br/>".join("• " + x for x in cells[k]), s["cell"]) for k, _, _ in KILL_CHAIN])
    story += [_table(kc, [1.35 * inch] + [1.13 * inch] * 5), Spacer(1, 4)]

    story.append(Paragraph("Recommendations", s["h"]))
    rec_rows = [["#", "Recommendation", "Stage", "Effort", "Cost", "Impact"]]
    for i, (r, why) in enumerate(zip(recs, prose["recommendation_rationales"]), start=1):
        rec_rows.append([str(i), Paragraph(f"<b>{r['control']}</b> ({r['typology_name']}; owner: {r['owner']})<br/>"
                                           f"<font color='#5b6470'>{why}</font>", s["cell"]),
                         STAGE_NAMES[r["stage"]], _level(r["effort"]), _level(r["cost"]), _level(r["impact"])])
    story.append(KeepTogether(_table(rec_rows, [0.25 * inch, 4.25 * inch, 0.85 * inch, 0.5 * inch, 0.5 * inch, 0.5 * inch], header_bg=colors.HexColor("#7a5c00"))))
    story += [
        Spacer(1, 8),
        Paragraph("<b>Method and caveats.</b> Trends use the CAFC Fraud Reporting System open dataset (Canada only); the CAFC "
                  "estimates only a small fraction of fraud is reported, so figures show direction and mix, not totals. Recent "
                  "months may rise as late reports arrive. Typology mapping, Interac exposure and effort/cost/impact scores are "
                  "analyst judgements, documented in the project's taxonomy file. Recommendations are ranked by "
                  "(impact ÷ effort+cost) × exposure × √loss share × growth. Bulletin facts were extracted with Claude and "
                  "link back to source pages. Control ideas are candidates for discussion, not claims about current practice.",
                  s["small"]),
    ]

    doc = SimpleDocTemplate(str(path), pagesize=letter, leftMargin=0.75 * inch, rightMargin=0.75 * inch,
                            topMargin=0.6 * inch, bottomMargin=0.6 * inch, title="Canadian Payment Scam Intelligence Brief")
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)


def _footer(data_through):
    def draw(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(ACCENT)
        canvas.rect(0, letter[1] - 6, letter[0], 6, stroke=0, fill=1)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(MUTED)
        canvas.drawString(0.75 * inch, 0.35 * inch, f"Scam Intelligence Brief · data through {data_through} · public sources only")
        canvas.drawRightString(letter[0] - 0.75 * inch, 0.35 * inch, f"{doc.page}")
        canvas.restoreState()
    return draw


def generate(n_recs: int = 3) -> Path:
    df = trends.load()
    tr = trends.typology_trends(df, months=6)
    channels = trends.channel_shift(df)
    intel = summarize(load_extracted())
    ranked = rank_controls(tr)
    recs, seen = [], set()
    for r in ranked:  # at most one recommendation per typology
        if r["typology"] not in seen:
            recs.append(r)
            seen.add(r["typology"])
        if len(recs) == n_recs:
            break
    top_high = [t for t in tr.index if TYPOLOGY_BY_ID[t]["interac_exposure"] == "High"][:4]
    series = trends.monthly_series(df, top_high)
    facts = build_facts(df, tr, channels, intel)
    prose = write_prose(facts, recs)

    OUT_DIR.mkdir(exist_ok=True)
    stamp = facts["headline_12m"]["data_through"]
    (OUT_DIR / f"facts-{stamp}.json").write_text(json.dumps({"facts": facts, "recommendations": recs, "prose": prose},
                                                            indent=2, default=str), encoding="utf-8")
    path = OUT_DIR / f"scam-intel-brief-{stamp}.pdf"
    build_pdf(path, df, tr, channels, intel, prose, recs, series, facts)
    return path
