"""Trend analysis on the CAFC Fraud Reporting System open dataset.

The dataset (open.canada.ca) has one row per report: date, category,
solicitation method, victim age, province, and dollar loss. We map each
CAFC category onto our typologies and look for what is growing.

Caveat carried into the brief: the CAFC estimates only a small share of
fraud is ever reported, so these are signals about direction and mix,
not totals.
"""
from pathlib import Path

import pandas as pd

from .taxonomy import CATEGORY_TO_TYPOLOGY, TYPOLOGY_BY_ID, UNMAPPED

ROOT = Path(__file__).resolve().parent.parent
RAW_CSV = ROOT / "data" / "raw" / "cafc.csv"
CLEAN = ROOT / "data" / "cafc_clean.pkl"

COLUMNS = {  # positional, English columns only
    1: "date", 2: "received_via", 4: "country", 6: "province", 8: "category",
    10: "solicitation", 12: "gender", 16: "age_range", 17: "complaint_type",
    19: "victims", 20: "loss",
}
SENIOR_AGES = {"60 - 69", "70 - 79", "80 - 89", "90 - 99", "100 +"}


def load(rebuild: bool = False) -> pd.DataFrame:
    if CLEAN.exists() and not rebuild:
        return pd.read_pickle(CLEAN)
    raw = pd.read_csv(RAW_CSV, encoding="cp1252", low_memory=False)
    df = raw.iloc[:, list(COLUMNS)].copy()
    df.columns = list(COLUMNS.values())
    # object array + cache=False: pandas 3 segfaults on Windows mapping arrow strings here
    df["date"] = pd.to_datetime(df["date"].to_numpy(dtype=object), format="%Y-%m-%d",
                                errors="coerce", cache=False)
    df["month"] = df["date"].dt.to_period("M")
    df["age_range"] = df["age_range"].str.lstrip("'")
    df["loss"] = pd.to_numeric(df["loss"].str.replace(r"[$,]", "", regex=True), errors="coerce").fillna(0.0)
    df["typology"] = df["category"].map(CATEGORY_TO_TYPOLOGY).fillna("unmapped")
    df.loc[df["category"].isin(UNMAPPED), "typology"] = "unmapped"
    df["is_victim"] = df["complaint_type"].eq("Victim")
    df["senior"] = df["age_range"].isin(SENIOR_AGES)
    df = df[df["country"].eq("Canada") & df["date"].notna()]
    df.to_pickle(CLEAN)
    return df


def _window(df: pd.DataFrame, end: pd.Period, months: int) -> pd.DataFrame:
    start = end - (months - 1)
    return df[(df["month"] >= start) & (df["month"] <= end)]


def typology_trends(df: pd.DataFrame, months: int = 6) -> pd.DataFrame:
    """Latest N months vs the same N months a year earlier (avoids seasonality)."""
    end = df["month"].max()
    cur, prev = _window(df, end, months), _window(df, end - 12, months)

    def agg(frame):
        g = frame.groupby("typology")
        losses = frame[frame["loss"] > 0].groupby("typology")["loss"]
        return pd.DataFrame({
            "reports": g.size(),
            "victims": g["is_victim"].sum(),
            "loss": g["loss"].sum(),
            # a few huge reports can swing a category; track totals without the top 3 and the median
            "loss_ex_top3": losses.apply(lambda s: s.sum() - s.nlargest(3).sum()),
            "median_loss": losses.median(),
            "senior_loss": frame[frame["senior"]].groupby("typology")["loss"].sum(),
        }).fillna(0)

    def yoy(col):
        return out[col] / out[f"{col}_prev"].where(out[f"{col}_prev"] > 0) - 1

    c, p = agg(cur), agg(prev)
    out = c.join(p, rsuffix="_prev", how="outer").fillna(0)
    out["reports_yoy"] = yoy("reports")
    out["loss_yoy"] = yoy("loss")
    out["loss_ex_top3_yoy"] = yoy("loss_ex_top3")
    out["median_loss_yoy"] = yoy("median_loss")
    # growth counts as robust only if it survives dropping the 3 largest reports
    out["robust_growth"] = (out["loss_yoy"] >= 0.2) & (out["loss_ex_top3_yoy"] >= 0.2)
    out["senior_loss_share"] = out["senior_loss"] / out["loss"].where(out["loss"] > 0)
    out["loss_per_victim"] = out["loss"] / out["victims"].where(out["victims"] > 0)
    out = out.drop(index="unmapped", errors="ignore")
    out["name"] = [TYPOLOGY_BY_ID[i]["name"] for i in out.index]
    out["interac_exposure"] = [TYPOLOGY_BY_ID[i]["interac_exposure"] for i in out.index]
    out.attrs["window"] = f"{end - (months - 1)} to {end}"
    out.attrs["prev_window"] = f"{end - 12 - (months - 1)} to {end - 12}"
    return out.sort_values("loss", ascending=False)


def monthly_series(df: pd.DataFrame, typology_ids: list[str]) -> pd.DataFrame:
    """Monthly victim losses per typology (in $ millions)."""
    sub = df[df["typology"].isin(typology_ids)]
    return (sub.pivot_table(index="month", columns="typology", values="loss", aggfunc="sum")
            .fillna(0) / 1e6)


def channel_shift(df: pd.DataFrame, months: int = 6) -> pd.DataFrame:
    """How scammers are reaching victims now vs a year ago (share of reports)."""
    end = df["month"].max()
    known = df[~df["solicitation"].isin(["Other/unknown", "Not Available"])]
    cur = _window(known, end, months)["solicitation"].value_counts(normalize=True)
    prev = _window(known, end - 12, months)["solicitation"].value_counts(normalize=True)
    out = pd.DataFrame({"share": cur, "share_prev": prev}).fillna(0)
    out["change_pts"] = (out["share"] - out["share_prev"]) * 100
    return out.sort_values("share", ascending=False)


def headline_numbers(df: pd.DataFrame, months: int = 12) -> dict:
    end = df["month"].max()
    cur = _window(df, end, months)
    return {
        "period": f"{end - (months - 1)} to {end}",
        "reports": int(len(cur)),
        "victims": int(cur["is_victim"].sum()),
        "loss": float(cur["loss"].sum()),
        "senior_loss_share": float(cur.loc[cur["senior"], "loss"].sum() / cur["loss"].sum()),
        "data_through": str(end),
    }
