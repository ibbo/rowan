"use strict";
const $ = (id) => document.getElementById(id);
const escapeHtml = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c],
  );
const defaults = {
  length: 16,
  jigs: 5,
  reels: 6,
  strathspeys: 5,
  break_after: 8,
  profile: "social",
  rhythm_mode: "error",
  duplicate_mode: "error",
  max_fast_run: 2,
  rscds_target: 75,
  rscds_tolerance: 15,
  jig_opener: true,
  quick_finish: true,
  pool: "sample",
  difficulty_mix: { one: 40, two: 45, three: 15, expert: 0 },
  allow_ungraded: false,
  figure_rules: [],
};
const GRADES = ["one", "two", "three", "expert"];
const PRESET_NAMES = { beginner: "easier", social: "mixed", ball: "ball-level" };
const RHYTHM_NAMES = { J: "jig", R: "reel", S: "strathspey" };
let state = {
    version: 1,
    title: "My dance programme",
    entries: [],
    options: JSON.parse(JSON.stringify(defaults)),
  },
  history = [],
  revision = 0,
  checkTimer,
  searchTimer,
  noticeTimer,
  searchVersion = 0,
  replaceIndex = null,
  openRow = null,
  customDifficulty = false,
  busy = false;
let metadata = new Map(),
  candidates = new Map(),
  rowIssues = new Map(),
  figures = [],
  difficultyGrades = {},
  difficultyPresets = {};
// The search box moves between the foot of the list and a row being replaced.
const searchBox = $("search-box"),
  searchInput = $("dance-search"),
  searchResults = $("search-results");
const cleanEntry = (e) => ({
  kind: e.kind || "dance",
  dance_id: e.dance_id || null,
  name: e.name || "",
  locked: !!e.locked,
});
const plural = (n, one, many = one + "s") => `${n} ${n === 1 ? one : many}`;
const difficultyTotal = (mix) => (mix ? GRADES.reduce((a, k) => a + mix[k], 0) : 100);

function notify(message, error = false) {
  clearTimeout(noticeTimer);
  $("notice").textContent = message;
  $("notice").className = error ? "error" : "";
  $("notice").hidden = false;
  if (!error) noticeTimer = setTimeout(() => ($("notice").hidden = true), 6000);
}
async function api(path, data) {
  const response = await fetch("/api/programmes/" + path, {
    method: data ? "POST" : "GET",
    headers: data ? { "Content-Type": "application/json" } : {},
    body: data ? JSON.stringify(data) : undefined,
  });
  const result = await response.json();
  if (!response.ok) {
    let detail = result.detail;
    throw Error(
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((e) => `${e.loc.slice(1).join(" ")}: ${e.msg}`).join("; ")
          : "The request could not be completed.",
    );
  }
  return result;
}
function remember() {
  history.push(JSON.stringify(state));
  if (history.length > 30) history.shift();
  $("undo").disabled = false;
}
function store() {
  let item = activeItem();
  if (!item) {
    item = { id: library.active || newId() };
    library.items.unshift(item);
    library.active = item.id;
  }
  const snapshot = JSON.stringify(state);
  if (JSON.stringify(item.state) !== snapshot) {
    item.state = JSON.parse(snapshot);
    item.updatedAt = new Date().toISOString();
  }
  try {
    localStorage.setItem(LIBRARY_KEY, JSON.stringify(library));
    $("save-state").textContent = "Saved in this browser";
  } catch {
    $("save-state").textContent = "Not saved — download a file to keep it";
  }
  renderLibrary();
}
function changed() {
  revision++;
  store();
  render();
  $("status").hidden = false;
  $("status").className = "status";
  $("status").textContent = "Checking…";
  clearTimeout(checkTimer);
  checkTimer = setTimeout(runCheck, 220);
}
function mutate(fn) {
  if (busy) return;
  remember();
  // Clear stale messages first so that a message raised by fn() stays visible.
  $("notice").hidden = true;
  fn();
  changed();
}
function rememberMetadata(entries) {
  for (const e of entries || []) {
    if (e.dance) metadata.set(e.dance.id, e.dance);
    if (e.candidates?.length) {
      for (const d of e.candidates) metadata.set(d.id, d);
      candidates.set(e.name, e.candidates);
    }
  }
}

/* ---------- Options ---------- */
function applyOptions() {
  const o = state.options;
  for (const [id, key] of Object.entries(optionIds)) {
    const el = $(id);
    if (el.type === "checkbox") el.checked = o[key];
    else el.value = o[key];
  }
  $("rscds-target").value = o.rscds_target ?? 75;
  $("rscds-enabled").checked = o.rscds_target !== null;
  customDifficulty = false;
  applyDifficulty();
  renderRules();
  updateOptionsView();
}
function applyDifficulty() {
  for (const [index, key] of GRADES.entries()) {
    $("difficulty-" + key).value = state.options.difficulty_mix?.[key] ?? 0;
    $("difficulty-" + key).title = difficultyGrades[index + 1] || "";
  }
  $("allow-ungraded").checked = state.options.allow_ungraded;
}
function difficultyPreset() {
  const mix = state.options.difficulty_mix;
  if (mix === null) return "off";
  if (customDifficulty) return "custom";
  return (
    Object.keys(difficultyPresets).find((key) => GRADES.every((g) => mix[g] === difficultyPresets[key][g])) ||
    "custom"
  );
}
function describeMix(mix) {
  return [
    [mix.one, "1 ghillie"],
    [mix.two, "2 ghillies"],
    [mix.three, "3 ghillies"],
    [mix.expert, "expert"],
  ]
    .filter(([n]) => n)
    .map(([n, label]) => `${n}% ${label}`)
    .join(" · ");
}
function updateOptionsView() {
  const o = state.options,
    total = o.jigs + o.reels + o.strathspeys,
    mix = o.difficulty_mix,
    preset = difficultyPreset(),
    mixTotal = difficultyTotal(mix);
  // Dialog
  $("mix-total").textContent =
    total === o.length
      ? `Adds up to ${o.length} dances.`
      : `Adds up to ${total}, but the programme has ${o.length} dances.`;
  $("mix-total").classList.toggle("bad", total !== o.length);
  $("rscds-value").textContent = (o.rscds_target ?? $("rscds-target").value) + "%";
  $("rscds-target").disabled = o.rscds_target === null || busy;
  $("difficulty-preset").value = preset;
  $("difficulty-custom").hidden = preset !== "custom";
  $("difficulty-description").textContent =
    mix === null ? "Difficulty is not considered." : preset === "custom" ? "" : describeMix(mix) + " of graded dances.";
  $("difficulty-total").hidden = preset !== "custom";
  $("difficulty-total").textContent =
    mixTotal === 100 ? "Adds up to 100%." : `Adds up to ${mixTotal}% — needs to be 100%.`;
  $("difficulty-total").classList.toggle("bad", mixTotal !== 100);
  $("allow-ungraded-label").hidden = mix === null;
  // One-line summary under the setup sentence
  const parts = [];
  if (total !== o.length)
    parts.push(`<b class="bad">Rhythm counts add up to ${total}, not ${o.length}</b>`);
  else parts.push(`${o.jigs} jigs, ${o.reels} reels, ${o.strathspeys} strathspeys`);
  parts.push(o.break_after ? `interval after ${o.break_after}` : "no interval");
  if (mix && mixTotal !== 100) parts.push(`<b class="bad">difficulty adds up to ${mixTotal}%</b>`);
  else parts.push(mix ? `${PRESET_NAMES[preset] || "custom"} difficulty` : "any difficulty");
  if (o.figure_rules.length) parts.push(plural(o.figure_rules.length, "figure rule"));
  if (o.pool === "catalogue") parts.push("whole catalogue");
  $("options-summary").innerHTML = parts.join(" · ");
}
function figureOptions(selected) {
  return (
    '<option value="">Choose a figure…</option>' +
    figures
      .map(
        (f) =>
          `<option value="${escapeHtml(f.key)}" ${f.key === selected ? "selected" : ""}>${escapeHtml(f.name)}</option>`,
      )
      .join("")
  );
}
function renderRules() {
  $("figure-rules").innerHTML = state.options.figure_rules
    .map(
      (r, i) => `<div class="figure-rule" data-rule="${i}">
        <select data-field="key" aria-label="Figure">${figureOptions(r.key)}</select>
        <label class="inline">At most <input data-field="max_count" type="number" min="0" max="32" value="${r.max_count ?? ""}" placeholder="any"> dances</label>
        <label class="inline">At least <input data-field="min_gap" type="number" min="0" max="16" value="${r.min_gap}"> dances apart</label>
        <div class="rule-foot">
          <select data-field="mode" aria-label="How strict">
            <option value="warning" ${r.mode === "warning" ? "selected" : ""}>Warn me</option>
            <option value="error" ${r.mode === "error" ? "selected" : ""}>Required (needs verified figure data)</option>
            <option value="off" ${r.mode === "off" ? "selected" : ""}>Off</option>
          </select>
          <button class="link" data-remove-rule="${i}">Remove</button>
        </div>
      </div>`,
    )
    .join("");
}

/* ---------- Programme list ---------- */
const LOCK_ICON = (locked) =>
  `<svg viewBox="0 0 16 16" aria-hidden="true"><rect x="3" y="7" width="10" height="7" rx="1.5"/><path d="${locked ? "M5.5 7V5a2.5 2.5 0 0 1 5 0v2" : "M5.5 7V5a2.5 2.5 0 0 1 4.9-.7"}" fill="none"/></svg>`;
function gradeLabel(d) {
  return d.rscds_grade === 1
    ? "1 ghillie"
    : d.rscds_grade === 2
      ? "2 ghillies"
      : d.rscds_grade === 3
        ? "3 ghillies"
        : d.rscds_grade === 4
          ? "expert"
          : "ungraded";
}
function shortMeta(d) {
  return [d.bars ? `${d.bars} bars` : null, d.couples, gradeLabel(d)]
    .filter(Boolean)
    .map(escapeHtml)
    .join(" · ");
}
function moveButtons(i) {
  const label = escapeHtml(state.entries[i].name || "interval");
  return `<button class="ghost" data-action="up" data-index="${i}" aria-label="Move ${label} up" ${i === 0 ? "disabled" : ""}>↑ Up</button><button class="ghost" data-action="down" data-index="${i}" aria-label="Move ${label} down" ${i === state.entries.length - 1 ? "disabled" : ""}>↓ Down</button>`;
}
function issueNotes(i) {
  return (rowIssues.get(i) || [])
    .map((issue) => `<p class="row-issue ${issue.level}">${escapeHtml(issue.message)}</p>`)
    .join("");
}
function danceRow(e, i, position) {
  const d = metadata.get(e.dance_id),
    open = openRow === i,
    level = (rowIssues.get(i) || []).some((x) => x.level === "error")
      ? "error"
      : rowIssues.has(i)
        ? "warning"
        : "",
    rhythm = d?.rhythm || "?",
    number = e.kind === "extra" ? "" : String(position).padStart(2, "0");
  let meta;
  if (d) meta = shortMeta(d);
  else if (e.dance_id) meta = "Loading…";
  else meta = '<span class="bad">Not found in the catalogue</span>';
  const choices =
    !e.dance_id && candidates.get(e.name)?.length
      ? `<div class="choices"><span>Did you mean</span>${candidates
          .get(e.name)
          .map(
            (c) =>
              `<button class="chip" data-action="pick" data-index="${i}" data-dance="${c.id}">${escapeHtml(c.name)} <small>${escapeHtml(c.rhythm)}${c.bars}</small></button>`,
          )
          .join("")}</div>`
      : "";
  const facts = d
    ? `<dl class="facts">
        <dt>Set</dt><dd>${escapeHtml([d.couples, d.set_shape].filter(Boolean).join(", ") || "Unknown")}</dd>
        <dt>Difficulty</dt><dd>${escapeHtml(d.rscds_grade_label || "No published grade")}</dd>
        <dt>Published in</dt><dd>${escapeHtml(d.publications.slice(0, 3).map((p) => p.name).join(" · ") || "Unknown")}</dd>
        <dt>Figures</dt><dd>${escapeHtml(d.figure_names.join(" · ") || "No figure data")}${d.figure_names.length && d.formations_verified !== 1 ? ' <span class="muted">(unverified)</span>' : ""}</dd>
      </dl><a href="${escapeHtml(d.url)}" target="_blank" rel="noopener">View on SCDDB ↗</a>`
    : "";
  return `<li class="row ${open ? "open" : ""} ${level}" id="row-${i}">
    <div class="row-main">
      <span class="num">${number}</span>
      <span class="badge ${["J", "R", "S"].includes(rhythm) ? rhythm : ""}" title="${escapeHtml(RHYTHM_NAMES[rhythm] || "Rhythm unknown")}">${escapeHtml(rhythm)}</span>
      <button class="row-toggle" data-action="toggle" data-index="${i}" aria-expanded="${open}" aria-controls="detail-${i}">
        <span class="name ${e.dance_id ? "" : "bad"}"><span class="name-text">${escapeHtml(d?.name || e.name || "Unnamed dance")}</span>${level ? `<span class="flag ${level}" aria-label="Has issues"></span>` : ""}</span>
        <span class="meta">${meta}</span>
      </button>
      ${e.kind === "dance" ? `<button class="lock ${e.locked ? "on" : ""}" data-action="lock" data-index="${i}" aria-pressed="${e.locked}" title="${e.locked ? "Locked: kept when you regenerate" : "Lock to keep when you regenerate"}" aria-label="${e.locked ? "Unlock" : "Lock"} ${escapeHtml(e.name)}">${LOCK_ICON(e.locked)}</button>` : '<span class="lock-space"></span>'}
    </div>
    ${choices}
    <div class="row-detail" id="detail-${i}" ${open ? "" : "hidden"}>
      ${issueNotes(i)}
      ${facts}
      <div class="row-actions">${moveButtons(i)}<button class="ghost" data-action="replace" data-index="${i}">Replace</button><button class="ghost danger" data-action="remove" data-index="${i}">Remove</button></div>
    </div>
  </li>`;
}
function intervalRow(e, i) {
  return `<li class="row interval" id="row-${i}"><span>${escapeHtml(e.name || "Interval")}</span><div class="row-actions">${moveButtons(i)}<button class="ghost" data-action="remove" data-index="${i}" aria-label="Remove interval">✕</button></div></li>`;
}
function render() {
  if (document.activeElement !== $("title")) $("title").value = state.title;
  updateOptionsView();
  $("generate").textContent = busy ? "Generating…" : state.entries.length ? "Regenerate" : "Generate";
  const hadFocus = document.activeElement === searchInput;
  $("add-slot").prepend(searchBox);
  let position = 0,
    extras = false;
  const rows = state.entries.map((e, i) => {
    if (e.kind === "break") return intervalRow(e, i);
    if (e.kind === "dance") position++;
    const heading = e.kind === "extra" && !extras ? '<li class="section-heading">Extras</li>' : "";
    if (e.kind === "extra") extras = true;
    return heading + danceRow(e, i, position);
  });
  $("programme-list").innerHTML = rows.length
    ? rows.join("")
    : `<li class="empty"><h2>Start your programme</h2><p>Set the event and number of dances above, then press <b>Generate</b>.</p><p>Already have a list? <button class="link" data-menu="paste">Paste it here</button> to check it.</p></li>`;
  if (replaceIndex !== null && $("row-" + replaceIndex)) {
    $("row-" + replaceIndex).querySelector(".row-detail").prepend(searchBox);
  }
  if (hadFocus) searchInput.focus();
  const mains = state.entries.filter((e) => e.kind === "dance").length,
    extraCount = state.entries.filter((e) => e.kind === "extra").length,
    locked = state.entries.filter((e) => e.locked).length;
  $("counts").textContent = state.entries.length
    ? [plural(mains, "dance"), extraCount ? plural(extraCount, "extra") : "", locked ? `${locked} locked` : ""]
        .filter(Boolean)
        .join(" · ")
    : "";
  $("undo").disabled = !history.length || busy;
}

/* ---------- Check results ---------- */
function renderCheck(result) {
  const s = result.summary;
  rowIssues = new Map();
  if (!state.entries.length) {
    $("review").hidden = true;
    $("status").hidden = true;
    render();
    return;
  }
  const visible = result.issues.filter((i) => i.level !== "info"),
    notes = result.issues.filter((i) => i.level === "info");
  for (const issue of visible)
    for (const index of new Set(issue.indices)) {
      if (!rowIssues.has(index)) rowIssues.set(index, []);
      rowIssues.get(index).push(issue);
    }
  render();
  $("status").hidden = false;
  $("status").className = "status " + (s.errors ? "error" : s.warnings ? "warning" : "ok");
  $("status").textContent = s.errors
    ? `${s.errors} to fix`
    : s.warnings
      ? `${plural(s.warnings, "suggestion")}`
      : "✓ Looks good";
  $("review").hidden = false;
  $("issues").innerHTML = visible.length
    ? visible
        .map(
          (i) =>
            `<div class="issue ${i.level}"><span class="tag">${i.level === "error" ? "Fix" : "Consider"}</span><p>${escapeHtml(i.message)}</p>${i.indices.length ? `<button class="link" data-show-row="${i.indices[0]}">Show</button>` : i.code === "difficulty_balance" ? '<button class="link" data-show-summary>Show</button>' : ""}</div>`,
        )
        .join("")
    : '<p class="all-good">✓ No problems found with the rules you’ve set.</p>';
  const grades = s.difficulty_counts || {},
    names = ["1 ghillie", "2 ghillies", "3 ghillies", "Expert / unusual"];
  const difficulty = state.options.difficulty_mix
    ? `<table><thead><tr><th scope="col">Difficulty</th><th scope="col">Target</th><th scope="col">Actual</th></tr></thead><tbody>${names
        .map(
          (label, i) =>
            `<tr><th scope="row">${label}</th><td>${s.difficulty_targets?.[i + 1] || 0}</td><td>${grades[i + 1] || 0}</td></tr>`,
        )
        .join(
          "",
        )}</tbody></table><p class="hint">Counts ${plural(s.difficulty_graded, "graded main dance")}${s.difficulty_ungraded ? `; ${s.difficulty_ungraded} ungraded not counted` : ""}. A difference of more than one dance is flagged.</p>`
    : `<p>${names.map((label, i) => `${grades[i + 1] || 0} × ${label.toLowerCase()}`).join(" · ")} · ${s.difficulty_ungraded} ungraded</p>`;
  $("summary-body").innerHTML = `
    <div class="stats">
      <div><b>${s.main_count}${s.extras ? `<small> + ${s.extras}</small>` : ""}</b><span>dances${s.extras ? " + extras" : ""}</span></div>
      <div><b>${s.rhythms.J || 0} / ${s.rhythms.R || 0} / ${s.rhythms.S || 0}</b><span>J / R / S</span></div>
      <div><b>${s.rscds_share === null ? "—" : Math.round(s.rscds_share) + "%"}</b><span>RSCDS-published</span></div>
      <div><b>${s.max_fast_run}</b><span>longest quick-time run</span></div>
    </div>
    <h3>Difficulty</h3>${difficulty}
    <h3>Figures</h3>${
      s.families.length
        ? `<div class="chips">${s.families.map((f) => `<span class="chip static">${escapeHtml(f.name)} <b>${f.count}</b></span>`).join("")}</div>`
        : '<p class="hint">No figure information yet.</p>'
    }
    ${notes.length ? `<h3>About the data</h3><ul class="notes">${notes.map((n) => `<li>${escapeHtml(n.message)}</li>`).join("")}</ul>` : ""}`;
}
async function runCheck() {
  const version = revision;
  if (difficultyTotal(state.options.difficulty_mix) !== 100) {
    $("status").className = "status error";
    $("status").textContent = "Fix difficulty percentages";
    return;
  }
  try {
    const result = await api("check", { entries: state.entries, options: state.options });
    if (version !== revision) return;
    rememberMetadata(result.entries);
    renderCheck(result);
  } catch (e) {
    if (version === revision) notify(e.message, true);
  }
}
function setBusy(value) {
  busy = value;
  document.querySelectorAll("button,input,select,textarea").forEach((el) => (el.disabled = value));
  render();
}
async function makeProgramme() {
  if (busy) return;
  clearTimeout(checkTimer);
  cancelReplace();
  setBusy(true);
  $("notice").hidden = true;
  try {
    const result = await api("generate", { entries: state.entries, options: state.options });
    remember();
    const locked = state.entries.filter((e) => e.locked).length;
    state.entries = result.entries.map(cleanEntry);
    openRow = null;
    rememberMetadata(result.entries);
    revision++;
    store();
    renderCheck(result);
    notify(
      (locked ? `New programme generated around your ${plural(locked, "locked dance")}.` : "Programme generated.") +
        " Lock the dances you like, then regenerate to change the rest.",
    );
  } catch (e) {
    notify(e.message, true);
  } finally {
    setBusy(false);
    updateOptionsView();
  }
}
function updateBreakOption() {
  let n = 0,
    found = false;
  for (const e of state.entries) {
    if (e.kind === "dance") n++;
    if (e.kind === "break" && !found) {
      state.options.break_after = n;
      found = true;
    }
  }
  if (!found) state.options.break_after = 0;
  $("break-after").value = state.options.break_after;
}

/* ---------- Search, add and replace ---------- */
function startReplace(i) {
  replaceIndex = i;
  openRow = i;
  $("search-label").textContent = `Replace “${state.entries[i].name}”`;
  searchInput.placeholder = "Search for a replacement…";
  $("cancel-replace").hidden = false;
  render();
  searchInput.value = state.entries[i].name;
  searchInput.focus();
  searchInput.select();
  searchDances();
}
function cancelReplace() {
  const wasReplacing = replaceIndex !== null;
  replaceIndex = null;
  $("search-label").textContent = "Add a dance";
  searchInput.placeholder = "Add a dance by name…";
  $("cancel-replace").hidden = true;
  searchInput.value = "";
  searchResults.hidden = true;
  searchVersion++;
  if (wasReplacing) $("add-slot").prepend(searchBox);
}
async function searchDances() {
  const term = searchInput.value.trim(),
    version = ++searchVersion;
  if (!term) {
    searchResults.hidden = true;
    return;
  }
  try {
    const result = await api("catalogue?q=" + encodeURIComponent(term));
    if (version !== searchVersion) return;
    for (const d of result.dances) metadata.set(d.id, d);
    const replacing = replaceIndex !== null;
    searchResults.innerHTML = result.dances.length
      ? result.dances
          .map(
            (d) =>
              `<div class="result"><button class="result-main" data-dance="${d.id}"><span class="badge ${escapeHtml(d.rhythm)}">${escapeHtml(d.rhythm)}</span><span><span class="name">${escapeHtml(d.name)}</span><span class="meta">${shortMeta(d)} · ${escapeHtml(d.publications[0]?.name || "Publication unknown")}</span></span></button>${replacing ? "" : `<button class="ghost" data-dance="${d.id}" data-extra aria-label="Add ${escapeHtml(d.name)} as an extra">+ Extra</button>`}</div>`,
          )
          .join("")
      : '<p class="hint pad">No matching dances. Try part of the name.</p>';
    searchResults.hidden = false;
  } catch (e) {
    notify(e.message, true);
  }
}
function placeDance(d, asExtra) {
  const replacing = replaceIndex !== null;
  mutate(() => {
    if (replaceIndex !== null) {
      const old = state.entries[replaceIndex];
      state.entries[replaceIndex] = { ...old, dance_id: d.id, name: d.name };
    } else {
      if (state.entries.length >= 80) {
        notify("This programme has reached the 80-item limit.", true);
        return;
      }
      const e = { kind: asExtra ? "extra" : "dance", dance_id: d.id, name: d.name, locked: false };
      const extra = state.entries.findIndex((e) => e.kind === "extra");
      if (!asExtra && extra >= 0) state.entries.splice(extra, 0, e);
      else state.entries.push(e);
    }
    openRow = null;
    cancelReplace();
  });
  if (!replacing) searchInput.focus();
}
searchInput.oninput = () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(searchDances, 180);
};
searchInput.onkeydown = (event) => {
  if (event.key === "Escape") {
    cancelReplace();
    render();
  }
  if (event.key === "Enter") searchResults.querySelector("[data-dance]")?.click();
};
searchResults.onclick = (event) => {
  const b = event.target.closest("[data-dance]");
  if (b) placeDance(metadata.get(Number(b.dataset.dance)), "extra" in b.dataset);
};
$("cancel-replace").onclick = () => {
  cancelReplace();
  render();
};

/* ---------- Row actions ---------- */
$("programme-list").onclick = (event) => {
  const button = event.target.closest("[data-action]");
  if (!button || busy) return;
  const i = Number(button.dataset.index),
    action = button.dataset.action;
  if (action === "toggle") {
    if (replaceIndex === i) cancelReplace();
    openRow = openRow === i ? null : i;
    render();
    return;
  }
  if (action === "replace") return startReplace(i);
  mutate(() => {
    if (action === "lock") state.entries[i].locked = !state.entries[i].locked;
    else if (action === "pick") {
      const d = metadata.get(Number(button.dataset.dance));
      state.entries[i] = { ...state.entries[i], dance_id: d.id, name: d.name };
    } else if (action === "remove") {
      state.entries.splice(i, 1);
      openRow = null;
    } else {
      const j = i + (action === "up" ? -1 : 1);
      if (j >= 0 && j < state.entries.length) {
        [state.entries[i], state.entries[j]] = [state.entries[j], state.entries[i]];
        if (openRow === i) openRow = j;
      }
    }
    updateBreakOption();
    cancelReplace();
  });
  // Keep focus on the move button so a dance can be nudged repeatedly.
  if (action === "up" || action === "down") {
    const j = i + (action === "up" ? -1 : 1);
    document.querySelector(`[data-action="${action}"][data-index="${j}"]:not(:disabled)`)?.focus();
  }
};
$("issues").onclick = (e) => {
  if (e.target.closest("[data-show-summary]")) {
    $("summary-details").open = true;
    $("summary-details").scrollIntoView({ behavior: "smooth", block: "start" });
    return;
  }
  const b = e.target.closest("[data-show-row]");
  if (!b) return;
  const i = Number(b.dataset.showRow);
  if (state.entries[i]?.kind !== "break") openRow = i;
  render();
  const row = $("row-" + i);
  if (row) {
    row.scrollIntoView({ behavior: "smooth", block: "center" });
    row.classList.add("target");
    setTimeout(() => row.classList.remove("target"), 2500);
  }
};
$("status").onclick = () => $("review").scrollIntoView({ behavior: "smooth", block: "start" });
$("generate").onclick = makeProgramme;
$("title").oninput = () => {
  state.title = $("title").value;
  store();
};

/* ---------- Option inputs ---------- */
const optionIds = {
  profile: "profile",
  length: "length",
  jigs: "jigs",
  reels: "reels",
  strathspeys: "strathspeys",
  "break-after": "break_after",
  "rhythm-mode": "rhythm_mode",
  "duplicate-mode": "duplicate_mode",
  "max-fast-run": "max_fast_run",
  pool: "pool",
  "jig-opener": "jig_opener",
  "quick-finish": "quick_finish",
  "allow-ungraded": "allow_ungraded",
};
for (const [id, key] of Object.entries(optionIds)) {
  const update = () => {
    const el = $(id),
      value = el.type === "checkbox" ? el.checked : el.type === "number" ? Number(el.value) : el.value;
    if (state.options[key] === value) return;
    if (el.type === "number" && (el.value === "" || !el.checkValidity())) return;
    mutate(() => {
      state.options[key] = value;
      if (key === "profile") {
        state.options.rhythm_mode = value === "beginner" ? "warning" : "error";
        $("rhythm-mode").value = state.options.rhythm_mode;
        state.options.difficulty_mix = { ...difficultyPresets[value] };
        customDifficulty = false;
        applyDifficulty();
      }
      if (key === "length") {
        const n = state.options.length;
        state.options.strathspeys = Math.round(n / 3);
        state.options.jigs = Math.floor((n - state.options.strathspeys) / 2);
        state.options.reels = n - state.options.jigs - state.options.strathspeys;
        for (const r of ["jigs", "reels", "strathspeys"]) $(r).value = state.options[r];
      }
      if (key === "break_after" && state.entries.length) {
        state.entries = state.entries.filter((e) => e.kind !== "break");
        if (state.options.break_after) {
          let n = 0,
            index = state.entries.findIndex((e) => e.kind === "dance" && ++n === state.options.break_after);
          if (index >= 0)
            state.entries.splice(index + 1, 0, { kind: "break", name: "Interval", dance_id: null, locked: false });
          else notify("The interval will be placed when a programme of the requested length is generated.");
        }
      }
    });
  };
  $(id).onchange = update;
  if ($(id).type === "number") $(id).oninput = update;
}
$("difficulty-preset").onchange = () =>
  mutate(() => {
    const preset = $("difficulty-preset").value;
    customDifficulty = preset === "custom";
    state.options.difficulty_mix =
      preset === "off"
        ? null
        : { ...(difficultyPresets[preset] || state.options.difficulty_mix || difficultyPresets.social) };
    applyDifficulty();
  });
for (const key of GRADES) {
  const update = () => {
    const value = Number($("difficulty-" + key).value);
    if (state.options.difficulty_mix?.[key] === value) return;
    mutate(() => {
      state.options.difficulty_mix[key] = value;
    });
  };
  $("difficulty-" + key).oninput = update;
  $("difficulty-" + key).onchange = update;
}
function changeRscds() {
  const value = $("rscds-enabled").checked ? Number($("rscds-target").value) : null;
  if (state.options.rscds_target === value) return;
  mutate(() => {
    state.options.rscds_target = value;
  });
}
$("rscds-target").oninput = changeRscds;
$("rscds-target").onchange = changeRscds;
$("rscds-enabled").onchange = changeRscds;
$("add-figure").onclick = () =>
  mutate(() => {
    if (state.options.figure_rules.length >= 20) return;
    state.options.figure_rules.push({ key: "family:ALLMND", max_count: null, min_gap: 1, mode: "warning" });
    renderRules();
  });
$("figure-rules").onchange = (event) => {
  const el = event.target,
    container = el.closest("[data-rule]");
  if (!container || !el.dataset.field) return;
  const r = state.options.figure_rules[Number(container.dataset.rule)],
    field = el.dataset.field,
    value =
      field === "max_count"
        ? el.value === ""
          ? null
          : Number(el.value)
        : field === "min_gap"
          ? Number(el.value)
          : el.value;
  if (r[field] === value) return;
  mutate(() => {
    r[field] = value;
  });
};
$("figure-rules").oninput = (event) => {
  if (event.target.type === "number") $("figure-rules").onchange(event);
};
$("figure-rules").onclick = (event) => {
  const b = event.target.closest("[data-remove-rule]");
  if (b)
    mutate(() => {
      state.options.figure_rules.splice(Number(b.dataset.removeRule), 1);
      renderRules();
    });
};
$("add-break").onclick = () =>
  mutate(() => {
    const count = state.entries.filter((e) => e.kind === "dance").length;
    if (count < 2) {
      notify("Add at least two dances before inserting an interval.");
      return;
    }
    let position = 0,
      lastBreak = 0;
    for (const entry of state.entries) {
      if (entry.kind === "dance") position++;
      if (entry.kind === "break") lastBreak = position;
    }
    const after = lastBreak < count - 1 ? lastBreak + Math.floor((count - lastBreak) / 2) : Math.floor(count / 2);
    position = 0;
    const index = state.entries.findIndex((e) => e.kind === "dance" && ++position === after) + 1;
    state.entries.splice(index, 0, { kind: "break", name: "Interval", dance_id: null, locked: false });
    updateBreakOption();
  });
$("undo").onclick = () => {
  if (!history.length || busy) return;
  state = JSON.parse(history.pop());
  openRow = null;
  applyOptions();
  cancelReplace();
  changed();
};

/* ---------- Menu and dialogs ---------- */
$("open-options").onclick = () => $("options-dialog").showModal();
for (const dialog of document.querySelectorAll("dialog")) {
  dialog.addEventListener("click", (event) => {
    const r = dialog.getBoundingClientRect(),
      outside =
        event.target === dialog &&
        (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom);
    if (outside || event.target.closest("[data-close]")) dialog.close();
  });
}
document.addEventListener("click", (event) => {
  if (!event.target.closest("#menu")) $("menu").open = false;
  const item = event.target.closest("[data-menu]");
  if (!item || busy) return;
  $("menu").open = false;
  const action = item.dataset.menu;
  if (action === "paste") $("import-dialog").showModal();
  else if (action === "duplicate") duplicateProgramme();
  else if (action === "export") download(textExport(), "text/plain", ".txt");
  else if (action === "download") download(JSON.stringify(state, null, 2), "application/json", ".json");
  else if (action === "print") window.print();
  else if (action === "clear")
    mutate(() => {
      state.entries = [];
      openRow = null;
      cancelReplace();
      notify("Programme cleared. Use Undo to bring it back.");
    });
});
$("import-submit").onclick = async () => {
  if (!$("import-text").value.trim()) {
    notify("Paste some dance names first.", true);
    return;
  }
  try {
    const result = await api("import", { text: $("import-text").value });
    mutate(() => {
      state.entries = result.entries.map(cleanEntry);
      openRow = null;
      rememberMetadata(result.entries);
      const mains = state.entries.filter((e) => e.kind === "dance");
      if (mains.length >= 4 && mains.length <= 32) state.options.length = mains.length;
      updateBreakOption();
      const counts = { J: 0, R: 0, S: 0 };
      for (const e of mains) {
        const r = metadata.get(e.dance_id)?.rhythm;
        if (r in counts) counts[r]++;
      }
      if (Object.values(counts).reduce((a, b) => a + b, 0) === mains.length) {
        state.options.jigs = counts.J;
        state.options.reels = counts.R;
        state.options.strathspeys = counts.S;
      } else if (mains.length >= 4 && mains.length <= 32) {
        const n = mains.length;
        state.options.strathspeys = Math.round(n / 3);
        state.options.jigs = Math.floor((n - state.options.strathspeys) / 2);
        state.options.reels = n - state.options.jigs - state.options.strathspeys;
      }
      applyOptions();
      cancelReplace();
    });
    $("import-dialog").close();
    const unresolved = state.entries.filter((e) => e.kind !== "break" && !e.dance_id).length;
    notify(
      unresolved
        ? `Programme imported. ${plural(unresolved, "name")} couldn’t be matched — pick the right dance in red rows.`
        : "Programme imported and checked.",
    );
  } catch (e) {
    notify(e.message, true);
  }
};
function textExport() {
  let n = 0,
    extras = false;
  const lines = [state.title, ""];
  for (const e of state.entries) {
    if (e.kind === "break") {
      lines.push("", e.name || "Interval", "");
      continue;
    }
    if (e.kind === "extra" && !extras) {
      lines.push("", "Extras");
      extras = true;
    }
    if (e.kind === "dance" && extras) {
      lines.push("", "Main programme");
      extras = false;
    }
    const d = metadata.get(e.dance_id);
    lines.push(
      `${e.kind === "dance" ? ++n + ". " : ""}${d?.name || e.name}${d ? " — " + d.rhythm + d.bars : ""}${!e.dance_id ? " [unresolved]" : ""}`,
    );
  }
  return lines.join("\n");
}
function download(content, type, suffix) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = (state.title.replace(/[^a-z0-9 -]/gi, "").trim() || "programme") + suffix;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
async function loadDraft(candidate, targetId = null) {
  if (
    !candidate ||
    candidate.version !== 1 ||
    !Array.isArray(candidate.entries) ||
    candidate.entries.length > 80 ||
    typeof candidate.title !== "string" ||
    candidate.title.length > 160 ||
    !candidate.options
  )
    throw Error("This is not a supported programme draft.");
  const next = {
    version: 1,
    title: candidate.title,
    entries: candidate.entries.map(cleanEntry),
    options: { ...defaults, ...candidate.options },
  };
  const oldDifficulty = !("difficulty_mix" in candidate.options) && candidate.options.max_rscds_grade != null;
  if (!("difficulty_mix" in candidate.options)) {
    next.options.difficulty_mix = oldDifficulty ? { ...difficultyPresets[next.options.profile] } : null;
  }
  delete next.options.max_rscds_grade;
  delete next.options.difficulty_mode;
  const result = await api("check", next);
  // Switch programmes only once the draft is known to be valid.
  if (targetId) library.active = targetId;
  mutate(() => {
    state = next;
    openRow = null;
    rememberMetadata(result.entries);
    applyOptions();
    cancelReplace();
  });
  clearTimeout(checkTimer);
  renderCheck(result);
  if (oldDifficulty)
    notify(
      "The old difficulty limit has been replaced with your event style’s suggested balance. Review it under More options.",
    );
}
$("upload-json").onchange = async (event) => {
  const file = event.target.files[0];
  $("menu").open = false;
  if (!file) return;
  try {
    if (file.size > 200000) throw Error("This file is too large for a programme draft.");
    await openProgramme(JSON.parse(await file.text()), newId());
    notify("Programme file opened as a new programme.");
  } catch (e) {
    notify(e.message, true);
  }
  event.target.value = "";
};

/* ---------- Programme library (sidebar) ---------- */
// Each programme saves itself, like a chat session. The old single draft and
// "saved copies" keys are migrated once and left in place.
const LIBRARY_KEY = "chatscd.programme.library.v1";
const PROGRAMME_ICON =
  '<svg viewBox="0 0 24 24"><path d="M3 13h2v-2H3v2zm0 4h2v-2H3v2zm0-8h2V7H3v2zm4 4h14v-2H7v2zm0 4h14v-2H7v2zM7 7v2h14V7H7z"/></svg>';
const RENAME_ICON =
  '<svg viewBox="0 0 24 24"><path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34a.9959.9959 0 0 0-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/></svg>';
const DELETE_ICON =
  '<svg viewBox="0 0 24 24"><path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/></svg>';
let library = { active: null, items: [] };
const newId = () => (crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`);
const activeItem = () => library.items.find((item) => item.id === library.active);
const freshState = () => ({
  version: 1,
  title: "Untitled programme",
  entries: [],
  options: JSON.parse(JSON.stringify(defaults)),
});
function readLibrary() {
  const read = (key) => {
    try {
      return JSON.parse(localStorage.getItem(key) || "null");
    } catch {
      return null;
    }
  };
  const saved = read(LIBRARY_KEY);
  if (saved?.items) return saved;
  const items = [],
    now = new Date().toISOString(),
    current = read("chatscd.programme.current.v1");
  if (current?.entries) items.push({ id: newId(), updatedAt: now, state: current });
  for (const { savedAt, ...copy } of read("chatscd.programme.drafts.v1") || [])
    items.push({ id: newId(), updatedAt: savedAt || now, state: copy });
  return { active: items[0]?.id || null, items };
}
function groupLabel(iso) {
  const then = new Date(iso),
    now = new Date(),
    startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()),
    days = Math.floor((startOfToday - then) / 86400000) + 1;
  if (then >= startOfToday) return "Today";
  if (days <= 1) return "Yesterday";
  if (days <= 7) return "Previous 7 days";
  return "Older";
}
function timeAgo(iso) {
  const seconds = Math.floor((Date.now() - new Date(iso)) / 1000);
  if (seconds < 60) return "Just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  if (seconds < 604800) return `${Math.floor(seconds / 86400)}d ago`;
  return new Date(iso).toLocaleDateString();
}
function renderLibrary() {
  const items = [...library.items].sort((a, b) => (b.updatedAt || "").localeCompare(a.updatedAt || ""));
  if (!items.length) {
    $("programme-library").innerHTML = '<div class="sessions-empty">No programmes yet.</div>';
    return;
  }
  let lastGroup = null;
  $("programme-library").innerHTML = items
    .map((item) => {
      const group = groupLabel(item.updatedAt),
        heading = group !== lastGroup ? `<div class="session-group-label">${group}</div>` : "",
        dances = item.state.entries.filter((e) => e.kind === "dance").length;
      lastGroup = group;
      return `${heading}<div class="session-item ${item.id === library.active ? "active" : ""}" data-programme="${item.id}" role="button" tabindex="0" title="${escapeHtml(item.state.title)}">
        <div class="session-mode-icon">${PROGRAMME_ICON}</div>
        <div class="session-body"><div class="session-title">${escapeHtml(item.state.title || "Untitled programme")}</div><div class="session-time">${dances ? plural(dances, "dance") + " · " : ""}${timeAgo(item.updatedAt)}</div></div>
        <div class="session-actions"><button class="session-action-btn" data-rename title="Rename">${RENAME_ICON}</button><button class="session-action-btn delete" data-delete title="Delete">${DELETE_ICON}</button></div>
      </div>`;
    })
    .join("");
}
async function openProgramme(candidate, id) {
  if (busy) return;
  cancelReplace();
  await loadDraft(candidate, id);
  $("title").value = state.title;
  history = [];
  $("undo").disabled = true;
  closeMobileSidebar();
}
async function newProgramme() {
  if (activeItem() && !state.entries.length) {
    // Reuse an empty programme rather than piling up blank ones.
    closeMobileSidebar();
    $("title").focus();
    $("title").select();
    return;
  }
  await openProgramme(freshState(), newId());
  $("title").focus();
  $("title").select();
}
async function duplicateProgramme() {
  const copy = JSON.parse(JSON.stringify(state));
  copy.title = `${state.title} (copy)`.slice(0, 160);
  await openProgramme(copy, newId());
  notify("Duplicated. You’re now editing the copy.");
}
async function deleteProgramme(id) {
  const item = library.items.find((i) => i.id === id);
  if (!item || !confirm(`Delete “${item.state.title}”? This cannot be undone.`)) return;
  library.items = library.items.filter((i) => i.id !== id);
  if (id !== library.active) return store();
  const next = [...library.items].sort((a, b) => (b.updatedAt || "").localeCompare(a.updatedAt || ""))[0];
  library.active = null;
  await openProgramme(next ? next.state : freshState(), next ? next.id : newId());
}
function startRename(row, id) {
  const item = library.items.find((i) => i.id === id),
    title = row.querySelector(".session-title"),
    input = document.createElement("input");
  input.className = "session-title-input";
  input.value = item.state.title;
  input.maxLength = 160;
  title.replaceWith(input);
  input.focus();
  input.select();
  let done = false;
  const finish = (save) => {
    if (done) return;
    done = true;
    const value = input.value.trim();
    if (save && value) {
      if (id === library.active) state.title = value;
      else item.state.title = value;
      if (id === library.active) $("title").value = value;
    }
    store();
  };
  input.onkeydown = (event) => {
    if (event.key === "Enter") finish(true);
    if (event.key === "Escape") finish(false);
  };
  input.onblur = () => finish(true);
  input.onclick = (event) => event.stopPropagation();
}
$("programme-library").onclick = async (event) => {
  const row = event.target.closest("[data-programme]");
  if (!row || busy) return;
  const id = row.dataset.programme;
  if (event.target.closest("[data-rename]")) return startRename(row, id);
  if (event.target.closest("[data-delete]")) return deleteProgramme(id);
  if (event.target.closest("input")) return;
  if (id === library.active) return closeMobileSidebar();
  try {
    await openProgramme(library.items.find((i) => i.id === id).state, id);
  } catch (e) {
    notify(e.message, true);
  }
};
$("programme-library").onkeydown = (event) => {
  if (event.key === "Enter" && event.target.matches("[data-programme]")) event.target.click();
};
$("new-programme").onclick = newProgramme;

/* ---------- Shell: sidebar and sign-in (shared with the chat page) ---------- */
function closeMobileSidebar() {
  $("sidebar").classList.remove("mobile-open");
  $("sidebar-overlay").classList.remove("active");
}
$("sidebar-toggle").onclick = () => {
  if (innerWidth <= 768) {
    const open = !$("sidebar").classList.contains("mobile-open");
    $("sidebar").classList.toggle("mobile-open", open);
    $("sidebar-overlay").classList.toggle("active", open);
    return;
  }
  const collapsed = $("sidebar").classList.toggle("collapsed");
  $("app").classList.toggle("sidebar-collapsed", collapsed);
  try {
    localStorage.setItem("chatSCD_sidebarCollapsed", collapsed);
  } catch {}
};
$("sidebar-overlay").onclick = closeMobileSidebar;
function browserId() {
  let id = localStorage.getItem("chatSCD_browserId");
  if (!id) {
    id = newId();
    localStorage.setItem("chatSCD_browserId", id);
  }
  return id;
}
function startOAuth(provider) {
  location.href = `/auth/login/${provider}?browser_id=${encodeURIComponent(browserId())}&next=${encodeURIComponent(location.pathname)}`;
}
function startDevAuth() {
  location.href = `/auth/dev-login?browser_id=${encodeURIComponent(browserId())}&next=${encodeURIComponent(location.pathname)}`;
}

async function init() {
  if (["localhost", "127.0.0.1"].includes(location.hostname)) $("preview-badge").hidden = false;
  try {
    if (innerWidth > 768 && localStorage.getItem("chatSCD_sidebarCollapsed") === "true") {
      $("sidebar").classList.add("collapsed");
      $("app").classList.add("sidebar-collapsed");
    }
  } catch {}
  library = readLibrary();
  if (!activeItem() && library.items.length) library.active = library.items[0].id;
  renderLibrary();
  try {
    const cat = await api("catalogue");
    difficultyGrades = cat.difficulty_grades || {};
    difficultyPresets = cat.difficulty_presets || {};
    figures = cat.figures.sort((a, b) => a.name.localeCompare(b.name));
    const item = activeItem();
    if (item) {
      await loadDraft(item.state, item.id);
      history = [];
    } else {
      state = freshState();
      applyOptions();
      render();
    }
    $("undo").disabled = !history.length;
  } catch (e) {
    notify(e.message, true);
    applyOptions();
    render();
  }
}
init();
