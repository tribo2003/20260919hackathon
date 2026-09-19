const form = document.getElementById("plan-form");
const statusEl = document.getElementById("form-status");
const greetingTitleEl = document.getElementById("greeting-title");
const summaryEl = document.getElementById("summary-text");
const ganttEl = document.getElementById("gantt-chart");
const detailsEl = document.getElementById("learning-details");
const skillsEl = document.getElementById("skill-rating");
const skillCaption = document.getElementById("skill-caption");
const stageFilter = document.getElementById("stage-filter");
const submitBtn = document.getElementById("generate-plan");

let planState = { events: [], skills: [], selected: null, stage: "all" };

form.addEventListener("submit", async (event) => {
    event.preventDefault();
    setStatus("產生中，請稍候…", false);
    submitBtn.disabled = true;

    const body = new FormData();
    const resumeFile = document.getElementById("resume").files[0];
    const resumeTextInput = document.getElementById("resume-text");
    if (resumeFile) body.append("resume", resumeFile);
    body.append("resume_text", resumeTextInput ? resumeTextInput.value : "");
    body.append("desired_job", document.getElementById("desired-job").value);
    body.append("company", document.getElementById("company").value);
    body.append("specific_job", document.getElementById("specific-job").value);

    try {
        const res = await fetch("/api/plan", { method: "POST", body });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Request failed");

        planState.events = data.events || [];
        planState.skills = data.skills || [];
        planState.selected = planState.events[0] || null;
        planState.stage = "all";

        const candidateName = String(data.candidate_name || "").trim();
        greetingTitleEl.textContent = candidateName
            ? `How can I help you, ${candidateName}?`
            : "How can I help you?";
        summaryEl.textContent = data.summary || "";
        fillStages(planState.events);
        renderAll();
        renderSkills(planState.skills, data.job_count);
        const note = data.warning
            ? `已用備援規則產生計畫（模型呼叫失敗：${data.warning}）`
            : "計畫已更新。";
        setStatus(note, false);
    } catch (err) {
        setStatus(err.message, true);
    } finally {
        submitBtn.disabled = false;
    }
});

stageFilter.addEventListener("change", () => {
    planState.stage = stageFilter.value;
    const visible = visibleEvents();
    if (!visible.includes(planState.selected)) {
        planState.selected = visible[0] || null;
    }
    renderAll();
});

function setStatus(text, isError) {
    statusEl.hidden = !text;
    statusEl.textContent = text;
    statusEl.className = `status ${isError ? "error" : "ok"}`;
}

function fillStages(events) {
    const stages = [...new Set(events.map((e) => e.stage).filter(Boolean))];
    stageFilter.innerHTML = `<option value="all">全部</option>` +
        stages.map((s) => `<option value="${escapeHtml(s)}">${escapeHtml(s)}</option>`).join("");
}

function visibleEvents() {
    if (planState.stage === "all") return planState.events;
    return planState.events.filter((e) => e.stage === planState.stage);
}

function renderAll() {
    renderGantt(visibleEvents(), planState.selected);
    renderDetails(planState.selected);
}

function renderGantt(events, selected) {
    if (!events.length) {
        ganttEl.innerHTML = `<p class="placeholder">這個階段沒有事件。</p>`;
        return;
    }

    const starts = events.map((e) => new Date(e.start_date).getTime());
    const ends = events.map((e) => new Date(e.end_date).getTime());
    const minT = Math.min(...starts);
    const maxT = Math.max(...ends);
    const span = Math.max(maxT - minT, 1);

    const left = 168;
    const top = 28;
    const rowH = 36;
    const width = 920;
    const height = top + events.length * rowH + 28;
    const barW = width - left - 24;

    const ticks = 6;
    let axis = "";
    for (let i = 0; i <= ticks; i += 1) {
        const t = minT + (span * i) / ticks;
        const x = left + (barW * i) / ticks;
        axis += `<line x1="${x}" y1="${top - 8}" x2="${x}" y2="${height - 18}" stroke="#e5e7eb"/>`;
        axis += `<text x="${x}" y="${height - 4}" text-anchor="middle" font-size="11" fill="#6b7280">${fmt(t)}</text>`;
    }

    const rows = events.map((ev, i) => {
        const y = top + i * rowH;
        const x = left + ((new Date(ev.start_date).getTime() - minT) / span) * barW;
        const w = Math.max(8, ((new Date(ev.end_date).getTime() - new Date(ev.start_date).getTime()) / span) * barW);
        const active = selected && selected.event === ev.event && selected.start_date === ev.start_date;
        return `
            <text x="8" y="${y + 16}" font-size="12">${escapeHtml(truncate(ev.event, 22))}</text>
            <rect class="gantt-bar${active ? " active" : ""}" data-idx="${i}"
                  x="${x}" y="${y}" width="${w}" height="22" rx="4"
                  fill="${active ? "#1d4ed8" : "#60a5fa"}"
                  role="button" tabindex="0" aria-label="${escapeAttr(ev.event)}"/>
        `;
    }).join("");

    ganttEl.innerHTML = `
        <svg class="gantt-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="Learning gantt chart">
            <text x="${left}" y="14" font-size="11" fill="#6b7280">時間</text>
            ${axis}
            ${rows}
        </svg>
    `;

    ganttEl.querySelectorAll(".gantt-bar").forEach((bar) => {
        bar.addEventListener("click", () => {
            planState.selected = events[Number(bar.dataset.idx)];
            renderAll();
        });
    });
}

function renderDetails(eventItem) {
    if (!eventItem) {
        detailsEl.innerHTML = `<p class="placeholder">點選甘特圖上的事件，查看該階段學習細項與資源。</p>`;
        return;
    }
    const resources = (eventItem.resources || [])
        .map((r) => `<li><a href="${escapeAttr(r.url)}" target="_blank" rel="noreferrer">${escapeHtml(r.title || r.url)}</a></li>`)
        .join("");
    detailsEl.innerHTML = `
        <div class="detail-block">
            <h3>${escapeHtml(eventItem.event)}</h3>
            <div class="meta">
                <span class="chip">階段：${escapeHtml(eventItem.stage || "-")}</span>
                <span class="chip">優先度：${escapeHtml(String(eventItem.priority))}</span>
                <span class="chip">${escapeHtml(eventItem.start_date)} → ${escapeHtml(eventItem.end_date)}</span>
            </div>
            <p>${escapeHtml(eventItem.details || "")}</p>
            <h4>Resources</h4>
            <ul class="resources">${resources || "<li>無指定資源</li>"}</ul>
        </div>
    `;
}

function renderSkills(skills, jobCount) {
    if (!skills.length) {
        skillsEl.innerHTML = `<p class="placeholder">尚未產生評級。</p>`;
        return;
    }
    skillCaption.textContent = `依 ${jobCount || "相關"} 則職缺 JD 統計：JD average 為該技能出現在職缺中的比例；Your resume 為履歷技能評分（0-100）。`;
    const largestGapSkills = new Set(
        [...skills]
            .sort((a, b) => Math.abs((Number(b.jd_rating) || 0) - (Number(b.user_rating) || 0))
                - Math.abs((Number(a.jd_rating) || 0) - (Number(a.user_rating) || 0)))
            .slice(0, 3)
            .map((skill) => skill.skill),
    );
    skillsEl.innerHTML = skills.map((s) => `
        <div class="bar-row">
            <div class="skill-heading${largestGapSkills.has(s.skill) ? " gap-skill" : ""}">
                <div>${escapeHtml(s.skill)}</div>
                <div class="bar-meta">JD ${escapeHtml(String(s.mention_count))} 次</div>
            </div>
            <div class="skill-bars">
                <div class="bar-series">
                    <span class="bar-label">JD average</span>
                    <div class="bar-track"><div class="bar-fill jd-fill" style="width:${Number(s.jd_rating) || 0}%"></div></div>
                    <span class="bar-value">${escapeHtml(String(s.jd_rating ?? 0))}</span>
                </div>
                <div class="bar-series">
                    <span class="bar-label">Your resume</span>
                    <div class="bar-track"><div class="bar-fill resume-fill" style="width:${Number(s.user_rating) || 0}%"></div></div>
                    <span class="bar-value">${escapeHtml(String(s.user_rating))}</span>
                </div>
            </div>
        </div>
    `).join("");
}

function fmt(ts) {
    const d = new Date(ts);
    return `${d.getMonth() + 1}/${d.getDate()}`;
}

function truncate(text, n) {
    return text.length > n ? `${text.slice(0, n - 1)}…` : text;
}

function escapeHtml(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;");
}

function escapeAttr(value) {
    return escapeHtml(value).replaceAll("'", "&#39;");
}
