"use strict";

const REGIONS = ["서울","부산","대구","인천","광주","대전","울산","세종",
  "경기","강원","충북","충남","전북","전남","경북","경남","제주"];
const CATEGORIES = ["자금","R&D","수출·판로","인력","창업·사업화",
  "교육·컨설팅","시설·공간","행사·네트워크","기타"];
const PAGE_SIZE = 30;

const state = {
  records: [],
  filters: { region: "", stage: "", age: "", categories: new Set(), targets: new Set(), keyword: "", sort: "deadline" },
  shown: PAGE_SIZE,
};

function ageMatch(sel, ageLimit) {
  if (sel === "youth") return ageLimit.some(t => t.includes("39세 이하") || t.includes("20세 미만"));
  if (sel === "over40") return ageLimit.some(t => t.includes("40세 이상"));
  return true;
}

// 반환: "ok"(✅ 신청 가능) | "check"(⚪ 확인 필요) | null(조건 불일치 → 숨김)
function matchRecord(r, f) {
  let complete = r.eligibility_complete;
  if (f.region) {
    if (r.regions.includes("UNKNOWN")) complete = false;
    else if (!r.regions.includes("전국") && !r.regions.includes(f.region)) return null;
  }
  if (f.stage) {
    if (!r.startup_years) complete = false;
    else if (!r.startup_years.includes(f.stage)) return null;
  }
  if (f.age) {
    if (!r.age_limit) complete = false;
    else if (!ageMatch(f.age, r.age_limit)) return null;
  }
  if (f.targets.size) {
    if (!r.target_types.length) complete = false;
    else if (![...f.targets].some(t => r.target_types.includes(t))) return null;
  }
  if (f.categories.size && !f.categories.has(r.category)) return null;
  if (f.keyword) {
    const k = f.keyword.toLowerCase();
    const hay = (r.title + " " + (r.summary || "")).toLowerCase();
    if (!hay.includes(k)) return null;
  }
  return complete ? "ok" : "check";
}

function dday(r) {
  if (!r.apply_end) return null;
  const end = new Date(r.apply_end + "T23:59:59+09:00");
  return Math.floor((end - Date.now()) / 86400000);
}

function sortRecords(list, mode) {
  const copy = [...list];
  if (mode === "latest") {
    copy.sort((a, b) => (b.rec.listed_at || "").localeCompare(a.rec.listed_at || ""));
  } else {
    copy.sort((a, b) => {
      const ka = a.rec.apply_end || "9999-12-31", kb = b.rec.apply_end || "9999-12-31";
      return ka === kb ? a.rec.title.localeCompare(b.rec.title, "ko") : ka.localeCompare(kb);
    });
  }
  return copy;
}

function esc(s) {
  return (s || "").replace(/[&<>"']/g, c =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function cardHtml({ rec, verdict }) {
  const d = dday(rec);
  const badges = [];
  if (verdict === "ok") badges.push('<span class="badge ok">✅ 신청 가능</span>');
  else badges.push('<span class="badge checkmark">⚪ 원문 확인 필요</span>');
  if (rec.period_status === "ROLLING") badges.push('<span class="badge rolling">상시 모집</span>');
  else if (rec.period_status === "UPCOMING") badges.push('<span class="badge">접수 예정</span>');
  else if (d !== null && d >= 0) badges.push(`<span class="badge dday">D-${d === 0 ? "DAY" : d}</span>`);
  else if (rec.period_status === "UNKNOWN") badges.push('<span class="badge">기간 원문 확인</span>');
  badges.push(`<span class="badge">${esc(rec.category)}</span>`);
  rec.regions.filter(x => x !== "UNKNOWN").slice(0, 3)
    .forEach(x => badges.push(`<span class="badge">${esc(x)}</span>`));
  const period = rec.apply_end
    ? `${esc(rec.apply_start || "?")} ~ ${esc(rec.apply_end)}`
    : esc(rec.raw_period_text || "기간 원문 확인");
  return `<li class="card">
    <div class="badges">${badges.join("")}</div>
    <h2><a href="${esc(rec.url)}" target="_blank" rel="noopener">${esc(rec.title)}</a></h2>
    <p class="meta">${esc(rec.org)} · ${period}</p>
    ${rec.summary ? `<p class="summary">${esc(rec.summary)}</p>` : ""}
  </li>`;
}

function render() {
  const f = state.filters;
  const matched = [];
  for (const rec of state.records) {
    const verdict = matchRecord(rec, f);
    if (verdict) matched.push({ rec, verdict });
  }
  const sorted = sortRecords(matched, f.sort);
  const okCount = sorted.filter(m => m.verdict === "ok").length;
  document.getElementById("result-count").textContent =
    `${sorted.length}건 (✅ 신청 가능 ${okCount} · ⚪ 확인 필요 ${sorted.length - okCount})`;
  document.getElementById("results").innerHTML =
    sorted.slice(0, state.shown).map(cardHtml).join("");
  document.getElementById("more").hidden = sorted.length <= state.shown;
}

function buildChips(containerId, values, selectedSet) {
  const box = document.getElementById(containerId);
  box.innerHTML = values.map(v => `<button type="button" class="chip" data-v="${esc(v)}">${esc(v)}</button>`).join("");
  box.addEventListener("click", e => {
    const btn = e.target.closest(".chip");
    if (!btn) return;
    const v = btn.dataset.v;
    if (selectedSet.has(v)) { selectedSet.delete(v); btn.classList.remove("on"); }
    else { selectedSet.add(v); btn.classList.add("on"); }
    state.shown = PAGE_SIZE;
    render();
  });
}

function init(records, meta) {
  state.records = records;
  const metaEl = document.getElementById("meta-info");
  metaEl.textContent = `데이터 기준: ${meta.generated_at.replace("T", " ").slice(0, 16)}`;
  const failed = Object.entries(meta.sources).filter(([, s]) => !s.ok).map(([n]) => n);
  if (failed.length) {
    const warn = document.getElementById("source-warning");
    warn.textContent = `일부 출처(${failed.join(", ")})의 최신 갱신에 실패해 이전 데이터가 포함되어 있어요.`;
    warn.hidden = false;
  }
  const regionSel = document.getElementById("f-region");
  REGIONS.forEach(r => regionSel.insertAdjacentHTML("beforeend", `<option>${r}</option>`));
  buildChips("f-category", CATEGORIES, state.filters.categories);
  const targetCount = new Map();
  records.forEach(r => r.target_types.forEach(t => targetCount.set(t, (targetCount.get(t) || 0) + 1)));
  const topTargets = [...targetCount.entries()].sort((a, b) => b[1] - a[1]).slice(0, 8).map(([t]) => t);
  buildChips("f-targets", topTargets, state.filters.targets);

  const bind = (id, key) => document.getElementById(id).addEventListener("change", e => {
    state.filters[key] = e.target.value; state.shown = PAGE_SIZE; render();
  });
  bind("f-region", "region"); bind("f-stage", "stage"); bind("f-age", "age"); bind("f-sort", "sort");
  document.getElementById("f-keyword").addEventListener("input", e => {
    state.filters.keyword = e.target.value.trim(); state.shown = PAGE_SIZE; render();
  });
  document.getElementById("more").addEventListener("click", () => {
    state.shown += PAGE_SIZE; render();
  });
  render();
}

Promise.all([
  fetch("data/programs.json").then(r => { if (!r.ok) throw new Error(r.status); return r.json(); }),
  fetch("data/meta.json").then(r => { if (!r.ok) throw new Error(r.status); return r.json(); }),
]).then(([records, meta]) => init(records, meta))
  .catch(err => {
    document.getElementById("meta-info").textContent = "데이터를 불러오지 못했습니다. 잠시 후 새로고침해 주세요.";
    console.error(err);
  });
