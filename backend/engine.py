from __future__ import annotations

import json
import os
import re
from datetime import date, timedelta

from openai import OpenAI

from skills import resume_skill_hits


DEFAULT_BASE_URL = "https://api.ifm.ai/v1"
DEFAULT_MODEL = "IFM/K2-Horizon-375B-A23B"
DEFAULT_HORIZON_WEEKS = 12


def planner(payload: dict) -> dict:
    top_skills = payload["top_skills"]
    resume_text = payload.get("resume_text") or ""
    horizon = max(1, _to_int(payload.get("horizon_weeks"), DEFAULT_HORIZON_WEEKS))
    hits = resume_skill_hits(resume_text, [s["skill"] for s in top_skills])

    ai_plan = None
    error = None
    try:
        ai_plan = _call_model(payload, hits, horizon)
    except Exception as exc:  # noqa: BLE001 — demo fallback
        error = str(exc)[:300]

    if not ai_plan:
        ai_plan = _fallback_plan(payload, hits, horizon)

    events = _normalize_events(ai_plan.get("events") or [], horizon)
    ratings = _merge_ratings(
        top_skills,
        hits,
        ai_plan.get("skill_ratings") or [],
        payload.get("job_count", 0),
    )
    summary = (ai_plan.get("summary") or "").strip() or _fallback_summary(payload, ratings)

    return {
        "summary": summary,
        "events": events,
        "skills": ratings,
        "job_count": payload.get("job_count", 0),
        "warning": error,
    }


def _client() -> OpenAI:
    api_key = os.environ.get("IFM_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing IFM_API_KEY")
    return OpenAI(
        base_url=os.environ.get("IFM_BASE_URL", DEFAULT_BASE_URL),
        api_key=api_key,
        timeout=240,
    )


def _call_model(payload: dict, hits: dict, horizon: int) -> dict:
    skill_lines = "\n".join(
        f"- {s['skill']}: mentioned in {s['mention_count']} of {payload.get('job_count', '?')} job descriptions; "
        f"resume mentions it: {'yes' if hits.get(s['skill']) else 'no'}"
        for s in payload["top_skills"]
    )
    target_preference = payload.get("target_preference") or {}
    preference_type = target_preference.get("type", "not specified")
    preference_value = target_preference.get("value", "not specified")
    mapped_industry = target_preference.get("industry") or "not mapped"
    prompt = f"""You are a career coach. Build a {horizon}-week learning plan.

Target job: {payload.get('desired_job') or 'not specified'}
Industry / Company preference type: {preference_type}
Industry / Company preference: {preference_value}
Mapped industry: {mapped_industry}
Specific job notes / JD:
{payload.get('specific_job') or '(none)'}

Resume:
{payload.get('resume_text')[:8000]}

Top skills by JD mention count:
{skill_lines}

Return ONLY valid JSON with this shape:
{{
  "summary": "Concise 1-2 sentence gap analysis and priority overview",
  "events": [
    {{
      "event": "short title",
      "stage": "Foundation|Build|Portfolio|Interview",
      "priority": 1,
      "start_week": 0,
      "end_week": 2,
      "details": "what to study this block",
      "resources": [{{"title": "resource name", "url": "https://..."}}]
    }}
  ],
  "skill_ratings": [
    {{"skill": "Python", "rating": 62}}
  ]
}}

Rules:
- Keep the summary concise: no more than 2 sentences, focusing only on the most important strengths, gaps, and learning priority.
- If the preference type is company, tailor examples and interview preparation to that company's likely role expectations.
- If the preference type is industry, tailor domain knowledge, projects, and terminology to that industry; do not treat it as a company name.
- If the preference type is "industry or company preference", use it as context but do not invent company-specific requirements.
- 6 to 10 events covering {horizon} weeks.
- priority is 1-10, higher = more urgent / important.
- start_week/end_week are integers 0-{horizon}, end_week > start_week.
- Sequence dependent skills so prerequisites finish before projects that use them. Independent topics may overlap.
- skill_ratings must include exactly these skills: {[s['skill'] for s in payload['top_skills']]}
- rating is 0-100 based on the resume evidence.
- Resources should be real, well-known public URLs when possible.
"""
    client = _client()
    model = os.environ.get("IFM_MODEL", DEFAULT_MODEL)
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
    )
    content = resp.choices[0].message.content or ""
    return _parse_json(content)


def _parse_json(text: str) -> dict:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    text = text.split("</think>")[-1].strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.S)
    if fenced:
        text = fenced.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    return json.loads(text)


def _fallback_plan(payload: dict, hits: dict, horizon: int) -> dict:
    skills = payload["top_skills"]
    job = payload.get("desired_job") or "the target role"
    events = []
    week = 0
    stages = ["Foundation", "Build", "Portfolio", "Interview"]
    for i, item in enumerate(skills):
        name = item["skill"]
        span = min(horizon, 2 if i < 3 else 3)
        events.append(
            {
                "event": f"Level up {name}",
                "stage": stages[min(i, len(stages) - 1)],
                "priority": 10 - i,
                "start_week": week,
                "end_week": min(horizon, week + span),
                "details": (
                    f"Close the gap on {name} for {job}. "
                    "Work through one structured course, then apply it in a small project."
                ),
                "resources": _default_resources(name),
            }
        )
        week = min(max(0, horizon - 2), week + 2)
    events.append(
        {
            "event": "Portfolio + mock interviews",
            "stage": "Interview",
            "priority": 8,
            "start_week": max(0, horizon - 3),
            "end_week": horizon,
            "details": "Ship one public project that showcases the top skills, then run weekly mock interviews.",
            "resources": [
                {"title": "Interviewing.io", "url": "https://interviewing.io/"},
                {"title": "Pramp", "url": "https://www.pramp.com/"},
            ],
        }
    )
    ratings = [
        {
            "skill": s["skill"],
            "rating": 68 if hits.get(s["skill"]) else 28,
        }
        for s in skills
    ]
    return {"summary": "", "events": events, "skill_ratings": ratings}


def _default_resources(skill: str) -> list[dict]:
    catalog = {
        "Python": [{"title": "Python Official Tutorial", "url": "https://docs.python.org/3/tutorial/"}],
        "SQL": [{"title": "Mode SQL Tutorial", "url": "https://mode.com/sql-tutorial/"}],
        "Spark": [{"title": "Spark Programming Guide", "url": "https://spark.apache.org/docs/latest/"}],
        "Machine Learning": [{"title": "scikit-learn User Guide", "url": "https://scikit-learn.org/stable/user_guide.html"}],
        "React": [{"title": "React Docs", "url": "https://react.dev/learn"}],
        "AWS": [{"title": "AWS Skill Builder", "url": "https://skillbuilder.aws/"}],
        "Statistics": [{"title": "Seeing Theory", "url": "https://seeing-theory.brown.edu/"}],
    }
    return catalog.get(
        skill,
        [{"title": f"Search learning path for {skill}", "url": f"https://www.google.com/search?q={skill}+course"}],
    )


def _fallback_summary(payload: dict, ratings: list[dict]) -> str:
    job = payload.get("desired_job") or "your target role"
    weak = [s["skill"] for s in ratings if s["user_rating"] < 50]
    strong = [s["skill"] for s in ratings if s["user_rating"] >= 50]
    bits = [f"Plan aligned to {job} using the most frequently mentioned JD skills."]
    if strong:
        bits.append("Resume already signals: " + ", ".join(strong) + ".")
    if weak:
        bits.append("Priority gaps: " + ", ".join(weak) + ".")
    return " ".join(bits)


def _to_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_events(events: list[dict], horizon: int) -> list[dict]:
    today = date.today()
    cleaned = []
    for item in events:
        if not isinstance(item, dict):
            continue
        start_w = max(0, min(horizon - 1, _to_int(item.get("start_week"), 0)))
        end_w = max(start_w + 1, min(horizon, _to_int(item.get("end_week"), start_w + 2)))
        if end_w <= start_w:
            end_w = start_w + 1
        start = today + timedelta(weeks=start_w)
        end = today + timedelta(weeks=end_w)
        resources = item.get("resources") if isinstance(item.get("resources"), list) else []
        cleaned.append(
            {
                "event": item.get("event") or "Learning block",
                "stage": item.get("stage") or "Foundation",
                "priority": max(1, min(10, _to_int(item.get("priority"), 1))),
                "details": item.get("details") or "",
                "resources": resources,
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "deadline": end.isoformat(),
            }
        )
    cleaned.sort(key=lambda x: (-x["priority"], x["start_date"]))
    return cleaned


def _merge_ratings(
    top_skills: list[dict],
    hits: dict,
    ai_ratings: list[dict],
    job_count: int,
) -> list[dict]:
    by_name = {str(r.get("skill")): r for r in ai_ratings}
    merged = []
    for item in top_skills:
        name = item["skill"]
        ai = by_name.get(name) or {}
        rating = ai.get("rating")
        try:
            rating = max(0, min(100, int(rating)))
        except (TypeError, ValueError):
            rating = 70 if hits.get(name) else 30
        # A JD score is the percentage of matched job descriptions mentioning
        # this skill, so it shares the same 0-100 scale as the resume rating.
        jd_rating = round(100 * item["mention_count"] / job_count) if job_count else 0
        merged.append(
            {
                "skill": name,
                "mention_count": item["mention_count"],
                "jd_rating": min(100, jd_rating),
                "user_rating": rating,
            }
        )
    return merged
