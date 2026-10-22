"""The Payment Scam Kill Chain and the scam typologies mapped onto it.

Every authorized-push-payment scam moves through the same five stages.
The point of the taxonomy is to ask, for each scam: at which stage could
the payment ecosystem (network, banks, telcos, platforms) break the chain,
and what would that cost?

Effort / cost / impact are scored 1 (low) to 3 (high). They are my own
judgement calls, written so they can be argued with - not industry figures.
Control ideas are candidates for discussion, not claims about what any
organization does today.
"""

KILL_CHAIN = [
    ("contact", "Contact", "Scammer reaches the victim (call, text, social media, marketplace, email)."),
    ("pretext", "Pretext", "Story that creates trust or urgency (bank, police, romance, job, investment)."),
    ("payment", "Payment request", "Victim is told to pay: e-Transfer, debit, crypto ATM, gift cards, wire, cash."),
    ("movement", "Fund movement", "Money lands in a mule or scammer-controlled account and is moved on."),
    ("cashout", "Cash-out", "Funds leave the regulated system (crypto, cash, overseas wire)."),
]
STAGE_NAMES = {key: name for key, name, _ in KILL_CHAIN}

# Interac exposure: how directly the scam's money is likely to flow over
# Interac rails (e-Transfer / debit) rather than crypto, cards or gift cards.
TYPOLOGIES = [
    {
        "id": "bank_investigator",
        "name": "Bank investigator / impersonation",
        "cafc_categories": ["Bank Investigator", "Spoofing"],
        "summary": "Caller poses as the victim's bank or police, says the account is compromised, and talks the victim into moving money to a 'safe' account or handing over card/OTP.",
        "contact": ["Direct call", "Text message"],
        "rails": ["Interac e-Transfer", "Debit card handover", "Crypto ATM", "Cash courier"],
        "interac_exposure": "High",
        "controls": [
            {"stage": "contact", "control": "Telco caller-ID authentication + bank number spoof blocking", "owner": "Telcos / FIs", "effort": 3, "cost": 3, "impact": 3},
            {"stage": "payment", "control": "Scam-specific in-flow warning when a first-time payee is added shortly after an inbound call ('Your bank will never ask you to move money')", "owner": "FIs / network", "effort": 2, "cost": 1, "impact": 2},
            {"stage": "movement", "control": "Shared mule-account signals across institutions on the receiving side", "owner": "Network / FIs", "effort": 3, "cost": 2, "impact": 3},
        ],
    },
    {
        "id": "emergency_grandparent",
        "name": "Emergency / grandparent scam",
        "cafc_categories": ["Emergency (Jail, Accident, Hospital, Help)"],
        "summary": "A 'grandchild', lawyer or officer says a relative is in jail or hospital and needs bail money now; cash is often collected by courier.",
        "contact": ["Direct call"],
        "rails": ["Cash courier", "Interac e-Transfer"],
        "interac_exposure": "Medium",
        "controls": [
            {"stage": "pretext", "control": "Family 'safe word' public awareness campaigns aimed at seniors", "owner": "Network / FIs / police", "effort": 1, "cost": 1, "impact": 2},
            {"stage": "payment", "control": "Branch / ATM teller scripts for large unusual cash withdrawals by seniors", "owner": "FIs", "effort": 2, "cost": 2, "impact": 2},
        ],
    },
    {
        "id": "investment_crypto",
        "name": "Investment / crypto scam (incl. pig butchering)",
        "cafc_categories": ["Investments", "Pyramid"],
        "summary": "Fake trading platforms, deepfake celebrity ads and long-con 'relationship' grooming that ends in ever-larger deposits.",
        "contact": ["Internet-social network", "Internet", "Text message"],
        "rails": ["Crypto exchange", "Crypto ATM", "Wire", "Interac e-Transfer to 'onboarding agent'"],
        "interac_exposure": "Medium",
        "controls": [
            {"stage": "contact", "control": "Takedown pipeline for deepfake investment ads with platforms", "owner": "Platforms / regulators", "effort": 2, "cost": 2, "impact": 2},
            {"stage": "payment", "control": "Risk flag on repeated escalating transfers to crypto on-ramps", "owner": "FIs", "effort": 2, "cost": 2, "impact": 3},
            {"stage": "cashout", "control": "Faster freeze/recall coordination with Canadian crypto exchanges", "owner": "Exchanges / police", "effort": 3, "cost": 2, "impact": 2},
        ],
    },
    {
        "id": "romance",
        "name": "Romance scam",
        "cafc_categories": ["Romance"],
        "summary": "Online relationship built over weeks or months, followed by requests for travel, medical or investment money.",
        "contact": ["Internet-social network", "Internet"],
        "rails": ["Interac e-Transfer", "Wire", "Gift cards", "Crypto"],
        "interac_exposure": "Medium",
        "controls": [
            {"stage": "payment", "control": "Pattern flag: repeated sends to one new payee with escalating amounts", "owner": "FIs / network", "effort": 2, "cost": 1, "impact": 2},
            {"stage": "pretext", "control": "Dating-platform warnings when users move conversation off-platform", "owner": "Platforms", "effort": 2, "cost": 1, "impact": 1},
        ],
    },
    {
        "id": "merchandise_marketplace",
        "name": "Marketplace / merchandise (non-delivery)",
        "cafc_categories": ["Merchandise", "Counterfeit Merchandise"],
        "summary": "Buyer pays up-front for goods, pets, rentals or tickets that never arrive or are fake; common on social marketplaces.",
        "contact": ["Internet-social network", "Internet"],
        "rails": ["Interac e-Transfer", "Credit card"],
        "interac_exposure": "High",
        "controls": [
            {"stage": "payment", "control": "Recipient-name display / confirmation before sending to a new payee", "owner": "Network / FIs", "effort": 2, "cost": 2, "impact": 3},
            {"stage": "movement", "control": "Velocity signals on recipient accounts receiving many first-time payments", "owner": "Network / FIs", "effort": 2, "cost": 2, "impact": 3},
        ],
    },
    {
        "id": "vendor_overpayment",
        "name": "Seller-side / overpayment & fake payment notice",
        "cafc_categories": ["Vendor Fraud", "Fraudulent Cheque"],
        "summary": "Scammer 'buys' from a seller, sends a fake payment email or overpays, then asks for a refund of the difference.",
        "contact": ["Internet-social network", "Email"],
        "rails": ["Interac e-Transfer (refund)", "Fake e-Transfer notification email"],
        "interac_exposure": "High",
        "controls": [
            {"stage": "pretext", "control": "Consumer education: real e-Transfers are deposited through your own bank app, never via an emailed link", "owner": "Network", "effort": 1, "cost": 1, "impact": 2},
            {"stage": "contact", "control": "Brand-impersonation email/domain takedowns for fake payment notices", "owner": "Network", "effort": 1, "cost": 1, "impact": 2},
        ],
    },
    {
        "id": "phishing_takeover",
        "name": "Phishing → account takeover",
        # CAFC records $0 loss on these: the theft shows up later under other categories
        "cafc_categories": ["Phishing", "Personal Info"],
        "summary": "Fake bank, CRA, delivery or e-Transfer messages steal credentials or one-time passcodes, then the scammer drains the account.",
        "contact": ["Text message", "Email"],
        "rails": ["Interac e-Transfer from compromised account", "Card"],
        "interac_exposure": "High",
        "controls": [
            {"stage": "contact", "control": "Brand-impersonation smishing/phishing takedown service", "owner": "Network / FIs", "effort": 1, "cost": 1, "impact": 2},
            {"stage": "payment", "control": "Step-up authentication when a new device adds a payee and sends within minutes", "owner": "FIs", "effort": 2, "cost": 2, "impact": 3},
        ],
    },
    {
        "id": "identity_fraud",
        "name": "Identity fraud (new accounts / loans in victim's name)",
        "cafc_categories": ["Identity Fraud"],
        "summary": "Stolen identity used to open accounts, credit or mule accounts. Most CAFC reports are victims discovering misuse, not sending money.",
        "contact": ["Other/unknown", "Not Available"],
        "rails": ["New deposit accounts (mules)", "Credit products"],
        "interac_exposure": "Medium",
        "controls": [
            {"stage": "movement", "control": "Stronger digital identity verification at account opening to cut synthetic/mule accounts", "owner": "Network (identity) / FIs", "effort": 3, "cost": 3, "impact": 3},
        ],
    },
    {
        "id": "extortion",
        "name": "Extortion (CRA, sextortion, threats)",
        "cafc_categories": ["Extortion"],
        "summary": "Threats of arrest, deportation, tax penalties or leaked images unless the victim pays; often targets newcomers and youth.",
        "contact": ["Direct call", "Internet-social network", "Email"],
        "rails": ["Gift cards", "Crypto ATM", "Interac e-Transfer"],
        "interac_exposure": "Medium",
        "controls": [
            {"stage": "pretext", "control": "Targeted awareness for newcomers and teens ('CRA never demands payment by e-Transfer, gift card or bitcoin')", "owner": "Government / network", "effort": 1, "cost": 1, "impact": 2},
            {"stage": "payment", "control": "Retailer gift-card purchase limits and point-of-sale warnings", "owner": "Retailers", "effort": 2, "cost": 1, "impact": 2},
        ],
    },
    {
        "id": "job_mule",
        "name": "Job scams & money-mule recruitment",
        "cafc_categories": ["Job"],
        "summary": "Fake remote jobs ('task' apps, reshipping, payment processing) that take deposits or turn victims into money mules.",
        "contact": ["Text message", "Internet-social network"],
        "rails": ["Crypto", "Interac e-Transfer (victim receives and forwards funds)"],
        "interac_exposure": "High",
        "controls": [
            {"stage": "movement", "control": "Mule-behaviour detection: new accounts that receive and immediately forward funds", "owner": "Network / FIs", "effort": 2, "cost": 2, "impact": 3},
            {"stage": "contact", "control": "Campus / youth awareness: 'if a job pays you to move money, you are the mule'", "owner": "Network / schools", "effort": 1, "cost": 1, "impact": 2},
        ],
    },
    {
        "id": "service_tech_support",
        "name": "Service & tech-support scams",
        "cafc_categories": ["Service", "Telecom Fraud", "Unauthorized Charge"],
        "summary": "Fake tech support, utility, immigration or subscription services; remote-access tools often lead to account takeover.",
        "contact": ["Direct call", "Internet"],
        "rails": ["Interac e-Transfer", "Gift cards", "Card"],
        "interac_exposure": "Medium",
        "controls": [
            {"stage": "payment", "control": "Detect remote-access software active during a banking session", "owner": "FIs", "effort": 2, "cost": 2, "impact": 2},
        ],
    },
    {
        "id": "advance_fee",
        "name": "Advance fee (prize, loan, grant, inheritance)",
        "cafc_categories": ["Prize", "Loan", "GRANT", "Foreign Money Offer", "Vacation", "Timeshare", "Survey"],
        "summary": "Victim pays an up-front 'fee' or 'tax' to release a prize, loan, grant or inheritance that does not exist.",
        "contact": ["Direct call", "Email", "Mail"],
        "rails": ["Interac e-Transfer", "Gift cards", "Wire"],
        "interac_exposure": "Medium",
        "controls": [
            {"stage": "pretext", "control": "Awareness: legitimate lenders and prizes never require an up-front fee", "owner": "Network / regulators", "effort": 1, "cost": 1, "impact": 1},
        ],
    },
    {
        "id": "recovery",
        "name": "Recovery pitch (re-victimization)",
        "cafc_categories": ["Recovery Pitch", "Collection Agency"],
        "summary": "Prior victims are contacted by fake lawyers, police or 'recovery firms' promising to get money back for a fee.",
        "contact": ["Direct call", "Email", "Internet-social network"],
        "rails": ["Crypto", "Wire", "Interac e-Transfer"],
        "interac_exposure": "Medium",
        "controls": [
            {"stage": "contact", "control": "Proactive outreach to known victims warning about recovery scams", "owner": "FIs / police", "effort": 1, "cost": 1, "impact": 2},
        ],
    },
    {
        "id": "business_email_compromise",
        "name": "Business email compromise & false billing",
        # CAFC "Spear Phishing" = targeted emails impersonating executives/suppliers, i.e. BEC
        "cafc_categories": ["Spear Phishing", "False Billing", "Directory", "Office Supplies"],
        "summary": "Targeted emails impersonating executives or suppliers, fake invoices and changed bank details trick businesses into paying scammers.",
        "contact": ["Email"],
        "rails": ["Wire / EFT", "Interac e-Transfer for Business"],
        "interac_exposure": "Low",
        "controls": [
            {"stage": "payment", "control": "Payee-name check when supplier banking details change", "owner": "FIs / network", "effort": 2, "cost": 2, "impact": 3},
        ],
    },
    {
        "id": "charity_other",
        "name": "Charity, psychic & other",
        "cafc_categories": ["Charity / Donation", "Psychics", "Health", "Credit Card", "Modem-Hijacking"],
        "summary": "Smaller categories grouped for reporting.",
        "contact": ["Various"],
        "rails": ["Various"],
        "interac_exposure": "Low",
        "controls": [],
    },
]

UNMAPPED = {"Other", "Unknown", "Incomplete"}

CATEGORY_TO_TYPOLOGY = {cat: t["id"] for t in TYPOLOGIES for cat in t["cafc_categories"]}
TYPOLOGY_BY_ID = {t["id"]: t for t in TYPOLOGIES}


def control_score(c: dict) -> float:
    """Simple priority: impact earned per unit of effort + cost."""
    return round(c["impact"] * 2 / (c["effort"] + c["cost"]), 2)
