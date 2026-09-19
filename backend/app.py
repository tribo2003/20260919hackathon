from __future__ import annotations

import os
import sys
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import engine
from resume import extract_resume_text
from skills import top_skills

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"

app = Flask(__name__, static_folder=str(FRONTEND), static_url_path="")


def _load_dotenv() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()


@app.get("/")
def index():
    return send_from_directory(FRONTEND, "index.html")


@app.post("/api/plan")
def create_plan():
    desired_job = (request.form.get("desired_job") or "").strip()
    company = (request.form.get("company") or "").strip()
    specific_job = (request.form.get("specific_job") or "").strip()
    resume_text = (request.form.get("resume_text") or "").strip()

    upload = request.files.get("resume")
    if upload and upload.filename:
        raw = upload.read()
        parsed = extract_resume_text(upload.filename, raw).strip()
        if parsed:
            resume_text = parsed if not resume_text else resume_text + "\n" + parsed

    if not desired_job and not specific_job:
        return jsonify({"error": "Please enter a desired job or paste a job description."}), 400
    if not resume_text:
        return jsonify({"error": "Please upload or paste a resume."}), 400

    skills, job_count = top_skills(desired_job or specific_job, company, specific_job)
    result = engine.planner(
        {
            "desired_job": desired_job,
            "company": company,
            "specific_job": specific_job,
            "resume_text": resume_text,
            "top_skills": skills,
            "job_count": job_count,
        }
    )
    return jsonify(result)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
