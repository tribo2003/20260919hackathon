from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent / "data" / "job_postings.json"

# The demo job-posting data only stores company names.  Keep the industry
# knowledge here so an "Industry / Company" preference can be used for both
# JD aggregation and the AI prompt.
COMPANY_INDUSTRIES = {
    "Google": "Technology",
    "Meta": "Technology",
    "Amazon": "E-commerce / Cloud",
    "Microsoft": "Technology",
    "Netflix": "Media / Streaming",
    "Snowflake": "Data Cloud",
    "Uber": "Mobility / Marketplace",
    "OpenAI": "AI",
    "Apple": "Consumer Technology",
    "Stripe": "Fintech",
    "Airbnb": "Travel / Marketplace",
    "Shopify": "E-commerce",
    "McKinsey": "Consulting",
    "Spotify": "Media / Streaming",
    "LinkedIn": "Professional Networking",
}

INDUSTRY_ALIASES = {
    "Technology": ("technology", "tech", "software", "saas"),
    "AI": ("ai", "artificial intelligence", "machine learning"),
    "Fintech": ("fintech", "financial technology", "finance", "banking"),
    "E-commerce / Cloud": ("e-commerce", "ecommerce", "cloud"),
    "E-commerce": ("e-commerce", "ecommerce", "retail"),
    "Data Cloud": ("data cloud", "data platform"),
    "Media / Streaming": ("media", "streaming", "entertainment"),
    "Mobility / Marketplace": ("mobility", "transportation", "marketplace", "rideshare"),
    "Travel / Marketplace": ("travel", "hospitality", "marketplace"),
    "Consulting": ("consulting", "consultant"),
    "Consumer Technology": ("consumer technology", "consumer tech"),
    "Professional Networking": ("professional networking", "recruiting", "hr tech"),
}

SKILLS = [
    ("Python", [r"\bpython\b"]),
    ("SQL", [r"\bsql\b"]),
    ("Spark", [r"\bspark\b", r"\bpyspark\b"]),
    ("Airflow", [r"\bairflow\b"]),
    ("Kafka", [r"\bkafka\b"]),
    ("AWS", [r"\baws\b", r"\bsagemaker\b", r"\bredshift\b"]),
    ("Azure", [r"\bazure\b"]),
    ("GCP", [r"\bgcp\b", r"\bbigquery\b"]),
    ("Docker", [r"\bdocker\b"]),
    ("Kubernetes", [r"\bkubernetes\b", r"\bk8s\b"]),
    ("Machine Learning", [r"\bmachine learning\b", r"\bml\b"]),
    ("Deep Learning", [r"\bdeep learning\b"]),
    ("TensorFlow", [r"\btensorflow\b"]),
    ("PyTorch", [r"\bpytorch\b"]),
    ("NLP", [r"\bnlp\b", r"\btransformers\b"]),
    ("Statistics", [r"\bstatistics\b", r"\bcausal inference\b"]),
    ("A/B Testing", [r"\ba/?b testing\b", r"\bexperiment design\b"]),
    ("Tableau", [r"\btableau\b", r"\blooker\b"]),
    ("Excel", [r"\bexcel\b"]),
    ("Java", [r"\bjava\b"]),
    ("C++", [r"\bc\+\+\b"]),
    ("C#", [r"\bc#\b"]),
    ("JavaScript", [r"\bjavascript\b"]),
    ("TypeScript", [r"\btypescript\b"]),
    ("React", [r"\breact\b"]),
    ("CSS", [r"\bcss\b"]),
    ("HTML", [r"\bhtml\b"]),
    ("GraphQL", [r"\bgraphql\b"]),
    ("dbt", [r"\bdbt\b"]),
    ("Snowflake", [r"\bsnowflake\b"]),
    ("ETL", [r"\betl\b", r"\bdata pipelines?\b"]),
    ("Data Modeling", [r"\bdata modeling\b"]),
    ("MLOps", [r"\bmlops\b"]),
    ("System Design", [r"\bsystem design\b", r"\bdistributed systems\b"]),
    ("Communication", [r"\bcommunication\b"]),
]


def load_postings() -> list[dict]:
    with DATA_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def classify_target_preference(preference: str) -> dict[str, str]:
    """Identify whether the optional target is a company or an industry."""
    value = (preference or "").strip()
    normalized = value.lower()
    if not value:
        return {"type": "not specified", "value": "not specified", "industry": ""}

    for company, industry in COMPANY_INDUSTRIES.items():
        if normalized == company.lower():
            return {"type": "company", "value": company, "industry": industry}

    # Prefer exact aliases: "fintech" must not be caught by the shorter
    # "tech" alias for Technology.
    for industry, aliases in INDUSTRY_ALIASES.items():
        if normalized == industry.lower() or normalized in aliases:
            return {"type": "industry", "value": value, "industry": industry}

    for industry, aliases in INDUSTRY_ALIASES.items():
        if any(alias in normalized for alias in aliases):
            return {"type": "industry", "value": value, "industry": industry}

    # Preserve an unfamiliar value instead of guessing; the model can still
    # use it as context even when the local demo data cannot classify it.
    return {"type": "industry or company preference", "value": value, "industry": ""}


def _match_posting(posting: dict, desired_job: str, company: str) -> bool:
    title = (posting.get("title") or "").lower()
    corp = (posting.get("company") or "").lower()
    job = (desired_job or "").strip().lower()
    company = (company or "").strip().lower()

    title_ok = True
    if job:
        tokens = [t for t in re.split(r"\s+", job) if t]
        title_ok = all(t in title or t in (posting.get("description") or "").lower() for t in tokens[:3])
        if not title_ok:
            title_ok = any(t in title for t in tokens)

    company_ok = True if not company else company in corp
    return title_ok and company_ok


def _count_skills(texts: list[str]) -> Counter:
    counts: Counter = Counter()
    for text in texts:
        blob = (text or "").lower()
        for name, patterns in SKILLS:
            if any(re.search(p, blob, flags=re.I) for p in patterns):
                counts[name] += 1
    return counts


def top_skills(
    desired_job: str,
    preference: str = "",
    extra_jd: str = "",
    top_n: int = 10,
) -> tuple[list[dict], int]:
    postings = load_postings()
    by_title = [p for p in postings if _match_posting(p, desired_job, "")]
    preference_info = classify_target_preference(preference)
    if preference_info["type"] == "company":
        by_company = [p for p in by_title if _match_posting(p, desired_job, preference_info["value"])]
        matched = by_company or by_title or postings
    elif preference_info["type"] == "industry":
        by_industry = [
            p for p in by_title
            if COMPANY_INDUSTRIES.get(p.get("company", "")) == preference_info["industry"]
        ]
        matched = by_industry or by_title or postings
    else:
        matched = by_title or postings

    texts = [p.get("description", "") for p in matched]
    if extra_jd.strip():
        texts.append(extra_jd)

    counts = _count_skills(texts)
    ranked = counts.most_common(top_n)
    return (
        [{"skill": name, "mention_count": int(n)} for name, n in ranked],
        len(matched),
    )


def resume_skill_hits(resume_text: str, skills: list[str]) -> dict[str, bool]:
    blob = (resume_text or "").lower()
    found = {}
    lookup = {name: patterns for name, patterns in SKILLS}
    for skill in skills:
        patterns = lookup.get(skill, [rf"\b{re.escape(skill.lower())}\b"])
        found[skill] = any(re.search(p, blob, flags=re.I) for p in patterns)
    return found
