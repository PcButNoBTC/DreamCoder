/* BOOT SAFETY */
window.addEventListener("error", (e) => {
  console.error("DreamCoder error:", e.message, e.filename, e.lineno);
});
/* DreamCoder – interactive frontend with live AI self-update (Evolve) */

const API_BASE = window.DREAMCODER_API || "http://localhost:8000";

function showSyncBanner(message, kind="error", backupPath="") {
  let banner=document.getElementById("syncBanner");
  if(!banner){
    banner=document.createElement("div"); banner.id="syncBanner"; banner.className="sync-banner";
    const shell=document.querySelector(".app-shell"), workspace=document.querySelector(".workspace");
    if(shell) shell.insertBefore(banner,workspace||shell.firstChild);
  }
  banner.className="sync-banner "+kind;
  banner.innerHTML='<span class="sync-banner-msg">'+escapeHtml(message)+'</span>'+(backupPath?'<span class="sync-banner-backup">Backup: <code>'+escapeHtml(backupPath)+'</code></span>':'')+'<button class="sync-banner-close">×</button>';
  banner.hidden=false;
  banner.querySelector(".sync-banner-close").onclick=()=>{banner.hidden=true;};
}
function hideSyncBanner(){const b=document.getElementById("syncBanner");if(b)b.hidden=true;}

const editor = document.getElementById("editor");
const lineNumbers = document.getElementById("lineNumbers");
const statusEl = document.getElementById("status");
const terminal = document.getElementById("terminalOutput");
const modelSelect = document.getElementById("modelSelect");
const modelCurrent = document.getElementById("modelCurrent");
const patchList = document.getElementById("patchList");
const evolveInput = document.getElementById("evolveInput");

function updateLines() {
  const count = editor.value.split("\n").length || 1;
  lineNumbers.textContent = Array.from({ length: count }, (_, i) => i + 1).join("\n");
}

function syncStatus() {
  const before = editor.value.slice(0, editor.selectionStart);
  const lines = before.split("\n");
  const col = (lines.at(-1) || "").length + 1;
  document.querySelector(".statusbar span").textContent = `Ln ${lines.length}, Col ${col}`;
}

function setStatus(text) { statusEl.textContent = text; }

async function refreshModelHealth() {
  const selected = modelSelect?.value;
  const badge = document.getElementById("modelStatus");
  if (!selected) return;
  if (badge) {
    badge.textContent = "checking";
    badge.dataset.status = "checking";
  }
  try {
    const data = await api("/api/health?model=" + encodeURIComponent(selected));
    const m = data.model || {};
    const status = m.status || "unknown";
    const backend = m.backend || (selected === "mock" ? "mock" : "");
    const label = status === "ready" ? "online" : status.replace(/-/g, " ");
    if (badge) {
      badge.textContent = label + (backend ? " · " + backend : "");
      badge.dataset.status = status;
      badge.title = JSON.stringify(m);
    }
    if (modelCurrent) modelCurrent.textContent = selected;
  } catch (err) {
    if (badge) {
      badge.textContent = "unavailable";
      badge.dataset.status = "error";
      badge.title = err.message;
    }
  }
}

async function loadAvailableModels() {
  if (!modelSelect) return;
  try {
    const data = await api("/api/models");
    const models = Array.isArray(data.models) ? data.models : [];
    const previous = localStorage.getItem("dc_model");
    modelSelect.innerHTML = "";
    const groups = new Map();
    for (const model of models) {
      const provider = model.provider || "other";
      if (!groups.has(provider)) {
        const group = document.createElement("optgroup");
        group.label = provider === "mock" ? "Offline / development" : provider;
        groups.set(provider, group);
        modelSelect.appendChild(group);
      }
      const option = document.createElement("option");
      option.value = model.id;
      option.textContent = model.name + (model.real ? "" : " (mock)");
      option.dataset.status = model.status || "unknown";
      option.dataset.real = model.real ? "true" : "false";
      groups.get(provider).appendChild(option);
    }
    if (!models.length) {
      const option = document.createElement("option");
      option.value = "mock";
      option.textContent = "Mock / offline";
      modelSelect.appendChild(option);
    }
    const validPrevious = [...modelSelect.options].some((o) => o.value === previous);
    const firstReal = [...modelSelect.options].find((o) => o.dataset.real === "true");
    modelSelect.value = validPrevious ? previous : (firstReal?.value || "mock");
    modelCurrent.textContent = modelSelect.value;
    localStorage.setItem("dc_model", modelSelect.value);
    await refreshModelHealth();
  } catch (err) {
    // Never leave pretend model names selected when discovery is unavailable.
    modelSelect.innerHTML = '<option value="mock">Mock / offline</option>';
    modelSelect.value = "mock";
    modelCurrent.textContent = "mock";
    localStorage.setItem("dc_model", "mock");
    await refreshModelHealth();
    toast("Model discovery unavailable — using explicit Mock / offline mode", "info", 4500);
  }
}

function setTerminal(text) {
  terminal.textContent = text;
  terminal.scrollTop = terminal.scrollHeight;
}

async function api(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`${res.status}: ${err}`);
  }
  return res.json();
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function toast(msg, type = "info", ms = 3200) {
  const root = document.getElementById("toasts");
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.innerHTML = `<span class="toast-msg">${escapeHtml(msg)}</span><span class="toast-close">×</span>`;
  el.querySelector(".toast-close").onclick = () => { if (el && el.remove) el.remove(); };
  root.appendChild(el);
  setTimeout(() => el.remove(), ms);
}

function showModal({ title, bodyHtml, onApply, applyLabel = "Apply" }) {
  const root = document.getElementById("modalRoot");
  root.innerHTML = `
    <div class="modal-backdrop">
      <div class="modal">
        <div class="modal-head">
          <h3>${escapeHtml(title)}</h3>
          <button class="btn" id="modalClose">✕</button>
        </div>
        <div class="modal-body">${bodyHtml}</div>
        <div class="modal-foot">
          <button class="btn" id="modalCancel">Cancel</button>
          <button class="btn primary" id="modalApply">${escapeHtml(applyLabel)}</button>
        </div>
      </div>
    </div>`;
  const close = () => (root.innerHTML = "");
  root.querySelector("#modalClose").onclick = close;
  root.querySelector("#modalCancel").onclick = close;
  root.querySelector(".modal-backdrop").addEventListener("click", (e) => {
    if (e.target.classList.contains("modal-backdrop")) close();
  });
  root.querySelector("#modalApply").onclick = () => { onApply?.(); close(); };
}

let githubSaveTimer = null;
let githubSyncPromise = Promise.resolve();
let githubSyncConfigured = false;

function setGithubSyncState(label, state = "") {
  const el = document.getElementById("githubSyncState");
  if (!el) return;
  el.textContent = "GitHub: " + label;
  el.dataset.state = state;
}

async function refreshWorkspaceGitStatus() {
  const el = document.getElementById("workspaceGitState");
  if (!el) return;
  try {
    const data = await api("/api/workspace");
    if (!data.configured) {
      el.textContent = "Git: no workspace";
      return;
    }
    const branch = data.branch || "detached";
    const lines = (data.status?.stdout || "").split("\n").filter(Boolean);
    const dirty = lines.filter(x => !x.startsWith("##")).length;
    el.textContent = `Git: ${branch}${dirty ? " · " + dirty + " changed" : " · clean"}`;
    el.dataset.state = dirty ? "dirty" : "clean";
  } catch (_) {
    el.textContent = "Git: offline";
    el.dataset.state = "error";
  }
}

async function refreshGithubSyncStatus() {
  try {
    const data = await api("/api/github/status");
    githubSyncConfigured = Boolean(data.configured);
    if (data.configured) setGithubSyncState(data.repo + " · " + data.branch, "ready");
    else setGithubSyncState("not configured", "off");
  } catch (_) {
    githubSyncConfigured = false;
    setGithubSyncState("backend offline", "error");
  }
}

async function saveCurrentFileLive() {
  if (!currentPath) return;
  const content = editor.value;
  fileBuffers[currentPath] = content;
  setGithubSyncState(githubSyncConfigured ? "syncing…" : "local only", githubSyncConfigured ? "syncing" : "off");
  try {
    const data = await api("/api/files/save", {
      method: "POST",
      body: JSON.stringify({
        path: currentPath,
        content,
        language: langFromPath(currentPath),
        sync_github: true,
        commit_message: "DreamCoder live edit: " + currentPath,
      }),
    });
    const gh = data.github || {};
    if (gh.ok) {
      setGithubSyncState("synced ✓", "ready");
      setStatus("Saved · GitHub synced");
    } else if (gh.skipped) {
      setGithubSyncState("local only", "off");
      setStatus("Saved locally");
    } else {
      setGithubSyncState("sync error", "error");
      setStatus("Saved · GitHub sync failed");
      showSyncBanner("Local save succeeded, but GitHub sync failed", "error", gh.backup?.path || "");
      toast("Local save succeeded, but GitHub sync failed", "error");
    }
  } catch (err) {
    setGithubSyncState("sync error", "error");
    setStatus("Local edit pending");
    showSyncBanner("Local save request failed; your editor contents are still open.", "error");
  }
}

function scheduleLiveSave() {
  clearTimeout(githubSaveTimer);
  githubSaveTimer = setTimeout(() => {
    githubSyncPromise = githubSyncPromise.catch(() => {}).then(saveCurrentFileLive);
  }, 900);
}

editor.addEventListener("input", () => {
  updateLines();
  syncStatus();
  setStatus("Modified · syncing…");
  scheduleLiveSave();
});
editor.addEventListener("click", syncStatus);
editor.addEventListener("keyup", syncStatus);
updateLines();

document.getElementById("termClear").onclick = () => setTerminal("$ ");

async function runCode() {
  const btn = document.getElementById("runBtn");
  btn.disabled = true;
  setStatus("Running…");
  setTerminal("$ dreamcoder run\n\nConnecting to backend…");
  try {
    const data = await api("/api/run", {
      method: "POST",
      body: JSON.stringify({ code: editor.value, language: "python", filename: "main.py" }),
    });
    setTerminal(data.output);
    setStatus(data.exit_code === 0 ? "Ready" : "Error");
    toast(data.exit_code === 0 ? "Run finished" : "Syntax error", data.exit_code === 0 ? "success" : "error");
  } catch (err) {
    setTerminal(`$ dreamcoder run\n\n✗ Backend unreachable\n  ${err.message}\n\nStart backend:\n  cd backend && python -m uvicorn main:app --reload --port 8000`);
    setStatus("Offline");
    toast("Backend offline", "error");
  } finally {
    btn.disabled = false;
  }
}
document.getElementById("runBtn").onclick = runCode;
document.getElementById("agentBtn")?.addEventListener("click", runProjectAgent);
async function syncProjectToGithub() {
  const btn = document.getElementById("githubSyncBtn");
  if (btn) btn.disabled = true;
  setGithubSyncState("syncing…", "syncing");
  try {
    const data = await api("/api/github/sync", { method: "POST" });
    const failed = (data.results || []).filter(r => !r.ok && !r.skipped);
    if (failed.length) throw new Error(failed[0].error || "GitHub rejected a file");
    if ((data.results || []).some(r => r.ok)) {
      setGithubSyncState("synced ✓", "ready");
      toast("Project synced to GitHub", "success");
    } else {
      setGithubSyncState("local only", "off");
      toast("GitHub autosync is not configured", "info");
    }
  } catch (err) {
    setGithubSyncState("sync error", "error");
    toast("GitHub sync failed: " + err.message, "error");
  } finally {
    if (btn) btn.disabled = false;
  }
}
document.getElementById("githubSyncBtn")?.addEventListener("click", syncProjectToGithub);

async function runProjectAgent() {
  const goal = prompt("What should DreamCoder change in this project?", document.getElementById("projectGoal")?.value || "");
  if (!goal?.trim()) return;
  const model = modelSelect.value;
  setStatus("Agent planning…");
  setTerminal("$ dreamcoder agent\n\nPlanning with " + model + "…");
  try {
    const data = await api("/api/agent/run", {
      method: "POST",
      body: JSON.stringify({ goal: goal.trim(), cwd: "", model, auto_apply: false }),
    });
    renderAgentRun(data);
  } catch (err) {
    setStatus("Agent error");
    toast("Agent failed: " + err.message, "error");
  }
}

function renderAgentRun(data) {
  const steps = (data.plan || []).map((s, i) => `${i + 1}. ${escapeHtml(s.title)}`).join("<br>");
  const changes = (data.changes || []).filter(c => c && c.path).map(c => `<div class="agent-change"><strong><span class="change-type" data-type="${escapeHtml(c.change_type || "PROJECT_MODIFY")}">${escapeHtml(c.change_type || "PROJECT_MODIFY")}</span>${escapeHtml(c.path)}</strong><span>${escapeHtml(c.summary || "proposed change")}</span>${c.diff ? '<pre class="analysis-diff">' + escapeHtml(c.diff) + '</pre>' : ''}</div>`).join("");
  const body = `
    <div class="muted">Model: ${escapeHtml(data.model || modelSelect.value)} · Status: ${escapeHtml(data.status || "unknown")}</div>
    <div class="analysis-section">Plan</div><div class="analysis-model-note">${steps || "No plan returned."}</div>
    ${changes ? '<div class="analysis-section">Proposed changes</div>' + changes : ""}
    ${data.validation?.stderr ? '<div class="analysis-section">Validation</div><pre class="analysis-diff">' + escapeHtml(data.validation.stderr) + '</pre>' : ""}
  `;
  if (data.sync_warnings?.length) {
    const w=data.sync_warnings[0];
    showSyncBanner("GitHub sync failed for "+(w.path||"a changed file"),"error",w.backup_path||"");
  }
  const needsChangesApproval = data.status === "awaiting_approval" && changes;
  showModal({
    title: needsChangesApproval ? "Review model changes" : "Project agent plan",
    bodyHtml: body,
    applyLabel: needsChangesApproval ? "Apply changes" : "Generate changes",
    onApply: async () => {
      try {
        const next = await api("/api/agent/runs/" + encodeURIComponent(data.id) + "/approve", {
          method: "POST",
          body: JSON.stringify({ auto_apply: Boolean(needsChangesApproval) }),
        });
        renderAgentRun(next);
        if (next.status === "completed") {
          setStatus("Ready");
          setTerminal("$ dreamcoder agent\n\n✓ Agent completed and tests passed.\n" + ((next.validation && next.validation.stdout) || ""));
          toast("Agent completed", "success");
        } else {
          setStatus("Agent: " + next.status);
        }
      } catch (err) {
        toast("Agent approval failed: " + err.message, "error");
      }
    },
  });
}


async function getSuggestions() {
  const btn = document.getElementById("suggestBtn");
  btn.disabled = true;
  setStatus("Analyzing…");
  setTerminal("$ dreamcoder ai suggest\n\nSending context to model…");
  try {
    const data = await api("/api/ai/suggest", {
      method: "POST",
      body: JSON.stringify({
        model: modelSelect.value,
        language: "python",
        code: editor.value,
        selection: editor.value.substring(editor.selectionStart, editor.selectionEnd),
        filename: "main.py",
        use_cache: true,
      }),
    });
    renderSuggestions(data.suggestions);
    renderInsights(data.architecture_insights || []);
    renderHealth(data.health || {}, data.latency_ms, data.cached);
    setTerminal(`$ dreamcoder ai suggest\n\nModel: ${data.model}${data.cached ? " (cached)" : ""}\n→ ${data.suggestions.length} suggestions\n→ ${(data.architecture_insights || []).length} insights\nDone in ${data.latency_ms}ms`);
    setStatus("Ready");
    toast(`${data.suggestions.length} suggestions · ${data.latency_ms}ms`, "success");
  } catch (err) {
    setTerminal(`$ dreamcoder ai suggest\n\n✗ ${err.message}`);
    setStatus("Offline");
    toast("Suggest failed – backend offline?", "error");
  } finally {
    btn.disabled = false;
  }
}
document.getElementById("suggestBtn").onclick = getSuggestions;

modelSelect.onchange = async () => {
  modelCurrent.textContent = modelSelect.value;
  localStorage.setItem("dc_model", modelSelect.value);
  setStatus(`Model: ${modelSelect.value}`);
  await refreshModelHealth();
  toast(`Model → ${modelSelect.value}`, "info");
};

function renderSuggestions(suggestions) {
  const card = document.getElementById("suggestionsCard");
  card.querySelector(".card-head").innerHTML = `<span>Code Suggestions</span><span>${suggestions.length}</span>`;
  card.querySelectorAll(".suggestion, #sugEmpty").forEach((el) => el.remove());
  if (!suggestions.length) {
    const empty = document.createElement("div");
    empty.id = "sugEmpty";
    empty.className = "muted";
    empty.textContent = "No suggestions yet";
    card.appendChild(empty);
    return;
  }
  suggestions.forEach((s, i) => {
    const row = document.createElement("div");
    row.className = "suggestion";
    row.innerHTML = `
      <b>${String(i + 1).padStart(2, "0")}</b>
      <span style="flex:1">
        <strong>${escapeHtml(s.title)}</strong>
        <small>${escapeHtml(s.description)}</small>
        <div class="actions">
          <button class="apply">Apply</button>
          <button class="preview">Preview</button>
        </div>
      </span>`;
    row.querySelector(".apply").onclick = (e) => {
      e.stopPropagation();
      insertSuggestion(s.code);
      toast("Suggestion applied", "success");
    };
    row.querySelector(".preview").onclick = (e) => {
      e.stopPropagation();
      showModal({
        title: s.title,
        bodyHtml: `<p class="muted" style="margin:0 0 10px">${escapeHtml(s.description)}</p><pre>${escapeHtml(s.code)}</pre>`,
        applyLabel: "Insert into editor",
        onApply: () => { insertSuggestion(s.code); toast("Suggestion applied", "success"); },
      });
    };
    card.appendChild(row);
  });
}

function renderInsights(insights) {
  const card = document.getElementById("insightsCard");
  card.querySelector(".card-head").innerHTML = `<span>App Structure</span><span>${insights.length}</span>`;
  card.querySelectorAll(".insight").forEach((el) => el.remove());
  insights.forEach((ins) => {
    const div = document.createElement("div");
    div.className = "insight";
    div.innerHTML = `<span class="icon">${ins.icon || "•"}</span><div><strong>${escapeHtml(ins.title)}</strong><small>${escapeHtml(ins.detail || "")}</small></div>`;
    card.appendChild(div);
  });
}

function renderHealth(health, latency, cached) {
  const score = health.score ?? 87;
  document.getElementById("healthScore").textContent = `${score}%`;
  document.getElementById("healthBar").style.width = `${score}%`;
  document.getElementById("healthGrid").innerHTML = `
    <span>✓ ${health.files_indexed ?? "—"} files</span>
    <span>✓ ${health.symbols ?? "—"} symbols</span>
    <span>⚡ ${latency ?? health.ai_latency_ms ?? "—"}ms</span>
    <span>${cached ? "📦 cached" : "● live"}</span>`;
}

function insertSuggestion(snippet) {
  const start = editor.selectionStart, end = editor.selectionEnd;
  editor.setRangeText("\n# AI suggestion\n" + snippet + "\n", start, end, "end");
  updateLines(); syncStatus(); setStatus("Suggestion inserted");
}

/* ---- Evolve: live self-update ---- */

function renderPatches(patches) {
  patchList.innerHTML = "";
  if (!patches?.length) return;
  patches.forEach((p) => {
    const el = document.createElement("div");
    el.className = "patch";
    el.innerHTML = `
      <div class="patch-head">
        <span class="patch-title">${escapeHtml(p.title)}</span>
        <span class="patch-meta">${escapeHtml(p.target || "ui")}</span>
      </div>
      <div class="muted">${escapeHtml(p.description || "")}</div>
      <pre>${escapeHtml((p.code || "").slice(0, 600))}${(p.code || "").length > 600 ? "…" : ""}</pre>
      <div class="patch-actions">
        <button class="apply">Apply live</button>
        <button class="dismiss">Dismiss</button>
      </div>`;
    el.querySelector(".apply").onclick = () => applyPatch(p, el);
    el.querySelector(".dismiss").onclick = () => { if (el && el.remove) el.remove(); };
    patchList.appendChild(el);
  });
}

function applyPatch(patch, el) {
  if (!patch) return;
  if (patch.diff && !patch._confirmed) {
    showModal({
      title:"Review change: "+(patch.title||"patch"),
      bodyHtml:'<p class="muted">'+escapeHtml(patch.description||"")+'</p><div class="diff-toggle"><button class="btn diff-mode active" data-mode="unified">Unified</button><button class="btn diff-mode" data-mode="split">Side-by-side</button></div><pre class="diff-unified">'+escapeHtml(patch.diff)+'</pre><div class="diff-split" hidden>'+renderSplitDiff(patch.diff)+'</div>',
      applyLabel:"Apply",
      onApply:()=>applyPatch({...patch,_confirmed:true},el)
    });
    const root=document.getElementById("modalRoot");
    root?.querySelectorAll(".diff-mode").forEach(btn=>btn.onclick=()=>{
      root.querySelectorAll(".diff-mode").forEach(b=>b.classList.toggle("active",b===btn));
      const split=btn.dataset.mode==="split"; root.querySelector(".diff-unified").hidden=split; root.querySelector(".diff-split").hidden=!split;
    });
    return;
  }
  return applyPatchUnsafe(patch,el);
}
function renderSplitDiff(unified) {
  const lines=(unified||"").split("\n"),left=[],right=[];
  for(const line of lines){
    if(line.startsWith("-")&&!line.startsWith("---"))left.push(line);
    else if(line.startsWith("+")&&!line.startsWith("+++"))right.push(line);
    else{left.push(line);right.push(line);}
  }
  return '<div class="diff-cols"><pre class="diff-col">'+escapeHtml(left.join("\n"))+'</pre><pre class="diff-col">'+escapeHtml(right.join("\n"))+'</pre></div>';
}

function applyPatchUnsafe(patch, el) {
  if (!patch) return;
  const target = (patch.target || "css").toLowerCase();
  const code = patch.code || "";
  try {
    if (target === "css" || target === "style") {
      const style = document.createElement("style");
      style.textContent = code;
      document.head.appendChild(style);
      toast(`Applied CSS: ${patch.title}`, "success");
    } else if (target === "js" || target === "script") {
      const fn = new Function(code);
      fn();
      toast(`Applied JS: ${patch.title}`, "success");
    } else if (target === "html") {
      const slot = document.querySelector(".ai-panel");
      const wrap = document.createElement("div");
      wrap.className = "card";
      wrap.innerHTML = code;
      slot.insertBefore(wrap, slot.children[1] || null);
      toast(`Injected UI: ${patch.title}`, "success");
    } else {
      showModal({
        title: patch.title,
        bodyHtml: `<pre>${escapeHtml(code)}</pre>`,
        applyLabel: "Copy",
        onApply: () => { navigator.clipboard?.writeText(code); toast("Copied", "info"); },
      });
      return;
    }
    if (el && el.remove) if (el && el.remove) el.remove();
    setTerminal((terminal.textContent || "") + `\n\n$ evolve apply\n✓ Live patch: ${patch.title}`);
  } catch (err) {
    toast(`Patch failed: ${err.message}`, "error");
  }
}

function localEvolveFallback(prompt) {
  const p = prompt.toLowerCase();
  const patches = [];
  if (p.includes("shortcut") || p.includes("help") || p.includes("overlay")) {
    patches.push({
      id: "demo-help", title: "Keyboard shortcut overlay",
      description: "Floating help panel for Ctrl shortcuts",
      target: "html",
      code: `<div class="card-head"><span>⌨ Shortcuts</span><span class="badge">LIVE</span></div>
<div class="muted" style="line-height:1.7">
  <div><span class="kbd">Ctrl</span>+<span class="kbd">Enter</span> Run</div>
  <div><span class="kbd">Ctrl</span>+<span class="kbd">Shift</span>+<span class="kbd">S</span> Suggest</div>
  <div><span class="kbd">Ctrl</span>+<span class="kbd">E</span> Evolve</div>
</div>`,
    });
  }
  if (p.includes("terminal") || p.includes("font")) {
    patches.push({
      id: "demo-term", title: "Larger terminal",
      description: "Taller terminal + better contrast",
      target: "css",
      code: `.terminal{height:180px !important}
.terminal pre{font-size:12.5px !important;color:#c5d4e8 !important}`,
    });
  }
  if (p.includes("theme") || p.includes("transition") || p.includes("polish")) {
    patches.push({
      id: "demo-theme", title: "Smoother theme transitions",
      description: "Animate colors on theme switch",
      target: "css",
      code: `body,.app-shell,.files,.ai-panel,.editor-area,.topbar,.card{
  transition: background-color .35s ease, border-color .35s ease, color .25s ease;
}`,
    });
  }
  if (p.includes("file") || p.includes("tree") || p.includes("icon")) {
    patches.push({
      id: "demo-tree", title: "File tree accent",
      description: "Accent border on hover / active file",
      target: "css",
      code: `.file:hover{border-left:2px solid var(--accent);padding-left:10px}
.file.active-file{border-left:2px solid var(--accent2);padding-left:10px}`,
    });
  }
  if (p.includes("minimap") || p.includes("overview")) {
    patches.push({
      id: "demo-minimap", title: "Editor side accent bar",
      description: "Visual stand-in for a minimap",
      target: "css",
      code: `.editor-wrap{position:relative}
.editor-wrap::after{
  content:"";position:absolute;top:8px;right:6px;width:28px;height:calc(100% - 16px);
  background:linear-gradient(180deg,#7c8cff22,#4de0b811);border-radius:4px;
  border:1px solid #7c8cff22;pointer-events:none;
}`,
    });
  }
  if (/(more\s*theme|more\s*color|more\s*colour|add\s*theme|theme)/i.test(text)) {
    patches.push({
      id: "more-themes-local",
      title: "Add extra themes",
      description: "Peach, Shroom, Ocean, Ember buttons",
      target: "js",
      code: "['peach','shroom','ocean','ember','rose','mint','sand'].forEach(function(n){var row=document.querySelector('.theme-row');if(!row)return;if(document.querySelector('[data-theme=\''+n+'\']'))return;var b=document.createElement('button');b.className='theme';b.setAttribute('data-theme',n);b.textContent=n.charAt(0).toUpperCase()+n.slice(1);b.onclick=function(){if(typeof applyTheme==='function')applyTheme(n);};row.appendChild(b);});if(typeof toast==='function')toast('Themes expanded','success');",
    });
  }
  if (/(particle)/i.test(text)) {
    patches.push({
      id: "particles-fix",
      title: "Force-enable visible particles",
      description: "Rebuild particle layer",
      target: "js",
      code: "if(typeof setParticles==='function'){setParticles(false);setTimeout(function(){setParticles(true);},50);}",
    });
  }
  if (/(remove|hide).*(theme|these)/i.test(text)) {
    patches.push({
      id: "hide-themes-local",
      title: "Hide theme buttons",
      description: "Hide the theme row",
      target: "css",
      code: ".theme-row{display:none!important}",
    });
  }
  if (!patches.length) {
    patches.push({
      id: "demo-generic", title: "Evolve button pulse",
      description: "Subtle live pulse on Evolve control",
      target: "css",
      code: `.btn.evolve{animation:evolvePulse 2.2s infinite}
@keyframes evolvePulse{0%,100%{box-shadow:0 0 0 0 #4de0b833}50%{box-shadow:0 0 0 6px #4de0b800}}`,
    });
  }
  return { patches, model: "local-demo", latency_ms: 40 };
}

async function evolveApp(prompt) {
  const text = (prompt || evolveInput.value || "").trim();
  if (!text) { toast("Describe what to add or change", "info"); return; }
  const btn = document.getElementById("evolveSend");
  if (btn) btn.disabled = true;
  setStatus("Evolving…");
  setTerminal(`$ dreamcoder evolve\n\n"${text}"\n\nApplying UI changes…`);

  const applyAll = (patches) => {
    renderPatches(patches || []);
    (patches || []).forEach((p) => {
      try { applyPatch(p, null); } catch (e) { console.warn("patch", e); }
    });
  };

  try {
    const data = await api("/api/ai/evolve", {
      method: "POST",
      body: JSON.stringify({
        model: modelSelect.value,
        prompt: text,
        current_ui: {
          themes: ["midnight", "graphite", "violet", "peach", "shroom", "ocean", "ember"],
          panels: ["explorer", "editor", "terminal", "ai-assistant", "evolve"],
          features: ["run", "suggest", "evolve", "model-select", "health"],
        },
      }),
    });
    const patches = data.patches || [];
    applyAll(patches);
    setTerminal(`$ dreamcoder evolve\n\n"${text}"\n\nModel: ${data.model}\n→ Applied ${patches.length} change(s) in ${data.latency_ms}ms`);
    setStatus("Ready");
    toast(patches.length ? `Applied ${patches.length} change(s)` : "No matching patches", "success");
    evolveInput.value = "";
  } catch (err) {
    const demo = localEvolveFallback(text);
    applyAll(demo.patches);
    setTerminal(`$ dreamcoder evolve\n\n"${text}"\n\nLocal apply (backend offline)\n→ ${demo.patches.length} change(s)`);
    setStatus("Offline");
    toast(`Applied ${demo.patches.length} local change(s)`, "success");
  } finally {
    if (btn) btn.disabled = false;
  }
}


document.getElementById("evolveSend").onclick = () => evolveApp();
document.getElementById("evolveBtn").onclick = () => {
  evolveInput.focus();
  if (evolveInput.value.trim()) evolveApp();
  else toast("Type a change, or click a chip", "info");
};
document.getElementById("evolveChips").onclick = (e) => {
  const chip = e.target.closest(".chip");
  if (!chip) return;
  evolveInput.value = chip.dataset.prompt || chip.textContent;
  evolveApp(chip.dataset.prompt);
};
evolveInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); evolveApp(); }
});

document.querySelectorAll(".theme").forEach((btn) => {
  btn.onclick = () => {
    document.querySelectorAll(".theme").forEach((x) => x.classList.remove("active-theme"));
    btn.classList.add("active-theme");
    const t = btn.dataset.theme;
    if (t === "graphite") {
      document.documentElement.style.setProperty("--bg", "#101214");
      document.documentElement.style.setProperty("--panel", "#17191c");
      document.documentElement.style.setProperty("--accent", "#7c8cff");
    } else if (t === "violet") {
      document.documentElement.style.setProperty("--accent", "#b48cff");
      document.documentElement.style.setProperty("--bg", "#0e0b14");
      document.documentElement.style.setProperty("--panel", "#11151e");
    } else {
      document.documentElement.style.setProperty("--bg", "#0b0e14");
      document.documentElement.style.setProperty("--panel", "#11151e");
      document.documentElement.style.setProperty("--accent", "#7c8cff");
    }
    toast(`Theme: ${t}`, "info", 1500);
  };
});

document.addEventListener("keydown", (e) => {
  if (e.ctrlKey && e.key === "Enter") { e.preventDefault(); runCode(); }
  if (e.ctrlKey && e.shiftKey && (e.key === "S" || e.key === "s")) { e.preventDefault(); getSuggestions(); }
  if (e.ctrlKey && (e.key === "e" || e.key === "E")) { e.preventDefault(); evolveInput.focus(); }
});

(async () => {
  try {
    await api("/api/health");
    setStatus("Backend online");
    document.getElementById("liveDot").textContent = "LIVE";
    toast("Backend connected", "success", 2000);
  } catch {
    setStatus("Backend offline");
    document.getElementById("liveDot").textContent = "OFFLINE";
    document.getElementById("liveDot").style.color = "#ff6b7a";
    toast("Backend offline – Evolve still works with demo patches", "info", 4000);
  }
})();

/* ========== Multi-file buffer ========== */
const fileBuffers = {
  "src/main.py": editor.value,
  "src/ai_router.py": "class AIRouter:\n    def get_model(self, name: str):\n        ...\n",
  "src/suggestions.py": "# suggestions helpers\n",
  "src/cache.py": "# cache layer\n",
};
let currentPath = "src/main.py";

document.querySelectorAll(".file[data-path]").forEach((btn) => {
  btn.addEventListener("click", () => {
    const path = btn.dataset.path;
    if (!path) return;
    if (!(path in fileBuffers)) fileBuffers[path] = fileBuffers[path] || "";
    openPath(path);
  });
});

/* ========== Ask All models ========== */
async function askAllModels() {
  const btn = document.getElementById("askAllBtn");
  if (btn) btn.disabled = true;
  setStatus("Asking all models…");
  setTerminal("$ dreamcoder ask-all\n\nFiring parallel requests…");
  try {
    const catalog = await api("/api/models");
    const discovered = (catalog.models || []).filter(m => m.real).map(m => m.id).slice(0, 5);
    const models = discovered.length ? discovered : ["mock"];
    const data = await api("/api/ai/suggest-all", {
      method: "POST",
      body: JSON.stringify({
        models,
        code: editor.value,
        language: "python",
        filename: currentPath,
      }),
    });
    let out = `$ dreamcoder ask-all\n\nTotal ${data.total_latency_ms}ms\n\n`;
    const allSug = [];
    (data.results || []).forEach((r) => {
      out += `── ${r.model} ${r.ok ? "✓" : "✗"} (${r.latency_ms || "—"}ms)${r.cached ? " cached" : ""}\n`;
      (r.suggestions || []).forEach((s) => {
        out += `  • ${s.title}\n`;
        allSug.push({ ...s, title: `[${r.model}] ${s.title}` });
      });
      out += "\n";
    });
    setTerminal(out);
    renderSuggestions(allSug.slice(0, 12));
    setStatus("Ready");
    toast(`All models responded · ${data.total_latency_ms}ms`, "success");
  } catch (err) {
    setTerminal(`$ dreamcoder ask-all\n\n✗ ${err.message}`);
    toast("Ask All failed", "error");
    setStatus("Offline");
  } finally {
    if (btn) btn.disabled = false;
  }
}
const askAllBtn = document.getElementById("askAllBtn");
if (askAllBtn) askAllBtn.onclick = askAllModels;

/* ========== WebSocket streaming ========== */
let streamWs = null;

function streamComplete() {
  const btn = document.getElementById("streamBtn");
  if (btn) btn.disabled = true;
  setStatus("Streaming…");
  setTerminal("$ dreamcoder stream\n\nConnecting WebSocket…\n\n");

  const wsUrl = API_BASE.replace(/^http/, "ws") + "/ws/complete";
  try {
    streamWs = new WebSocket(wsUrl);
  } catch (e) {
    setTerminal(`$ dreamcoder stream\n\n✗ Cannot open WebSocket: ${e.message}`);
    if (btn) btn.disabled = false;
    return;
  }

  let buffer = "";
  streamWs.onopen = () => {
    streamWs.send(JSON.stringify({
      model: modelSelect.value,
      code: editor.value,
      language: "python",
      prompt: "Improve and continue this code with clear comments.",
    }));
  };
  streamWs.onmessage = (ev) => {
    try {
      const msg = JSON.parse(ev.data);
      if (msg.type === "start") {
        setTerminal(`$ dreamcoder stream\n\nModel: ${msg.model}\n\n`);
      } else if (msg.type === "token") {
        buffer += msg.text;
        setTerminal(`$ dreamcoder stream\n\n${buffer}`);
      } else if (msg.type === "done") {
        setTerminal(`$ dreamcoder stream\n\n${buffer}\n\n── done · ${msg.model} · ${msg.latency_ms}ms · ${msg.suggestion_count} suggestions`);
        setStatus("Ready");
        toast(`Stream complete · ${msg.latency_ms}ms`, "success");
        if (btn) btn.disabled = false;
        // offer to insert
        if (buffer.trim()) {
          showModal({
            title: "Streamed completion",
            bodyHtml: `<pre>${escapeHtml(buffer.slice(0, 3000))}</pre>`,
            applyLabel: "Insert at cursor",
            onApply: () => {
              insertSuggestion(buffer.trim());
              toast("Inserted streamed output", "success");
            },
          });
        }
      } else if (msg.type === "error") {
        setTerminal((terminal.textContent || "") + `\n✗ ${msg.message}`);
        if (btn) btn.disabled = false;
      }
    } catch (_) {}
  };
  streamWs.onerror = () => {
    setTerminal((terminal.textContent || "") + "\n✗ WebSocket error – is the backend running?");
    toast("Stream failed", "error");
    if (btn) btn.disabled = false;
  };
  streamWs.onclose = () => {
    if (btn) btn.disabled = false;
  };
}
const streamBtn = document.getElementById("streamBtn");
if (streamBtn) streamBtn.onclick = streamComplete;

/* extra shortcuts */
document.addEventListener("keydown", (e) => {
  if (e.ctrlKey && !e.shiftKey && (e.key === "a" || e.key === "A") && document.activeElement !== editor && document.activeElement !== evolveInput) {
    // only when not typing in inputs – actually Ctrl+A is select-all in editor; use Ctrl+Shift+A
  }
  if (e.ctrlKey && e.shiftKey && (e.key === "A" || e.key === "a")) {
    e.preventDefault();
    askAllModels();
  }
  if (e.ctrlKey && e.shiftKey && (e.key === "T" || e.key === "t")) {
    e.preventDefault();
    streamComplete();
  }
});

/* ========== Project context ========== */
async function loadProjectContext() {
  try {
    const ctx = await api("/api/project/context");
    document.getElementById("projectGoal").value = ctx.goal || "";
    document.getElementById("projectCmd").value = (ctx.commands && ctx.commands[0]) || "";
  } catch (_) {}
}

async function saveProjectContext() {
  const goal = document.getElementById("projectGoal").value.trim();
  const cmd = document.getElementById("projectCmd").value.trim();
  try {
    await api("/api/project/context", {
      method: "POST",
      body: JSON.stringify({ goal, description: goal, commands: cmd ? [cmd] : [] }),
    });
    toast("Project context saved", "success");
    refreshMonitor();
  } catch (err) {
    toast("Could not save context", "error");
  }
}
document.getElementById("saveContextBtn").onclick = saveProjectContext;

/* ========== Live monitor ========== */
function appendChat(role, content) {
  const log = document.getElementById("chatLog");
  const bubble = document.createElement("div");
  bubble.className = `chat-bubble ${role}`;
  const meta = role === "user" ? "You" : "Monitor";
  bubble.innerHTML = `<div class="meta">${meta}</div>${escapeHtml(content).replace(/\n/g, "<br>")}`;
  log.appendChild(bubble);
  log.scrollTop = log.scrollHeight;
}

async function refreshMonitor() {
  try {
    const data = await api("/api/ai/monitor");
    const box = document.getElementById("monitorInsights");
    box.innerHTML = (data.insights || [])
      .map(
        (i) =>
          `<div style="margin-bottom:5px"><strong>${escapeHtml(i.icon || "•")} ${escapeHtml(
            i.title
          )}</strong><br><span class="muted">${escapeHtml(i.detail || "")}</span></div>`
      )
      .join("");
    if (data.goal) {
      document.getElementById("monitorBadge").textContent = "GOAL SET";
    }
  } catch (_) {
    document.getElementById("monitorInsights").textContent =
      "Monitor offline – start backend for live project pulse.";
  }
}

async function sendChat(msg) {
  const text = (msg || document.getElementById("chatInput").value || "").trim();
  if (!text) return;
  appendChat("user", text);
  document.getElementById("chatInput").value = "";
  setStatus("Monitor thinking…");
  try {
    const data = await api("/api/ai/chat", {
      method: "POST",
      body: JSON.stringify({ message: text, model: modelSelect.value }),
    });
    appendChat("assistant", (data.model ? `[${data.model}${data.backend ? ` · ${data.backend}` : ""}]\n` : "") + (data.content || "(empty reply)"));
    setStatus("Ready");
    // If analysis payload, also render analysis card
    if (data.analysis) renderAnalysis(data.analysis);
    toast("Monitor replied", "success", 1800);
  } catch (err) {
    appendChat("assistant", `Offline: ${err.message}\n\nStart the backend to enable project-aware chat.`);
    setStatus("Offline");
  }
}

document.getElementById("chatSend").onclick = () => sendChat();
document.getElementById("chatInput").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendChat();
  }
});
document.getElementById("chatChips").onclick = (e) => {
  const chip = e.target.closest(".chip");
  if (!chip) return;
  sendChat(chip.dataset.chat || chip.textContent);
};

/* ========== Folder analysis ========== */
function openAnalysisDrawer() {
  const drawer = document.getElementById("analysisDrawer");
  const tab = document.getElementById("analysisTab");
  const backdrop = document.getElementById("analysisBackdrop");
  if (!drawer) return;
  drawer.classList.add("open");
  drawer.setAttribute("aria-hidden", "false");
  tab?.classList.add("open");
  tab?.setAttribute("aria-expanded", "true");
  if (backdrop) backdrop.hidden = false;
}
function closeAnalysisDrawer() {
  const drawer = document.getElementById("analysisDrawer");
  const tab = document.getElementById("analysisTab");
  const backdrop = document.getElementById("analysisBackdrop");
  drawer?.classList.remove("open");
  drawer?.setAttribute("aria-hidden", "true");
  tab?.classList.remove("open");
  tab?.setAttribute("aria-expanded", "false");
  if (backdrop) backdrop.hidden = true;
}
function initAnalysisDrawer() {
  const tab = document.getElementById("analysisTab");
  const close = document.getElementById("analysisClose");
  const backdrop = document.getElementById("analysisBackdrop");
  tab?.addEventListener("mouseenter", openAnalysisDrawer);
  tab?.addEventListener("click", () => {
    const open = document.getElementById("analysisDrawer")?.classList.contains("open");
    open ? closeAnalysisDrawer() : openAnalysisDrawer();
  });
  close?.addEventListener("click", closeAnalysisDrawer);
  backdrop?.addEventListener("click", closeAnalysisDrawer);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeAnalysisDrawer();
  });
}
initAnalysisDrawer();

function renderAnalysis(data) {
  openAnalysisDrawer();
  const modelInfo = data.model_analysis || {};
  const health = data.health ?? "—";
  document.getElementById("analysisTabHealth").textContent = health + "%";
  document.getElementById("analysisHealthDrawer").textContent = health + "%";
  document.getElementById("analysisModelDrawer").textContent =
    (modelInfo.model || modelSelect.value) + (modelInfo.backend ? " · " + modelInfo.backend : "");
  document.getElementById("analysisScope").textContent =
    "Current indexed folder only · " + ((data.scope && data.scope.files) || []).length + " files";
  document.getElementById("analysisSummaryDrawer").textContent =
    modelInfo.summary || data.summary || "";
  document.getElementById("analysisProjectType").innerHTML =
    "<strong>Project type:</strong> " + escapeHtml(modelInfo.project_type || "Not identified yet");

  let html = "";
  if (modelInfo.architecture?.length) {
    html += '<div class="analysis-section">Architecture</div><div class="analysis-model-note">' +
      modelInfo.architecture.map(escapeHtml).join("<br>") + "</div>";
  }
  if (modelInfo.strengths?.length) {
    html += '<div class="analysis-section">What is already working</div><div class="analysis-model-note">' +
      modelInfo.strengths.map(escapeHtml).join("<br>") + "</div>";
  }
  if (modelInfo.risks?.length) {
    html += '<div class="analysis-section">Risks / opportunities</div><div class="analysis-model-note">' +
      modelInfo.risks.map(escapeHtml).join("<br>") + "</div>";
  }

  const actions = data.actions || [];
  if (actions.length) {
    html += '<div class="analysis-section">Model-proposed live updates</div>';
    actions.forEach((a, i) => {
      html += '<div class="analysis-recommendation" data-analysis-action="' + i + '">' +
        '<div class="rec-head"><span class="rec-title">' + escapeHtml(a.title) + '</span>' +
        '<span class="rec-priority">' + escapeHtml(a.priority || "medium") + '</span></div>' +
        (a.path ? '<div class="rec-path">' + escapeHtml(a.path) + '</div>' : '') +
        '<div class="rec-detail">' + escapeHtml(a.detail || a.instruction || "") + '</div>' +
        (a.instruction ? '<div class="rec-detail"><strong>Model instruction:</strong> ' + escapeHtml(a.instruction) + '</div>' : '') +
        '<div class="rec-actions">' +
        (a.path ? '<button class="btn primary" data-generate-analysis="' + i + '">Generate update</button>' : '') +
        '</div></div>';
    });
  } else {
    html += '<div class="analysis-model-note">No model recommendations were returned for this folder. Try another selected model or refine the project goal.</div>';
  }

  const reports = data.file_reports || [];
  if (reports.length) {
    html += '<div class="analysis-section">File findings</div>';
    reports.forEach((f) => {
      const findings = [...(f.issues || []), ...(f.ideas || [])].slice(0, 4);
      if (!findings.length) return;
      html += '<div class="analysis-recommendation">' +
        '<div class="rec-title">' + escapeHtml(f.path) + '</div>' +
        '<div class="rec-detail">' + findings.map(escapeHtml).join('<br>') + '</div>' +
        '</div>';
    });
  }

  document.getElementById("analysisBodyDrawer").innerHTML = html;
  window._analysisActions = actions;
  window._analysisProposals = {};
  document.getElementById("analysisBodyDrawer").onclick = async (e) => {
    const generate = e.target.closest("[data-generate-analysis]");
    const apply = e.target.closest("[data-apply-analysis]");
    if (generate) {
      const idx = Number(generate.dataset.generateAnalysis);
      await generateAnalysisUpdate(idx);
    }
    if (apply) {
      const idx = Number(apply.dataset.applyAnalysis);
      await applyAnalysisProposal(idx);
    }
  };
}

async function generateAnalysisUpdate(index) {
  const action = (window._analysisActions || [])[index];
  if (!action?.path) return;
  const card = document.querySelector('[data-analysis-action="' + index + '"]');
  const button = card?.querySelector("[data-generate-analysis]");
  if (button) { button.disabled = true; button.textContent = "Generating…"; }
  try {
    const data = await api("/api/ai/analyze-action", {
      method: "POST",
      body: JSON.stringify({
        model: modelSelect.value,
        path: action.path,
        instruction: action.instruction || action.detail || action.title,
        project_type: document.getElementById("analysisProjectType")?.textContent || "",
      }),
    });
    window._analysisProposals[index] = data;
    if (card) {
      card.querySelector(".rec-actions").innerHTML =
        '<button class="btn" data-apply-analysis="' + index + '">Apply live</button>';
      const diff = document.createElement("div");
      diff.className = "analysis-diff";
      diff.textContent = data.diff || "(model made no file changes)";
      card.appendChild(diff);
    }
    toast("Model update generated — review the diff", "success");
  } catch (err) {
    if (button) { button.disabled = false; button.textContent = "Generate update"; }
    toast("Model update failed: " + err.message, "error");
  }
}

async function applyAnalysisProposal(index) {
  const proposal = (window._analysisProposals || {})[index];
  if (!proposal?.path || proposal.content == null) return;
  const action = (window._analysisActions || [])[index] || {};
  fileBuffers[proposal.path] = proposal.content;
  renderFileTree(Object.keys(fileBuffers));
  openPath(proposal.path);
  await api("/api/files/save", {
    method: "POST",
    body: JSON.stringify({
      path: proposal.path,
      content: proposal.content,
      language: langFromPath(proposal.path),
    }),
  });
  toast("Applied model update: " + (action.title || proposal.path), "success");
  setTerminal("$ dreamcoder model-update\\n\\n✓ " + proposal.path + "\\n  " + (proposal.summary || ""));
  refreshMonitor();
  closeAnalysisDrawer();
}


async function runFolderAnalysis() {
  const btn = document.getElementById("analyzeBtn");
  if (btn) btn.disabled = true;
  openAnalysisDrawer();
  setStatus("Analyzing folder with selected model…");
  setTerminal("$ dreamcoder analyze-folder\\n\\nScanning the indexed folder…");
  try {
    const data = await api("/api/ai/analyze-folder", {
      method: "POST",
      body: JSON.stringify({ model: modelSelect.value }),
    });
    renderAnalysis(data);
    setTerminal(
      "$ dreamcoder analyze-folder\\n\\n" +
      data.summary + "\\n\\n" +
      "Scope: " + ((data.scope && data.scope.files) || []).length + " indexed files\\n" +
      "Model: " + ((data.model_analysis && data.model_analysis.model) || modelSelect.value) + "\\n" +
      "Done in " + data.latency_ms + "ms"
    );
    setStatus("Ready");
    toast("Folder analysis complete", "success");
  } catch (err) {
    setTerminal("$ dreamcoder analyze-folder\\n\\n✗ " + err.message);
    toast("Analysis failed – selected model unavailable?", "error");
    setStatus("Offline");
  } finally {
    if (btn) btn.disabled = false;
  }
}
const analyzeBtn = document.getElementById("analyzeBtn");
if (analyzeBtn) analyzeBtn.onclick = runFolderAnalysis;

/* boot extras */
loadProjectContext();
refreshGithubSyncStatus();
refreshWorkspaceGitStatus();
setInterval(refreshWorkspaceGitStatus, 5000);
refreshMonitor();
setInterval(refreshMonitor, 45000); // keep monitor fresh

/* ========== Chat mode: Project vs General ========== */
let chatMode = "project";
const modeProjectBtn = document.getElementById("modeProject");
const modeGeneralBtn = document.getElementById("modeGeneral");
if (modeProjectBtn && modeGeneralBtn) {
  modeProjectBtn.onclick = () => {
    chatMode = "project";
    modeProjectBtn.classList.add("active-theme");
    modeGeneralBtn.classList.remove("active-theme");
    document.getElementById("monitorBadge").textContent = "PROJECT";
    document.getElementById("chatInput").placeholder = "Ask about this project, code, next steps…";
    toast("Chat mode: Project", "info", 1500);
  };
  modeGeneralBtn.onclick = () => {
    chatMode = "general";
    modeGeneralBtn.classList.add("active-theme");
    modeProjectBtn.classList.remove("active-theme");
    document.getElementById("monitorBadge").textContent = "GENERAL";
    document.getElementById("chatInput").placeholder = "Ask anything — coding concepts, ideas, general questions…";
    toast("Chat mode: General", "info", 1500);
  };
}

// Patch sendChat to include mode (override previous by redefining)
const _origSendChat = typeof sendChat === "function" ? sendChat : null;
async function sendChat(msg) {
  const text = (msg || document.getElementById("chatInput").value || "").trim();
  if (!text) return;
  appendChat("user", text);
  document.getElementById("chatInput").value = "";
  setStatus(chatMode === "general" ? "General chat…" : "Monitor thinking…");
  try {
    const data = await api("/api/ai/chat", {
      method: "POST",
      body: JSON.stringify({ message: text, model: modelSelect.value, mode: chatMode }),
    });
    appendChat("assistant", (data.model ? `[${data.model}]\n` : "") + (data.content || "(empty reply)"));
    setStatus("Ready");
    if (data.analysis) renderAnalysis(data.analysis);
    // Optional live updates from analysis / chat
    if (data.actions && data.actions.length) {
      const wrap = document.createElement("div");
      wrap.className = "chat-bubble assistant";
      wrap.innerHTML = "<div class=\"meta\">Live fixes</div>";
      data.actions.slice(0, 8).forEach((a, i) => {
        if (!a.path && a.target === "note") return;
        const row = document.createElement("div");
        row.style.marginTop = "6px";
        row.innerHTML = `<button class="btn primary" style="width:100%;margin-top:4px" data-ca="${i}">Apply: ${escapeHtml(a.title || a.id || "fix")}</button>`;
        wrap.appendChild(row);
      });
      wrap.onclick = (e) => {
        const b = e.target.closest("[data-ca]");
        if (!b) return;
        const a = data.actions[Number(b.dataset.ca)];
        if (!a) return;
        if (a.path && a.code != null && typeof applyAnalysisAction === "function") applyAnalysisAction(a);
        else if (typeof applyPatch === "function") applyPatch(a, null);
      };
      document.getElementById("chatLog")?.appendChild(wrap);
    }
    toast(chatMode === "general" ? "General reply" : "Project reply", "success", 1600);
  } catch (err) {
    appendChat("assistant", `Offline: ${err.message}`);
    setStatus("Offline");
  }
}
document.getElementById("chatSend").onclick = () => sendChat();
document.getElementById("chatInput").onkeydown = (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendChat();
  }
};

/* ========== Drag & drop folders / files ========== */
const TEXT_EXTS = new Set([
  "py","js","ts","tsx","jsx","html","css","md","json","toml","yaml","yml",
  "txt","rs","go","java","c","cpp","h","hpp","rb","php","sh","bat","ps1",
  "sql","env","ini","cfg","xml","svg",
]);

function langFromPath(path) {
  const ext = (path.split(".").pop() || "").toLowerCase();
  return {
    py: "python", js: "javascript", ts: "typescript", tsx: "typescript",
    jsx: "javascript", html: "html", css: "css", md: "markdown", json: "json",
  }[ext] || "text";
}

function readEntryFile(fileEntry) {
  return new Promise((resolve, reject) => {
    fileEntry.file((file) => {
      const reader = new FileReader();
      reader.onload = () => resolve({ path: fileEntry.fullPath.replace(/^\//, ""), content: reader.result, file });
      reader.onerror = reject;
      reader.readAsText(file);
    }, reject);
  });
}

function readDirectory(dirEntry) {
  return new Promise((resolve) => {
    const reader = dirEntry.createReader();
    const all = [];
    const readBatch = () => {
      reader.readEntries(async (entries) => {
        if (!entries.length) {
          resolve(all);
          return;
        }
        for (const entry of entries) {
          if (entry.isFile) all.push(entry);
          else if (entry.isDirectory) {
            if (entry.name.startsWith(".") || entry.name === "node_modules" || entry.name === "__pycache__" || entry.name === "venv") continue;
            const sub = await readDirectory(entry);
            all.push(...sub);
          }
        }
        readBatch();
      });
    };
    readBatch();
  });
}

async function collectDroppedItems(dataTransfer) {
  const items = dataTransfer.items;
  const fileEntries = [];
  if (items && items.length) {
    const entries = [];
    for (let i = 0; i < items.length; i++) {
      const entry = items[i].webkitGetAsEntry?.();
      if (entry) entries.push(entry);
    }
    for (const entry of entries) {
      if (entry.isFile) fileEntries.push(entry);
      else if (entry.isDirectory) {
        const sub = await readDirectory(entry);
        fileEntries.push(...sub);
      }
    }
  }
  // Fallback: plain files list
  if (!fileEntries.length && dataTransfer.files?.length) {
    return Array.from(dataTransfer.files).map((f) => ({
      path: f.webkitRelativePath || f.name,
      content: null,
      file: f,
    }));
  }
  const results = [];
  for (const entry of fileEntries) {
    try {
      const r = await readEntryFile(entry);
      results.push(r);
    } catch (_) {}
  }
  return results;
}

async function readFileBlob(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsText(file);
  });
}

async function ingestFiles(rawList, rootName, replaceExisting = false) {
  const payload = [];
  for (const item of rawList) {
    const path = (item.path || item.file?.name || "file").replace(/\\/g, "/");
    const ext = path.split(".").pop()?.toLowerCase() || "";
    if (ext && !TEXT_EXTS.has(ext)) continue;
    if (path.split("/").some((p) => p.startsWith(".") || p === "node_modules" || p === "__pycache__")) continue;
    let content = item.content;
    if (content == null && item.file) {
      try {
        content = await readFileBlob(item.file);
      } catch (_) {
        continue;
      }
    }
    if (typeof content !== "string") continue;
    // skip huge files
    if (content.length > 400000) continue;
    payload.push({ path, content, language: langFromPath(path) });
  }
  if (!payload.length) {
    toast("No text source files found in drop", "info");
    return;
  }

  if (replaceExisting) {
    fileBuffers = {};
    currentPath = "";
    renderFileTree([]);
  }

  setStatus(`Indexing ${payload.length} files…`);
  setTerminal(`$ dreamcoder import\n\nIndexing ${payload.length} files from drop…`);

  // Update local buffers + tree
  payload.forEach((f) => {
    fileBuffers[f.path] = f.content;
  });
  renderFileTree(Object.keys(fileBuffers));
  if (rootName) {
    document.getElementById("projectNameLabel").textContent = `◈ ${rootName}`;
  }

  // Open first file
  const first = payload[0];
  if (first) {
    currentPath = first.path;
    editor.value = first.content;
    updateLines();
    syncStatus();
    const tab = document.querySelector(".tab.active");
    if (tab) tab.innerHTML = `${first.path.split("/").pop()} <span>×</span>`;
  }

  try {
    const data = await api("/api/files/bulk", {
      method: "POST",
      body: JSON.stringify({ files: payload, root_name: rootName || "dropped-project", replace_existing: replaceExisting }),
    });
    setTerminal(
      `$ dreamcoder import\n\n✓ Indexed ${data.indexed} files\n` +
        `  symbols: ${data.stats?.symbols ?? "—"}\n` +
        `  root: ${data.root_name}`
    );
    setStatus("Ready");
    toast(`Imported ${data.indexed} files`, "success");
    refreshMonitor();
  } catch (err) {
    setTerminal(`$ dreamcoder import\n\n✓ Loaded ${payload.length} files locally\n✗ Backend index failed: ${err.message}`);
    setStatus("Local only");
    toast(`Loaded ${payload.length} files (backend offline)`, "info");
  }
}

async function openNativeWorkspace(root) {
  try {
    const data = await api("/api/workspace", { method: "POST", body: JSON.stringify({ root }) });
    await api("/api/watch", { method: "POST", body: JSON.stringify({ root }) });
    setStatus("Workspace connected");
    toast("Connected " + data.root, "success");
    await refreshWorkspaceGitStatus();
    await refreshMonitor();
    const listing = await api("/api/files");
    const files = listing?.files || [];
    fileBuffers = {};
    const paths = files.map(f => f.path).filter(Boolean);
    renderFileTree(paths);
    const first = paths[0];
    if (first) {
      const file = await api("/api/files/" + encodeURIComponent(first));
      fileBuffers[first] = file.content || "";
      openPath(first);
    }
  } catch (err) {
    toast("Workspace connection failed: " + err.message, "error");
    setStatus("Workspace error");
  }
}

function renderFileTree(paths) {
  const tree = document.getElementById("fileTree");
  if (!tree) return;
  // Group by top-level folder
  const sorted = [...paths].sort();
  tree.innerHTML = "";
  let lastDir = null;
  sorted.forEach((path) => {
    const parts = path.split("/");
    if (parts.length > 1) {
      const dir = parts[0];
      if (dir !== lastDir) {
        lastDir = dir;
        const folderBtn = document.createElement("button");
        folderBtn.className = "file active";
        folderBtn.textContent = `▾ ${dir}`;
        tree.appendChild(folderBtn);
      }
    }
    const btn = document.createElement("button");
    btn.className = "file" + (parts.length > 1 ? " indent" : "");
    if (path === currentPath) btn.classList.add("active-file");
    btn.dataset.path = path;
    btn.textContent = `◇ ${parts[parts.length - 1]}`;
    btn.onclick = () => openPath(path);
    tree.appendChild(btn);
  });
}

function openPath(path) {
  if (!path) return;
  const previousPath = currentPath;
  const previousContent = editor.value;
  fileBuffers[previousPath] = previousContent;

  if (previousPath && previousPath !== path) {
    githubSyncPromise = githubSyncPromise.catch(() => {}).then(async () => {
      try {
        const data = await api("/api/files/save", {
          method: "POST",
          body: JSON.stringify({
            path: previousPath,
            content: previousContent,
            language: langFromPath(previousPath),
            sync_github: true,
            commit_message: "DreamCoder file switch save: " + previousPath,
          }),
        });
        if (data.github?.ok) setGithubSyncState("synced ✓", "ready");
      } catch (_) {}
    });
  }

  if (!(path in fileBuffers)) fileBuffers[path] = "";
  currentPath = path;
  editor.value = fileBuffers[path] || "";
  updateLines();
  syncStatus();
  document.querySelectorAll(".file").forEach((f) => {
    f.classList.toggle("active-file", f.dataset.path === path);
  });
  if (typeof renderTabs === "function") renderTabs();
  setStatus(`Opened ${path}`);
}

// Drop zone wiring
const dropZone = document.getElementById("dropZone");
const folderInput = document.getElementById("folderInput");
const filesInput = document.getElementById("filesInput");

if (dropZone) {
  ["dragenter", "dragover"].forEach((ev) => {
    dropZone.addEventListener(ev, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropZone.classList.add("drag-over");
    });
  });
  ["dragleave", "drop"].forEach((ev) => {
    dropZone.addEventListener(ev, (e) => {
      e.preventDefault();
      e.stopPropagation();
      if (ev === "dragleave") dropZone.classList.remove("drag-over");
    });
  });
  dropZone.addEventListener("drop", async (e) => {
    dropZone.classList.remove("drag-over");
    const list = await collectDroppedItems(e.dataTransfer);
    let rootName = "dropped-project";
    if (e.dataTransfer.items?.[0]) {
      const entry = e.dataTransfer.items[0].webkitGetAsEntry?.();
      if (entry?.isDirectory) rootName = entry.name;
    }
    await ingestFiles(list, rootName, true);
  });
  dropZone.addEventListener("click", (e) => {
    if (e.target.closest("input")) return;
    // default open folder picker
    folderInput?.click();
  });
}

document.getElementById("browseFolderBtn")?.addEventListener("click", async (e) => {
  e.stopPropagation();
  if (window.dreamcoderDesktop?.chooseFolder) {
    const root = await window.dreamcoderDesktop.chooseFolder();
    if (root) await openNativeWorkspace(root);
    return;
  }
  folderInput?.click();
});
document.getElementById("browseFilesBtn")?.addEventListener("click", (e) => {
  e.stopPropagation();
  filesInput?.click();
});

folderInput?.addEventListener("change", async () => {
  const files = Array.from(folderInput.files || []);
  const list = files.map((f) => ({ path: f.webkitRelativePath || f.name, content: null, file: f }));
  const rootName = files[0]?.webkitRelativePath?.split("/")[0] || "folder";
  await ingestFiles(list, rootName);
  folderInput.value = "";
});

filesInput?.addEventListener("change", async () => {
  const files = Array.from(filesInput.files || []);
  const list = files.map((f) => ({ path: f.name, content: null, file: f }));
  await ingestFiles(list, "files");
  filesInput.value = "";
});

// Also allow dropping on the whole workspace
document.querySelector(".workspace")?.addEventListener("dragover", (e) => {
  e.preventDefault();
});
document.querySelector(".workspace")?.addEventListener("drop", async (e) => {
  if (e.target.closest("#dropZone")) return;
  e.preventDefault();
  const list = await collectDroppedItems(e.dataTransfer);
  if (list.length) await ingestFiles(list, "dropped-project", true);
});

/* ========== Hugging Face catalog ========== */
let hfCatalog = { organized: {}, models: [] };
let hfCategory = "all";

async function loadHfCatalog(search = "", refresh = false) {
  const list = document.getElementById("hfModelList");
  if (!list) return;
  list.textContent = refresh ? "Refreshing from Hugging Face…" : "Loading open models…";
  try {
    const q = new URLSearchParams();
    if (search) q.set("search", search);
    if (refresh) q.set("refresh", "true");
    const data = await api("/api/models/huggingface?" + q.toString());
    hfCatalog = data;
    renderHfCategories(data.organized || {});
    renderHfModels(data);
    const n = data.total || (data.models || []).length;
    toast(`${n} HF models${data.cached ? " (cached)" : ""}`, "success", 2000);
  } catch (err) {
    list.textContent = "Could not load HF catalog – backend offline? Curated list still available when API is up.";
  }
}

function renderHfCategories(organized) {
  const el = document.getElementById("hfCategories");
  if (!el) return;
  const cats = ["all", ...Object.keys(organized).filter((k) => (organized[k] || []).length)];
  el.innerHTML = cats
    .map(
      (c) =>
        `<button class="chip${c === hfCategory ? " active-theme" : ""}" data-hf-cat="${c}" type="button">${c}</button>`
    )
    .join("");
  el.onclick = (e) => {
    const btn = e.target.closest("[data-hf-cat]");
    if (!btn) return;
    hfCategory = btn.dataset.hfCat;
    renderHfCategories(hfCatalog.organized || {});
    renderHfModels(hfCatalog);
  };
}

function renderHfModels(data) {
  const list = document.getElementById("hfModelList");
  if (!list) return;
  let models = data.models || [];
  if (hfCategory !== "all" && data.organized?.[hfCategory]) {
    models = data.organized[hfCategory];
  }
  if (!models.length) {
    list.textContent = "No models in this category.";
    return;
  }
  list.innerHTML = "";
  models.slice(0, 40).forEach((m) => {
    const btn = document.createElement("button");
    btn.className = "hf-item";
    btn.type = "button";
    btn.innerHTML = `
      <span class="hf-id">${escapeHtml(m.id || m.name)}</span>
      <span class="hf-meta">${escapeHtml(m.category || "")} · ↓${formatNum(m.downloads)} · ♥${formatNum(m.likes)} · ${escapeHtml(m.source || "")}</span>`;
    btn.onclick = () => selectHfModel(m);
    list.appendChild(btn);
  });
}

function formatNum(n) {
  n = Number(n) || 0;
  if (n >= 1e6) return (n / 1e6).toFixed(1) + "M";
  if (n >= 1e3) return (n / 1e3).toFixed(1) + "k";
  return String(n);
}

async function selectHfModel(m) {
  const id = m.id || m.name;
  modelCurrent.textContent = id.split("/").pop();
  // Add to select if missing
  let opt = [...modelSelect.options].find((o) => o.value === id);
  if (!opt) {
    opt = document.createElement("option");
    opt.value = id;
    opt.textContent = id;
    modelSelect.appendChild(opt);
  }
  modelSelect.value = id;
  document.querySelectorAll(".hf-item").forEach((el) => el.classList.remove("active-hf"));
  // mark clicked roughly
  toast(`HF model → ${id}`, "success");
  setStatus(`Model: ${id}`);
  try {
    await api("/api/models/huggingface/select", {
      method: "POST",
      body: JSON.stringify({ model_id: id }),
    });
  } catch (_) {}
}

document.getElementById("hfRefresh")?.addEventListener("click", () => {
  loadHfCatalog(document.getElementById("hfSearch")?.value || "", true);
});
document.getElementById("hfSearch")?.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    loadHfCatalog(e.target.value || "", false);
  }
});

// Load catalog on boot
setTimeout(() => loadHfCatalog(), 800);

/* ========== Refresh / update animation ========== */
let _refreshTimer = null;
function playRefreshAnimation(label = "Updating…") {
  const overlay = document.getElementById("refreshOverlay");
  const text = document.getElementById("refreshText");
  const shell = document.querySelector(".app-shell");
  if (text) text.textContent = label;
  if (overlay) overlay.classList.add("show");
  if (shell) shell.classList.add("updating");
  document.querySelector(".topbar")?.classList.add("flash-update");
  clearTimeout(_refreshTimer);
  _refreshTimer = setTimeout(() => {
    overlay?.classList.remove("show");
    shell?.classList.remove("updating");
    document.querySelector(".topbar")?.classList.remove("flash-update");
  }, 650);
}

// Wrap toast to optionally trigger refresh feel on success updates
const _toast = toast;
toast = function (msg, type = "info", ms = 3200) {
  if (type === "success") playRefreshAnimation(msg);
  return _toast(msg, type, ms);
};

// Explicit refresh on major actions
const _runCode = runCode;
runCode = async function () {
  playRefreshAnimation("Running…");
  return _runCode.apply(this, arguments);
};
const _getSuggestions = getSuggestions;
getSuggestions = async function () {
  playRefreshAnimation("Suggesting…");
  return _getSuggestions.apply(this, arguments);
};
if (typeof askAllModels === "function") {
  const _askAll = askAllModels;
  askAllModels = async function () {
    playRefreshAnimation("Asking all models…");
    return _askAll.apply(this, arguments);
  };
}
if (typeof runFolderAnalysis === "function") {
  const _an = runFolderAnalysis;
  runFolderAnalysis = async function () {
    playRefreshAnimation("Analyzing folder…");
    return _an.apply(this, arguments);
  };
}
if (typeof loadHfCatalog === "function") {
  const _hf = loadHfCatalog;
  loadHfCatalog = async function () {
    playRefreshAnimation("Loading HF models…");
    return _hf.apply(this, arguments);
  };
}
if (typeof ingestFiles === "function") {
  const _ing = ingestFiles;
  ingestFiles = async function () {
    playRefreshAnimation("Importing files…");
    return _ing.apply(this, arguments);
  };
}
if (typeof evolveApp === "function") {
  const _ev = evolveApp;
  evolveApp = async function (prompt) {
    playRefreshAnimation("Evolving…");
    return _ev(prompt);
  };
}

// Keyboard: Ctrl+Shift+D → debug page
document.addEventListener("keydown", (e) => {
  if (e.ctrlKey && e.shiftKey && (e.key === "D" || e.key === "d")) {
    e.preventDefault();
    window.location.href = "debug.html";
  }
});

/* ========== Generate Project ========== */
let lastGenerated = null;

async function generateProject(downloadZip = false) {
  const prompt = (document.getElementById("generatePrompt")?.value || "").trim();
  if (!prompt) {
    toast("Describe the project to generate", "info");
    return;
  }
  playRefreshAnimation(downloadZip ? "Packaging zip…" : "Generating project…");
  setStatus("Generating…");
  setTerminal(`$ dreamcoder generate\n\n"${prompt.slice(0, 120)}…"\n\nScaffolding multi-file project…`);
  try {
    if (downloadZip) {
      const res = await fetch(`${API_BASE}/api/ai/generate-project/zip`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt,
          goal: document.getElementById("projectGoal")?.value || "",
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      const blob = await res.blob();
      const disp = res.headers.get("Content-Disposition") || "";
      const match = /filename="?([^"]+)"?/.exec(disp);
      const filename = match?.[1] || "project.zip";
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = filename;
      a.click();
      URL.revokeObjectURL(a.href);
      setTerminal(`$ dreamcoder generate --zip\n\n✓ Downloaded ${filename}`);
      toast(`Downloaded ${filename}`, "success");
      setStatus("Ready");
      return;
    }

    const data = await api("/api/ai/generate-project", {
      method: "POST",
      body: JSON.stringify({
        prompt,
        goal: document.getElementById("projectGoal")?.value || "",
      }),
    });
    lastGenerated = data;
    renderGenerated(data);
    setTerminal(
      `$ dreamcoder generate\n\n${data.summary}\n` +
        `Stack: ${data.stack?.language} / ${data.stack?.build}\n` +
        `Files: ${data.file_count}\n` +
        `Run: ${data.run_hint}\n` +
        `Done in ${data.latency_ms}ms`
    );
    setStatus("Ready");
    toast(data.summary, "success");
    appendChat("assistant", `${data.summary}\n\nRun hint:\n${data.run_hint}\n\nClick “Load into workspace” or Download zip.`);
  } catch (err) {
    setTerminal(`$ dreamcoder generate\n\n✗ ${err.message}`);
    toast("Generate failed", "error");
    setStatus("Offline");
  }
}

function renderGenerated(data) {
  const pagesEl = document.getElementById("generatePages");
  const filesEl = document.getElementById("generateFiles");
  const applyRow = document.getElementById("generateApplyRow");
  if (pagesEl) {
    pagesEl.innerHTML = (data.pages || [])
      .map((p, i) => `<div style="margin:3px 0"><b>${i + 1}. ${escapeHtml(p.title)}</b> — ${escapeHtml(p.detail || "")}</div>`)
      .join("");
  }
  if (filesEl) {
    filesEl.innerHTML = "";
    (data.files || []).forEach((f) => {
      const btn = document.createElement("button");
      btn.className = "hf-item";
      btn.type = "button";
      btn.innerHTML = `<span class="hf-id">${escapeHtml(f.path)}</span><span class="hf-meta">${(f.content || "").length} chars</span>`;
      btn.onclick = () => {
        showModal({
          title: f.path,
          bodyHtml: `<pre>${escapeHtml((f.content || "").slice(0, 4000))}</pre>`,
          applyLabel: "Open in editor",
          onApply: () => {
            fileBuffers[f.path] = f.content || "";
            openPath(f.path);
          },
        });
      };
      filesEl.appendChild(btn);
    });
  }
  if (applyRow) applyRow.style.display = data.files?.length ? "flex" : "none";
}

async function loadGeneratedIntoWorkspace() {
  if (!lastGenerated?.files?.length) {
    toast("Generate a project first", "info");
    return;
  }
  playRefreshAnimation("Writing + building project…");
  setStatus("Building generated project…");
  setTerminal("$ dreamcoder generate --build\\n\\nWriting generated files to the connected workspace…");
  try {
    const result = await api("/api/ai/generate-project/build", {
      method: "POST",
      body: JSON.stringify({ files: lastGenerated.files, name: lastGenerated.name || "generated-app", stack: lastGenerated.stack || {}, sync_github: true }),
    });
    lastGenerated.build = result;
    const files = lastGenerated.files;
    files.forEach((f) => { fileBuffers[f.path] = f.content || ""; });
    renderFileTree(Object.keys(fileBuffers));
    document.getElementById("projectNameLabel").textContent = `◈ ${lastGenerated.name || "generated"}`;
    const first = files[0];
    if (first) openPath(first.path);
    const v = result.validation || {};
    setTerminal(
      `$ dreamcoder generate --build\\n\\n` +
      `Project: ${result.name}\\n` +
      `Files written: ${result.file_count}\\n` +
      `Build: ${result.build_command || "materialized only"}\\n` +
      `${result.ok ? "✓ BUILD PASSED" : "✗ BUILD FAILED"}\\n\\n` +
      `${v.stdout || ""}${v.stderr || ""}${v.error || ""}`
    );
    if (result.ok) {
      setStatus("Build passed");
      toast(`Built ${result.name} successfully`, "success");
    } else {
      setStatus("Build failed");
      toast("Project was written, but the build failed. Use the validation output to self-heal.", "error", 5000);
    }
    refreshMonitor();
    refreshWorkspaceGitStatus();
  } catch (err) {
    setTerminal(`$ dreamcoder generate --build\\n\\n✗ ${err.message}`);
    setStatus("Build failed");
    toast("Build/load failed: " + err.message, "error");
  }
}

document.getElementById("generateBtn")?.addEventListener("click", () => {
  document.getElementById("generatePrompt")?.focus();
  toast("Describe the app below, then Generate", "info");
});
document.getElementById("generateGoBtn")?.addEventListener("click", () => generateProject(false));
document.getElementById("generateZipBtn")?.addEventListener("click", () => generateProject(true));
document.getElementById("generateApplyBtn")?.addEventListener("click", loadGeneratedIntoWorkspace);

/* ========== Self-Heal ========== */
async function runSelfHeal() {
  const errorText = (document.getElementById("healError")?.value || "").trim();
  if (!errorText) {
    toast("Paste an error message first", "info");
    return;
  }
  playRefreshAnimation("Self-healing…");
  const files = Object.keys(fileBuffers).map((path) => ({ path, content: fileBuffers[path] }));
  try {
    const data = await api("/api/ai/self-heal", {
      method: "POST",
      body: JSON.stringify({
        error_text: errorText,
        language: langFromPath(currentPath),
        files: files.slice(0, 40),
      }),
    });
    const box = document.getElementById("healResult");
    let html = (data.reasons || []).map((r) => `• ${escapeHtml(r)}`).join("<br>");
    if (data.patches?.length) {
      html += `<div style="margin-top:8px;font-weight:650">Patches (${data.patches.length})</div>`;
      data.patches.forEach((p) => {
        html += `<div class="hf-item"><span class="hf-id">${escapeHtml(p.action)} ${escapeHtml(p.path)}</span></div>`;
      });
      html += `<button class="btn primary" id="applyHealBtn" style="margin-top:8px;width:100%">Apply patches</button>`;
    }
    box.innerHTML = html || "No automatic fix found.";
    document.getElementById("applyHealBtn")?.addEventListener("click", () => {
      (data.patches || []).forEach((p) => {
        fileBuffers[p.path] = p.content || "";
      });
      renderFileTree(Object.keys(fileBuffers));
      toast("Heal patches applied", "success");
      if (data.patches[0]) openPath(data.patches[0].path);
    });
    setTerminal(`$ dreamcoder self-heal\n\n${(data.reasons || []).join("\n")}\nPatches: ${(data.patches || []).length}`);
    toast("Self-heal complete", "success");
  } catch (err) {
    toast("Self-heal failed", "error");
    setTerminal(`$ dreamcoder self-heal\n\n✗ ${err.message}`);
  }
}
document.getElementById("healBtn")?.addEventListener("click", runSelfHeal);

/* ========== Theme packs (incl. peach / shroom) ========== */
const THEMES = {
  midnight: { bg: "#0b0e14", panel: "#11151e", accent: "#7c8cff", accent2: "#4de0b8" },
  graphite: { bg: "#101214", panel: "#17191c", accent: "#7c8cff", accent2: "#4de0b8" },
  violet: { bg: "#0e0b14", panel: "#11151e", accent: "#b48cff", accent2: "#4de0b8" },
  peach: { bg: "#1a1210", panel: "#241a18", accent: "#ffb38a", accent2: "#ff8fab" },
  shroom: { bg: "#14101a", panel: "#1c1524", accent: "#e8a0bf", accent2: "#9dffb0" },
  ocean: { bg: "#0a1218", panel: "#0f1a22", accent: "#5ec8ff", accent2: "#3dffa8" },
  ember: { bg: "#140e0c", panel: "#1e1410", accent: "#ff7a45", accent2: "#ffd166" },
};

function applyTheme(name) {
  const t = THEMES[name] || THEMES.midnight;
  const root = document.documentElement;
  root.style.setProperty("--bg", t.bg);
  root.style.setProperty("--panel", t.panel);
  root.style.setProperty("--accent", t.accent);
  root.style.setProperty("--accent2", t.accent2);
  document.querySelectorAll(".theme[data-theme]").forEach((b) => {
    b.classList.toggle("active-theme", b.dataset.theme === name);
  });
  localStorage.setItem("dc_theme", name);
  playRefreshAnimation(`Theme: ${name}`);
}

// Rebind theme buttons (replace old handlers)
document.querySelectorAll(".theme[data-theme]").forEach((btn) => {
  btn.onclick = () => applyTheme(btn.dataset.theme);
});
const savedTheme = localStorage.getItem("dc_theme");
if (savedTheme && THEMES[savedTheme]) applyTheme(savedTheme);

/* ========== Interactive cursor ========== */
let cursorOn = false;
function setCursorFx(on) {
  cursorOn = on;
  document.body.classList.toggle("cursor-fx", on);
  document.getElementById("fxCursor")?.classList.toggle("active-theme", on);
  let dot = document.getElementById("cursorDot");
  let ring = document.getElementById("cursorRing");
  if (on) {
    if (!dot) {
      dot = document.createElement("div");
      dot.id = "cursorDot";
      document.body.appendChild(dot);
    }
    if (!ring) {
      ring = document.createElement("div");
      ring.id = "cursorRing";
      document.body.appendChild(ring);
    }
  } else {
    dot?.remove();
    ring?.remove();
  }
  localStorage.setItem("dc_cursor", on ? "1" : "0");
}
document.addEventListener("mousemove", (e) => {
  if (!cursorOn) return;
  const dot = document.getElementById("cursorDot");
  const ring = document.getElementById("cursorRing");
  if (dot) {
    dot.style.left = e.clientX + "px";
    dot.style.top = e.clientY + "px";
  }
  if (ring) {
    ring.style.left = e.clientX + "px";
    ring.style.top = e.clientY + "px";
  }
});
document.getElementById("fxCursor")?.addEventListener("click", () => setCursorFx(!cursorOn));
if (localStorage.getItem("dc_cursor") === "1") setCursorFx(true);

/* ========== Particles ========== */
let particlesOn = false;
let particleRaf = 0;
function setParticles(on) {
  particlesOn = !!on;
  document.getElementById("fxParticles")?.classList.toggle("active-theme", particlesOn);
  let canvas = document.getElementById("particleCanvas");
  cancelAnimationFrame(particleRaf);
  if (!particlesOn) {
    canvas?.remove();
    localStorage.setItem("dc_particles", "0");
    toast("Particles off", "info", 1200);
    return;
  }
  if (!canvas) {
    canvas = document.createElement("canvas");
    canvas.id = "particleCanvas";
    document.body.appendChild(canvas);
  }
  const ctx = canvas.getContext("2d");
  const resize = () => {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
  };
  resize();
  window.addEventListener("resize", resize);
  const opts = window.DC_PARTICLE_OPTS || {};
  const count = opts.count || 80;
  const spd = opts.speed || 0.8;
  const sz = opts.size || 2;
  const pts = Array.from({ length: count }, () => ({
    x: Math.random() * canvas.width,
    y: Math.random() * canvas.height,
    vx: (Math.random() - 0.5) * spd,
    vy: (Math.random() - 0.5) * spd,
    r: sz * (0.7 + Math.random()),
  }));
  const accent = () => getComputedStyle(document.documentElement).getPropertyValue("--accent").trim() || "#7c8cff";
  const accent2 = () => getComputedStyle(document.documentElement).getPropertyValue("--accent2").trim() || "#4de0b8";
  const loop = () => {
    if (!particlesOn) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    for (let i = 0; i < pts.length; i++) {
      const p = pts[i];
      p.x += p.vx; p.y += p.vy;
      if (p.x < 0 || p.x > canvas.width) p.vx *= -1;
      if (p.y < 0 || p.y > canvas.height) p.vy *= -1;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fillStyle = i % 2 ? accent() : accent2();
      ctx.globalAlpha = 0.65;
      ctx.fill();
    }
    ctx.globalAlpha = 0.25;
    ctx.strokeStyle = accent();
    ctx.lineWidth = 1;
    for (let i = 0; i < pts.length; i++) {
      for (let j = i + 1; j < pts.length; j++) {
        const dx = pts[i].x - pts[j].x, dy = pts[i].y - pts[j].y;
        const d = Math.hypot(dx, dy);
        if (d < 150) {
          ctx.beginPath();
          ctx.moveTo(pts[i].x, pts[i].y);
          ctx.lineTo(pts[j].x, pts[j].y);
          ctx.stroke();
        }
      }
    }
    particleRaf = requestAnimationFrame(loop);
  };
  loop();
  localStorage.setItem("dc_particles", "1");
  toast("Particles on — look at the background", "success", 2000);
}

document.getElementById("fxParticles")?.addEventListener("click", () => setParticles(!particlesOn));
if (localStorage.getItem("dc_particles") === "1") setParticles(true);

/* ========== Project tabs from saved context ========== */
const PROJECTS_KEY = "dc_projects";
function loadProjects() {
  try {
    return JSON.parse(localStorage.getItem(PROJECTS_KEY) || "[]");
  } catch {
    return [];
  }
}
function saveProjects(list) {
  localStorage.setItem(PROJECTS_KEY, JSON.stringify(list));
}
function renderProjectTabs(activeId) {
  const el = document.getElementById("projectTabs");
  if (!el) return;
  const list = loadProjects();
  el.innerHTML = list
    .map(
      (p) =>
        `<button class="project-tab${p.id === activeId ? " active-project" : ""}" data-pid="${p.id}" type="button" title="${escapeHtml(p.goal || p.name)}">${escapeHtml(p.name)} <span class="x" data-close="${p.id}">×</span></button>`
    )
    .join("");
  el.onclick = (e) => {
    const close = e.target.closest("[data-close]");
    if (close) {
      e.stopPropagation();
      const id = close.dataset.close;
      saveProjects(loadProjects().filter((p) => p.id !== id));
      renderProjectTabs();
      toast("Project tab removed", "info");
      return;
    }
    const tab = e.target.closest("[data-pid]");
    if (!tab) return;
    const id = tab.dataset.pid;
    const proj = loadProjects().find((p) => p.id === id);
    if (!proj) return;
    activateProject(proj);
  };
}

function activateProject(proj) {
  document.getElementById("projectNameLabel").textContent = `◈ ${proj.name}`;
  document.getElementById("projectGoal").value = proj.goal || "";
  document.getElementById("projectCmd").value = proj.cmd || "";
  // Restore file buffers if stored
  if (proj.files && typeof proj.files === "object") {
    Object.keys(fileBuffers).forEach((k) => delete fileBuffers[k]);
    Object.assign(fileBuffers, proj.files);
    const paths = Object.keys(fileBuffers);
    renderFileTree(paths);
    if (paths[0]) openPath(paths[0]);
  }
  renderProjectTabs(proj.id);
  localStorage.setItem("dc_active_project", proj.id);
  // sync backend context
  api("/api/project/context", {
    method: "POST",
    body: JSON.stringify({
      goal: proj.goal || "",
      description: proj.goal || "",
      commands: proj.cmd ? [proj.cmd] : [],
    }),
  }).catch(() => {});
  refreshMonitor();
  toast(`Project: ${proj.name}`, "success");
  playRefreshAnimation(`Switched to ${proj.name}`);
}

// Override save context to also create explorer project tab
const _saveCtx = saveProjectContext;
saveProjectContext = async function () {
  await _saveCtx();
  const goal = document.getElementById("projectGoal").value.trim();
  const cmd = document.getElementById("projectCmd").value.trim();
  if (!goal) return;
  const name = goal.split(/\s+/).slice(0, 3).join(" ") || "Project";
  const id = "p_" + Date.now();
  // snapshot current files
  fileBuffers[currentPath] = editor.value;
  const list = loadProjects();
  list.push({
    id,
    name: name.slice(0, 28),
    goal,
    cmd,
    files: { ...fileBuffers },
    created: Date.now(),
  });
  saveProjects(list);
  renderProjectTabs(id);
  document.getElementById("projectNameLabel").textContent = `◈ ${name.slice(0, 28)}`;
  localStorage.setItem("dc_active_project", id);
  toast(`Project tab “${name.slice(0, 28)}” created`, "success");
};

renderProjectTabs(localStorage.getItem("dc_active_project"));

/* Clarify mode difference in UI when switching */
if (modeProjectBtn && modeGeneralBtn) {
  modeProjectBtn.onclick = () => {
    chatMode = "project";
    modeProjectBtn.classList.add("active-theme");
    modeGeneralBtn.classList.remove("active-theme");
    document.getElementById("monitorBadge").textContent = "PROJECT";
    document.getElementById("chatInput").placeholder =
      "Project mode: uses your files, symbols, and goal…";
    toast("Project mode — answers grounded in this repo", "info", 2200);
  };
  modeGeneralBtn.onclick = () => {
    chatMode = "general";
    modeGeneralBtn.classList.add("active-theme");
    modeProjectBtn.classList.remove("active-theme");
    document.getElementById("monitorBadge").textContent = "GENERAL";
    document.getElementById("chatInput").placeholder =
      "General mode: any topic — not limited to this project…";
    toast("General mode — free-form chat", "info", 2200);
  };
}

/* ========== Undo stack for live patches ========== */
const undoStack = [];
function pushUndo(label, fn) {
  undoStack.push({ label, fn });
  if (undoStack.length > 30) undoStack.shift();
}
function undoLast() {
  const item = undoStack.pop();
  if (!item) {
    toast("Nothing to undo", "info");
    return;
  }
  try {
    item.fn();
    toast(`Undid: ${item.label}`, "success");
    playRefreshAnimation("Undo");
  } catch (e) {
    toast("Undo failed", "error");
  }
}
document.addEventListener("keydown", (e) => {
  if (e.ctrlKey && !e.shiftKey && (e.key === "z" || e.key === "Z")) {
    if (document.activeElement === editor || document.activeElement?.tagName === "TEXTAREA" || document.activeElement?.tagName === "INPUT") {
      // allow native undo in inputs unless alt
      if (!e.altKey) return;
    }
    e.preventDefault();
    undoLast();
  }
});

// Enhance applyPatch to support undo for CSS
const _applyPatch = applyPatch;
applyPatch = function (patch, el) {
  const target = (patch.target || "css").toLowerCase();
  if (target === "css" || target === "style") {
    const style = document.createElement("style");
    style.textContent = patch.code || "";
    document.head.appendChild(style);
    pushUndo(patch.title || "css patch", () => style.remove());
    toast(`Applied CSS: ${patch.title}`, "success");
    if (el && el.remove) if (el && el.remove) el.remove();
    setTerminal((terminal.textContent || "") + `\n\n$ evolve apply\n✓ ${patch.title}`);
    return;
  }
  if (target === "js" || target === "script") {
    try {
      const fn = new Function(patch.code || "");
      fn();
      pushUndo(patch.title || "js patch", () => toast("JS patches may need manual revert", "info"));
      toast(`Applied JS: ${patch.title}`, "success");
      if (el && el.remove) if (el && el.remove) el.remove();
    } catch (err) {
      toast(`Patch failed: ${err.message}`, "error");
    }
    return;
  }
  return _applyPatch(patch, el);
};

/* ========== Command palette (Ctrl+K) ========== */
const COMMANDS = [
  { label: "Theme: Midnight", run: () => applyTheme("midnight") },
  { label: "Theme: Graphite", run: () => applyTheme("graphite") },
  { label: "Theme: Violet", run: () => applyTheme("violet") },
  { label: "Theme: Peach", run: () => applyTheme("peach") },
  { label: "Theme: Shroom", run: () => applyTheme("shroom") },
  { label: "Theme: Ocean", run: () => applyTheme("ocean") },
  { label: "Theme: Ember", run: () => applyTheme("ember") },
  { label: "Particles on", run: () => setParticles(true) },
  { label: "Particles off", run: () => setParticles(false) },
  { label: "Cursor FX on", run: () => setCursorFx(true) },
  { label: "Cursor FX off", run: () => setCursorFx(false) },
  { label: "Run code", run: () => runCode() },
  { label: "Suggest", run: () => getSuggestions() },
  { label: "Ask all models", run: () => askAllModels() },
  { label: "Analyze folder", run: () => runFolderAnalysis() },
  { label: "Run project agent", run: () => runProjectAgent() },
  { label: "Stream completion", run: () => streamComplete() },
  { label: "Open Debug page", run: () => (window.location.href = "debug.html") },
  { label: "Undo last patch", run: () => undoLast() },
  { label: "Focus Evolve", run: () => document.getElementById("evolveInput")?.focus() },
  { label: "Focus Chat", run: () => document.getElementById("chatInput")?.focus() },
];

function openCommandPalette() {
  const pal = document.getElementById("commandPalette");
  const input = document.getElementById("cmdInput");
  if (!pal) return;
  pal.style.display = "flex";
  input.value = "";
  renderCmdResults("");
  setTimeout(() => input.focus(), 10);
}
function closeCommandPalette() {
  const pal = document.getElementById("commandPalette");
  if (pal) pal.style.display = "none";
}
function renderCmdResults(q) {
  const box = document.getElementById("cmdResults");
  if (!box) return;
  const qq = (q || "").toLowerCase();
  const items = COMMANDS.filter((c) => !qq || c.label.toLowerCase().includes(qq));
  box.innerHTML = items
    .map((c, i) => `<button class="cmd-item${i === 0 ? " active" : ""}" data-cmd="${i}" type="button">${escapeHtml(c.label)}</button>`)
    .join("");
  box._items = items;
  box.querySelectorAll(".cmd-item").forEach((btn) => {
    btn.onclick = () => {
      const c = items[Number(btn.dataset.cmd)];
      closeCommandPalette();
      c?.run();
    };
  });
}
document.getElementById("cmdInput")?.addEventListener("input", (e) => renderCmdResults(e.target.value));
document.getElementById("cmdInput")?.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeCommandPalette();
  if (e.key === "Enter") {
    const items = document.getElementById("cmdResults")?._items || [];
    if (items[0]) {
      closeCommandPalette();
      items[0].run();
    }
  }
});
document.addEventListener("keydown", (e) => {
  if (e.ctrlKey && (e.key === "k" || e.key === "K")) {
    e.preventDefault();
    openCommandPalette();
  }
  if (e.key === "Escape") closeCommandPalette();
});

// Evolve chips for themes
const evolveChips = document.getElementById("evolveChips");
if (evolveChips && !document.getElementById("chipThemePeach")) {
  const extra = [
    ["Switch to peach theme", "theme peach"],
    ["Enable particles", "particles"],
    ["Enable cursor FX", "cursor"],
    ["Compact UI", "compact"],
  ];
  extra.forEach(([label, key]) => {
    const b = document.createElement("button");
    b.className = "chip";
    b.dataset.prompt = label;
    b.textContent = label;
    if (key === "theme peach") b.id = "chipThemePeach";
    evolveChips.appendChild(b);
  });
}

/* ========== Interactive local terminal ========== */
const termInput = document.getElementById("termInput");
const termHistory = [];
let termHistIdx = -1;
let termCwd = "";

async function refreshTermCwd() {
  try {
    const d = await api("/api/terminal/cwd");
    termCwd = d.cwd || "";
    const p = document.getElementById("termPrompt");
    if (p) p.title = termCwd;
  } catch (_) {}
}
refreshTermCwd();

function appendTerminal(text) {
  const cur = terminal.textContent || "";
  setTerminal((cur.endsWith("\n") || !cur ? cur : cur + "\n") + text);
}

async function runTerminalCommand(cmd) {
  const line = (cmd || "").trim();
  if (!line) return;
  termHistory.push(line);
  termHistIdx = termHistory.length;
  appendTerminal(`$ ${line}`);
  if (termInput) termInput.value = "";
  setStatus("Shell…");
  try {
    const data = await api("/api/terminal/run", {
      method: "POST",
      body: JSON.stringify({ command: line, cwd: termCwd || "" }),
    });
    const out = (data.output || "").replace(/\r\n/g, "\n");
    appendTerminal(out);
    if (data.exit_code !== 0) appendTerminal(`[exit ${data.exit_code}]`);
    // track cd on Windows/unix heuristically
    if (/^(cd|chdir)\s+/i.test(line) && data.ok) {
      await refreshTermCwd();
    }
    setStatus(data.ok ? "Ready" : "Shell error");
  } catch (err) {
    appendTerminal(`✗ terminal offline: ${err.message}\n  Is the backend running?`);
    setStatus("Offline");
  }
}

if (termInput) {
  termInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      runTerminalCommand(termInput.value);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      if (!termHistory.length) return;
      termHistIdx = Math.max(0, termHistIdx - 1);
      termInput.value = termHistory[termHistIdx] || "";
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      termHistIdx = Math.min(termHistory.length, termHistIdx + 1);
      termInput.value = termHistIdx >= termHistory.length ? "" : termHistory[termHistIdx];
    }
  });
}

// Click terminal panel focuses input
document.getElementById("terminalPanel")?.addEventListener("click", () => {
  termInput?.focus();
});

document.getElementById("termClear")?.addEventListener("click", (e) => {
  e.stopPropagation();
  setTerminal("$ ");
});

// Add to command palette if present
if (typeof COMMANDS !== "undefined") {
  COMMANDS.push({
    label: "Focus terminal",
    run: () => termInput?.focus(),
  });
}

/* ========== Live editor tabs ========== */
function renderTabs() {
  const bar = document.getElementById("editorTabs");
  if (!bar) return;
  const addBtn = document.getElementById("tabAdd");
  bar.querySelectorAll(".tab[data-tab-path]").forEach((t) => t.remove());
  if (currentPath && !(currentPath in fileBuffers)) {
    fileBuffers[currentPath] = editor.value;
  }
  // Show open tabs: prefer files already in buffers, current first
  const paths = Object.keys(fileBuffers);
  if (!paths.includes(currentPath) && currentPath) paths.unshift(currentPath);
  const ordered = paths.length ? paths : [currentPath || "untitled.py"];
  ordered.forEach((path) => {
    const tab = document.createElement("div");
    tab.className = "tab" + (path === currentPath ? " active" : "");
    tab.dataset.tabPath = path;
    tab.style.cursor = "pointer";
    const name = (path || "untitled").split("/").pop();
    tab.innerHTML = `${escapeHtml(name)} <span class="tab-close" title="Close">×</span>`;
    tab.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      if (e.target.classList.contains("tab-close")) {
        closeTab(path);
        return;
      }
      switchTab(path);
    });
    if (addBtn) bar.insertBefore(tab, addBtn);
    else bar.appendChild(tab);
  });
}

function switchTab(path) {
  if (!path) return;
  // Always save current buffer first
  fileBuffers[currentPath] = editor.value;
  if (!(path in fileBuffers)) fileBuffers[path] = "";
  currentPath = path;
  editor.value = fileBuffers[path] || "";
  updateLines();
  syncStatus();
  document.querySelectorAll(".file").forEach((f) => {
    f.classList.toggle("active-file", f.dataset.path === path);
  });
  renderTabs();
  setStatus(`Tab: ${path}`);
  if (typeof playRefreshAnimation === "function") playRefreshAnimation(path.split("/").pop());
}

function closeTab(path) {
  const keys = Object.keys(fileBuffers);
  if (keys.length <= 1) {
    toast("Keep at least one tab", "info");
    return;
  }
  delete fileBuffers[path];
  if (currentPath === path) {
    const next = Object.keys(fileBuffers)[0];
    currentPath = next;
    editor.value = fileBuffers[next] || "";
    updateLines();
    syncStatus();
  }
  renderTabs();
  renderFileTree(Object.keys(fileBuffers));
}

function openInTab(path, content) {
  if (content != null) fileBuffers[path] = content;
  else if (!(path in fileBuffers)) fileBuffers[path] = "";
  switchTab(path);
  renderFileTree(Object.keys(fileBuffers));
}

// Hook existing openPath to keep tabs in sync
const _openPath = openPath;
openPath = function (path) {
  fileBuffers[currentPath] = editor.value;
  if (!(path in fileBuffers)) fileBuffers[path] = fileBuffers[path] || "";
  _openPath(path);
  renderTabs();
};

document.getElementById("tabAdd")?.addEventListener("click", () => {
  const name = prompt("New file name", "untitled.py");
  if (!name) return;
  const path = name.includes("/") ? name : name;
  openInTab(path, "");
  toast(`Opened ${path}`, "success");
});

// Initial tabs
renderTabs();



async function refreshQuota(){
  try{
    const data=await api("/api/quota"), el=document.getElementById("quotaDisplay"); if(!el)return;
    let html="";
    if(data.local_lanes?.length) html+=data.local_lanes.map(l=>'<div class="quota-row"><span>'+escapeHtml(l.name)+'</span><span class="quota-inf">∞</span></div>').join("");
    if(data.hf_remaining!=null&&data.hf_limit!=null){const pct=data.hf_percent_remaining??0,cls=pct<20?"quota-warn":"quota-ok";html+='<div class="quota-row"><span>HF quota</span><span class="'+cls+'">'+data.hf_remaining+'/'+data.hf_limit+'</span></div>';if(data.hf_seconds_until_reset)html+='<div class="quota-row muted">Resets in '+Math.round(data.hf_seconds_until_reset)+'s</div>';}
    else html+='<div class="quota-row muted">HF quota: not recorded yet</div>';
    el.innerHTML=html;
  }catch(_){}
}
async function validateAndLoadOllama(){
  const url=document.getElementById("ollamaUrlInput")?.value?.trim();if(!url){toast("Enter a URL","info");return;}
  try{const data=await api("/api/ollama/validate",{method:"POST",body:JSON.stringify({url})});renderOllamaModels(data);toast(data.model_count+" models loaded","success");}catch(err){toast("Validation failed: "+err.message,"error");}
}
function renderOllamaModels(data){
  const box=document.getElementById("ollamaModelList");if(!box)return;box.innerHTML="";const recommended=data.recommended?.name||"";
  (data.models||[]).forEach(m=>{const row=document.createElement("button");row.className="hf-item";row.innerHTML='<span class="hf-id">'+escapeHtml(m.name)+(m.name===recommended?" ★":"")+'</span><span class="hf-meta">'+escapeHtml(m.parameter_size||"?")+" · "+escapeHtml(m.quantization||"?")+" · score "+m.score+'</span>';row.onclick=()=>setPrimaryOllama(data.url,m.name);box.appendChild(row);});
}
async function setPrimaryOllama(url,model){try{await api("/api/ollama/primary",{method:"POST",body:JSON.stringify({url,model})});toast("Primary set: "+model,"success");refreshQuota();}catch(err){toast("Could not set primary","error");}}

/* ========== Vision / image analysis ========== */
let visionDataUrl = "";

function setVisionPreview(dataUrl) {
  visionDataUrl = dataUrl;
  const prev = document.getElementById("visionPreview");
  const img = document.getElementById("visionImg");
  if (img) img.src = dataUrl;
  if (prev) prev.style.display = "block";
}

async function analyzeVision() {
  if (!visionDataUrl) {
    toast("Drop or paste an image first", "info");
    return;
  }
  playRefreshAnimation("Analyzing image…");
  setStatus("Vision…");
  try {
    const data = await api("/api/ai/vision", {
      method: "POST",
      body: JSON.stringify({
        image_base64: visionDataUrl,
        prompt: document.getElementById("visionPrompt")?.value || "",
        model: modelSelect.value,
      }),
    });
    const box = document.getElementById("visionResult");
    let html = escapeHtml(data.content || "").replace(/\n/g, "<br>").replace(/\n/g, "<br>");
    if (data.actions && data.actions.length) {
      html += '<div style="margin-top:8px;font-weight:650">Apply live</div>';
      data.actions.forEach((a, i) => {
        html += '<div class="patch"><div class="patch-head"><span class="patch-title">' + escapeHtml(a.title || "") + '</span></div>' +
          '<div class="muted">' + escapeHtml(a.description || "") + '</div>' +
          '<div class="patch-actions"><button class="apply" data-vision-action="' + i + '">Apply</button></div></div>';
      });
    }
    if (box) {
      box.innerHTML = html;
      box.onclick = (e) => {
        const btn = e.target.closest("[data-vision-action]");
        if (!btn) return;
        const a = data.actions[Number(btn.dataset.visionAction)];
        if (a && typeof applyPatch === "function") applyPatch(a, btn.closest(".patch"));
      };
    }
    appendChat("assistant", data.content || "Vision done");
    setTerminal("$ dreamcoder vision\n\n" + (data.content || ""));
    toast(data.actions && data.actions.length ? data.actions.length + " action(s) ready" : "Image analyzed", "success");
    setStatus("Ready");
  } catch (err) {
    toast("Vision failed – is backend up?", "error");
    setStatus("Offline");
  }
}

const visionDrop = document.getElementById("visionDrop");
const visionFile = document.getElementById("visionFile");
visionDrop?.addEventListener("click", () => visionFile?.click());
visionFile?.addEventListener("change", () => {
  const f = visionFile.files?.[0];
  if (!f) return;
  const reader = new FileReader();
  reader.onload = () => {
    setVisionPreview(reader.result);
    toast("Image loaded – click Analyze", "info");
  };
  reader.readAsDataURL(f);
});
["dragenter", "dragover"].forEach((ev) => {
  visionDrop?.addEventListener(ev, (e) => {
    e.preventDefault();
    visionDrop.classList.add("drag-over");
  });
});
visionDrop?.addEventListener("dragleave", () => visionDrop.classList.remove("drag-over"));
visionDrop?.addEventListener("drop", (e) => {
  e.preventDefault();
  visionDrop.classList.remove("drag-over");
  const f = e.dataTransfer.files?.[0];
  if (!f || !f.type.startsWith("image/")) {
    toast("Drop an image file", "info");
    return;
  }
  const reader = new FileReader();
  reader.onload = () => setVisionPreview(reader.result);
  reader.readAsDataURL(f);
});
document.getElementById("visionAnalyzeBtn")?.addEventListener("click", analyzeVision);
document.getElementById("ollamaValidateBtn")?.addEventListener("click", validateAndLoadOllama);

// Paste image anywhere in app
document.addEventListener("paste", (e) => {
  const items = e.clipboardData?.items;
  if (!items) return;
  for (const it of items) {
    if (it.type.startsWith("image/")) {
      const file = it.getAsFile();
      if (!file) continue;
      const reader = new FileReader();
      reader.onload = () => {
        setVisionPreview(reader.result);
        toast("Image pasted – open Image analysis & Analyze", "success");
        document.getElementById("visionCard")?.scrollIntoView({ behavior: "smooth", block: "nearest" });
      };
      reader.readAsDataURL(file);
      break;
    }
  }
});

if (typeof COMMANDS !== "undefined") {
  COMMANDS.push({ label: "Analyze last image", run: () => analyzeVision() });
  COMMANDS.push({ label: "New editor tab", run: () => document.getElementById("tabAdd")?.click() });
}


/* Final: ensure theme buttons use full THEMES map (overrides early 3-theme handler) */
document.querySelectorAll(".theme[data-theme]").forEach((btn) => {
  btn.onclick = () => {
    if (typeof applyTheme === "function") applyTheme(btn.dataset.theme);
  };
});



/* ========== FINAL BOOT (tabs + themes must work) ========== */
(function finalBoot() {
  function showAiPanel(id) {
    id = id || "panel-chat";
    document.querySelectorAll(".ai-subtab").forEach((b) => {
      b.classList.toggle("active", b.dataset.panel === id);
    });
    document.querySelectorAll("[data-ai-panel]").forEach((el) => {
      if (el.getAttribute("data-ai-panel") === id) {
        el.classList.add("ai-panel-show");
        if (el.style) el.style.display = "";
      } else {
        el.classList.remove("ai-panel-show");
      }
    });
    try { localStorage.setItem("dc_ai_panel", id); } catch (_) {}
  }
  window.showAiPanel = showAiPanel;

  const tabs = document.getElementById("aiSubTabs");
  if (tabs) {
    tabs.onclick = (e) => {
      const btn = e.target.closest(".ai-subtab");
      if (!btn) return;
      showAiPanel(btn.dataset.panel);
    };
  }

  // Themes
  document.querySelectorAll(".theme[data-theme]").forEach((btn) => {
    btn.onclick = () => {
      const name = btn.dataset.theme;
      if (typeof applyTheme === "function") applyTheme(name);
      else {
        document.querySelectorAll(".theme").forEach((x) => x.classList.remove("active-theme"));
        btn.classList.add("active-theme");
      }
    };
  });

  // Start on chat (or saved)
  let start = "panel-chat";
  try { start = localStorage.getItem("dc_ai_panel") || "panel-chat"; } catch (_) {}
  showAiPanel(start);

  // Status
  const st = document.getElementById("status");
  if (st && (!st.textContent || st.textContent === "Ready")) {
    /* keep */
  }
  loadAvailableModels().catch(() => {});
  refreshQuota();
  setInterval(refreshQuota,30000);
  console.log("DreamCoder UI ready");
})();


/* Production control center: GitHub, Git, terminal, recovery and settings. */
(function productionUI(){
  const style=document.createElement("style"); style.textContent=".dc-prod{position:fixed;right:16px;bottom:48px;width:min(620px,94vw);max-height:72vh;overflow:auto;z-index:10000;background:#111722;border:1px solid var(--border);border-radius:12px;box-shadow:0 20px 70px #0008;padding:12px}.dc-tabs{display:flex;gap:5px;flex-wrap:wrap;margin-bottom:10px}.dc-tabs button,.dc-prod button{border:1px solid var(--border);background:#0d1118;color:var(--text);border-radius:6px;padding:6px 9px;cursor:pointer}.dc-tabs button.active{border-color:var(--accent)}.dc-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px}.dc-grid input,.dc-prod select{width:100%;box-sizing:border-box;background:#0b1018;color:var(--text);border:1px solid var(--border);padding:7px;border-radius:6px}.dc-row{display:flex;gap:6px;margin:6px 0;flex-wrap:wrap}.dc-log{background:#080b10;padding:8px;border-radius:7px;white-space:pre-wrap;font:10px ui-monospace;max-height:220px;overflow:auto}.dc-ok{color:var(--accent2)}.dc-err{color:var(--danger)}";document.head.appendChild(style);
  const b=document.createElement("button");b.className="chip";b.textContent="⚙ Production";b.style.position="fixed";b.style.right="12px";b.style.bottom="12px";b.style.zIndex="9999";document.body.appendChild(b);
  const box=document.createElement("div");box.className="dc-prod";box.hidden=true;document.body.appendChild(box);
  const tabs=["GitHub","Git","Terminal","Settings","Recovery","Diagnostics"];
  function shell(tab){
    box.innerHTML='<div class="dc-tabs">'+tabs.map(x=>'<button data-tab="'+x+'">'+x+'</button>').join("")+'<button data-close>×</button></div><div id="dc-body"></div>';
    box.querySelectorAll("[data-tab]").forEach(x=>x.onclick=()=>render(x.dataset.tab));
    box.querySelector("[data-close]").onclick=()=>box.hidden=true; render(tab);
  }
  async function post(path,body){return api(path,{method:"POST",body:JSON.stringify(body||{})})}
  async function render(tab){
    const body=box.querySelector("#dc-body"); body.innerHTML="<div class=muted>Loading…</div>";
    if(tab==="GitHub"){
      const me=await api("/api/github/me").catch(()=>({connected:false})); const cfg=await api("/api/github/oauth/config").catch(()=>({configured:false}));
      const repos=me.connected?await api("/api/github/repositories").catch(()=>({repositories:[]})):{repositories:[]};
      body.innerHTML='<h3>GitHub connection</h3><div class="muted">'+(me.connected?"Connected as "+escapeHtml(me.login):"Not connected")+'</div><div class=dc-row>'+(me.connected?'<button id=dcDisconnect>Disconnect</button>':'<button id=dcConnect>Connect GitHub</button>')+'</div><div class=dc-grid><select id=dcRepo>'+repos.repositories.map(x=>'<option value="'+escapeHtml(x.full_name)+'">'+escapeHtml(x.full_name)+'</option>').join("")+'</select><input id=dcBranch placeholder="branch (main)"/></div><div class=dc-row><button id=dcRepoSet>Use repository</button><button id=dcRefreshRepos>Refresh repositories</button></div><div id=dcGhLog class=dc-log></div>';
      body.querySelector("#dcConnect")?.addEventListener("click",()=>{ if(!cfg.configured){toast("Set DREAMCODER_GITHUB_CLIENT_ID/SECRET and OAUTH_STATE_SECRET first","error");return;} window.open(API_BASE+"/api/github/oauth/start","_blank","width=900,height=800"); setTimeout(()=>render("GitHub"),3000);});
      body.querySelector("#dcDisconnect")?.addEventListener("click",async()=>{await post("/api/github/disconnect");render("GitHub")});
      body.querySelector("#dcRepoSet")?.addEventListener("click",async()=>{const d=await post("/api/github/select-repository",{repo:body.querySelector("#dcRepo").value,branch:body.querySelector("#dcBranch").value||"main"});body.querySelector("#dcGhLog").textContent=JSON.stringify(d,null,2);refreshGithubSyncStatus()});
      body.querySelector("#dcRefreshRepos")?.addEventListener("click",()=>render("GitHub"));
      return;
    }
    if(tab==="Git"){
      const s=await api("/api/git/workflow/status").catch(e=>({error:String(e)})); const br=await api("/api/git/workflow/branches").catch(e=>({error:String(e)}));
      const files=await api("/api/git/workflow/files").catch(()=>({files:[]})); body.innerHTML='<h3>Git workflow</h3><div class=dc-row><button data-git=fetch>Fetch</button><button data-git=pull>Pull</button><button data-git=push>Push</button><button data-git=stash>Stash</button><button data-git=merge>Merge</button></div><div class=dc-grid><input id=dcBranchName placeholder="new/switch branch"/><button data-git=branch>Create & switch branch</button><input id=dcCommit placeholder="commit message"/><button data-git=commit>Commit staged</button></div><div class=dc-log id=dcGitFiles>'+((files.files||[]).map(f=>'<div><button data-stage="'+escapeHtml(f.path)+'">'+(f.index!==" "?"Unstage":"Stage")+'</button> <code>'+escapeHtml(f.path)+'</code></div>').join("")||"Working tree clean")+'</div><pre class=dc-log>'+escapeHtml(JSON.stringify({status:s,branches:br},null,2))+'</pre>';      body.querySelectorAll("[data-stage]").forEach(x=>x.onclick=async()=>{const path=x.dataset.stage;const f=(files.files||[]).find(z=>z.path===path);const d=await post("/api/git/workflow/"+(f&&f.index!==" "?"unstage":"stage"),{paths:[path]});toast(d.ok?"Git index updated":"Git operation failed",d.ok?"success":"error");render("Git");});\n").length || 1;
  lineNumbers.textContent = Array.from({ length: count }, (_, i) => i + 1).join("\n");
}

function syncStatus() {
  const before = editor.value.slice(0, editor.selectionStart);
  const lines = before.split("\n");
  const col = (lines.at(-1) || "").length + 1;
  document.querySelector(".statusbar span").textContent = `Ln ${lines.length}, Col ${col}`;
}

function setStatus(text) { statusEl.textContent = text; }

async function refreshModelHealth() {
  const selected = modelSelect?.value;
  const badge = document.getElementById("modelStatus");
  if (!selected) return;
  if (badge) {
    badge.textContent = "checking";
    badge.dataset.status = "checking";
  }
  try {
    const data = await api("/api/health?model=" + encodeURIComponent(selected));
    const m = data.model || {};
    const status = m.status || "unknown";
    const backend = m.backend || (selected === "mock" ? "mock" : "");
    const label = status === "ready" ? "online" : status.replace(/-/g, " ");
    if (badge) {
      badge.textContent = label + (backend ? " · " + backend : "");
      badge.dataset.status = status;
      badge.title = JSON.stringify(m);
    }
    if (modelCurrent) modelCurrent.textContent = selected;
  } catch (err) {
    if (badge) {
      badge.textContent = "unavailable";
      badge.dataset.status = "error";
      badge.title = err.message;
    }
  }
}

async function loadAvailableModels() {
  if (!modelSelect) return;
  try {
    const data = await api("/api/models");
    const models = Array.isArray(data.models) ? data.models : [];
    const previous = localStorage.getItem("dc_model");
    modelSelect.innerHTML = "";
    const groups = new Map();
    for (const model of models) {
      const provider = model.provider || "other";
      if (!groups.has(provider)) {
        const group = document.createElement("optgroup");
        group.label = provider === "mock" ? "Offline / development" : provider;
        groups.set(provider, group);
        modelSelect.appendChild(group);
      }
      const option = document.createElement("option");
      option.value = model.id;
      option.textContent = model.name + (model.real ? "" : " (mock)");
      option.dataset.status = model.status || "unknown";
      option.dataset.real = model.real ? "true" : "false";
      groups.get(provider).appendChild(option);
    }
    if (!models.length) {
      const option = document.createElement("option");
      option.value = "mock";
      option.textContent = "Mock / offline";
      modelSelect.appendChild(option);
    }
    const validPrevious = [...modelSelect.options].some((o) => o.value === previous);
    const firstReal = [...modelSelect.options].find((o) => o.dataset.real === "true");
    modelSelect.value = validPrevious ? previous : (firstReal?.value || "mock");
    modelCurrent.textContent = modelSelect.value;
    localStorage.setItem("dc_model", modelSelect.value);
    await refreshModelHealth();
  } catch (err) {
    // Never leave pretend model names selected when discovery is unavailable.
    modelSelect.innerHTML = '<option value="mock">Mock / offline</option>';
    modelSelect.value = "mock";
    modelCurrent.textContent = "mock";
    localStorage.setItem("dc_model", "mock");
    await refreshModelHealth();
    toast("Model discovery unavailable — using explicit Mock / offline mode", "info", 4500);
  }
}

function setTerminal(text) {
  terminal.textContent = text;
  terminal.scrollTop = terminal.scrollHeight;
}

async function api(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`${res.status}: ${err}`);
  }
  return res.json();
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function toast(msg, type = "info", ms = 3200) {
  const root = document.getElementById("toasts");
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.innerHTML = `<span class="toast-msg">${escapeHtml(msg)}</span><span class="toast-close">×</span>`;
  el.querySelector(".toast-close").onclick = () => { if (el && el.remove) el.remove(); };
  root.appendChild(el);
  setTimeout(() => el.remove(), ms);
}

function showModal({ title, bodyHtml, onApply, applyLabel = "Apply" }) {
  const root = document.getElementById("modalRoot");
  root.innerHTML = `
    <div class="modal-backdrop">
      <div class="modal">
        <div class="modal-head">
          <h3>${escapeHtml(title)}</h3>
          <button class="btn" id="modalClose">✕</button>
        </div>
        <div class="modal-body">${bodyHtml}</div>
        <div class="modal-foot">
          <button class="btn" id="modalCancel">Cancel</button>
          <button class="btn primary" id="modalApply">${escapeHtml(applyLabel)}</button>
        </div>
      </div>
    </div>`;
  const close = () => (root.innerHTML = "");
  root.querySelector("#modalClose").onclick = close;
  root.querySelector("#modalCancel").onclick = close;
  root.querySelector(".modal-backdrop").addEventListener("click", (e) => {
    if (e.target.classList.contains("modal-backdrop")) close();
  });
  root.querySelector("#modalApply").onclick = () => { onApply?.(); close(); };
}

let githubSaveTimer = null;
let githubSyncPromise = Promise.resolve();
let githubSyncConfigured = false;

function setGithubSyncState(label, state = "") {
  const el = document.getElementById("githubSyncState");
  if (!el) return;
  el.textContent = "GitHub: " + label;
  el.dataset.state = state;
}

async function refreshWorkspaceGitStatus() {
  const el = document.getElementById("workspaceGitState");
  if (!el) return;
  try {
    const data = await api("/api/workspace");
    if (!data.configured) {
      el.textContent = "Git: no workspace";
      return;
    }
    const branch = data.branch || "detached";
    const lines = (data.status?.stdout || "").split("\n").filter(Boolean);
    const dirty = lines.filter(x => !x.startsWith("##")).length;
    el.textContent = `Git: ${branch}${dirty ? " · " + dirty + " changed" : " · clean"}`;
    el.dataset.state = dirty ? "dirty" : "clean";
  } catch (_) {
    el.textContent = "Git: offline";
    el.dataset.state = "error";
  }
}

async function refreshGithubSyncStatus() {
  try {
    const data = await api("/api/github/status");
    githubSyncConfigured = Boolean(data.configured);
    if (data.configured) setGithubSyncState(data.repo + " · " + data.branch, "ready");
    else setGithubSyncState("not configured", "off");
  } catch (_) {
    githubSyncConfigured = false;
    setGithubSyncState("backend offline", "error");
  }
}

async function saveCurrentFileLive() {
  if (!currentPath) return;
  const content = editor.value;
  fileBuffers[currentPath] = content;
  setGithubSyncState(githubSyncConfigured ? "syncing…" : "local only", githubSyncConfigured ? "syncing" : "off");
  try {
    const data = await api("/api/files/save", {
      method: "POST",
      body: JSON.stringify({
        path: currentPath,
        content,
        language: langFromPath(currentPath),
        sync_github: true,
        commit_message: "DreamCoder live edit: " + currentPath,
      }),
    });
    const gh = data.github || {};
    if (gh.ok) {
      setGithubSyncState("synced ✓", "ready");
      setStatus("Saved · GitHub synced");
    } else if (gh.skipped) {
      setGithubSyncState("local only", "off");
      setStatus("Saved locally");
    } else {
      setGithubSyncState("sync error", "error");
      setStatus("Saved · GitHub sync failed");
      showSyncBanner("Local save succeeded, but GitHub sync failed", "error", gh.backup?.path || "");
      toast("Local save succeeded, but GitHub sync failed", "error");
    }
  } catch (err) {
    setGithubSyncState("sync error", "error");
    setStatus("Local edit pending");
    showSyncBanner("Local save request failed; your editor contents are still open.", "error");
  }
}

function scheduleLiveSave() {
  clearTimeout(githubSaveTimer);
  githubSaveTimer = setTimeout(() => {
    githubSyncPromise = githubSyncPromise.catch(() => {}).then(saveCurrentFileLive);
  }, 900);
}

editor.addEventListener("input", () => {
  updateLines();
  syncStatus();
  setStatus("Modified · syncing…");
  scheduleLiveSave();
});
editor.addEventListener("click", syncStatus);
editor.addEventListener("keyup", syncStatus);
updateLines();

document.getElementById("termClear").onclick = () => setTerminal("$ ");

async function runCode() {
  const btn = document.getElementById("runBtn");
  btn.disabled = true;
  setStatus("Running…");
  setTerminal("$ dreamcoder run\n\nConnecting to backend…");
  try {
    const data = await api("/api/run", {
      method: "POST",
      body: JSON.stringify({ code: editor.value, language: "python", filename: "main.py" }),
    });
    setTerminal(data.output);
    setStatus(data.exit_code === 0 ? "Ready" : "Error");
    toast(data.exit_code === 0 ? "Run finished" : "Syntax error", data.exit_code === 0 ? "success" : "error");
  } catch (err) {
    setTerminal(`$ dreamcoder run\n\n✗ Backend unreachable\n  ${err.message}\n\nStart backend:\n  cd backend && python -m uvicorn main:app --reload --port 8000`);
    setStatus("Offline");
    toast("Backend offline", "error");
  } finally {
    btn.disabled = false;
  }
}
document.getElementById("runBtn").onclick = runCode;
document.getElementById("agentBtn")?.addEventListener("click", runProjectAgent);
async function syncProjectToGithub() {
  const btn = document.getElementById("githubSyncBtn");
  if (btn) btn.disabled = true;
  setGithubSyncState("syncing…", "syncing");
  try {
    const data = await api("/api/github/sync", { method: "POST" });
    const failed = (data.results || []).filter(r => !r.ok && !r.skipped);
    if (failed.length) throw new Error(failed[0].error || "GitHub rejected a file");
    if ((data.results || []).some(r => r.ok)) {
      setGithubSyncState("synced ✓", "ready");
      toast("Project synced to GitHub", "success");
    } else {
      setGithubSyncState("local only", "off");
      toast("GitHub autosync is not configured", "info");
    }
  } catch (err) {
    setGithubSyncState("sync error", "error");
    toast("GitHub sync failed: " + err.message, "error");
  } finally {
    if (btn) btn.disabled = false;
  }
}
document.getElementById("githubSyncBtn")?.addEventListener("click", syncProjectToGithub);

async function runProjectAgent() {
  const goal = prompt("What should DreamCoder change in this project?", document.getElementById("projectGoal")?.value || "");
  if (!goal?.trim()) return;
  const model = modelSelect.value;
  setStatus("Agent planning…");
  setTerminal("$ dreamcoder agent\n\nPlanning with " + model + "…");
  try {
    const data = await api("/api/agent/run", {
      method: "POST",
      body: JSON.stringify({ goal: goal.trim(), cwd: "", model, auto_apply: false }),
    });
    renderAgentRun(data);
  } catch (err) {
    setStatus("Agent error");
    toast("Agent failed: " + err.message, "error");
  }
}

function renderAgentRun(data) {
  const steps = (data.plan || []).map((s, i) => `${i + 1}. ${escapeHtml(s.title)}`).join("<br>");
  const changes = (data.changes || []).filter(c => c && c.path).map(c => `<div class="agent-change"><strong><span class="change-type" data-type="${escapeHtml(c.change_type || "PROJECT_MODIFY")}">${escapeHtml(c.change_type || "PROJECT_MODIFY")}</span>${escapeHtml(c.path)}</strong><span>${escapeHtml(c.summary || "proposed change")}</span>${c.diff ? '<pre class="analysis-diff">' + escapeHtml(c.diff) + '</pre>' : ''}</div>`).join("");
  const body = `
    <div class="muted">Model: ${escapeHtml(data.model || modelSelect.value)} · Status: ${escapeHtml(data.status || "unknown")}</div>
    <div class="analysis-section">Plan</div><div class="analysis-model-note">${steps || "No plan returned."}</div>
    ${changes ? '<div class="analysis-section">Proposed changes</div>' + changes : ""}
    ${data.validation?.stderr ? '<div class="analysis-section">Validation</div><pre class="analysis-diff">' + escapeHtml(data.validation.stderr) + '</pre>' : ""}
  `;
  if (data.sync_warnings?.length) {
    const w=data.sync_warnings[0];
    showSyncBanner("GitHub sync failed for "+(w.path||"a changed file"),"error",w.backup_path||"");
  }
  const needsChangesApproval = data.status === "awaiting_approval" && changes;
  showModal({
    title: needsChangesApproval ? "Review model changes" : "Project agent plan",
    bodyHtml: body,
    applyLabel: needsChangesApproval ? "Apply changes" : "Generate changes",
    onApply: async () => {
      try {
        const next = await api("/api/agent/runs/" + encodeURIComponent(data.id) + "/approve", {
          method: "POST",
          body: JSON.stringify({ auto_apply: Boolean(needsChangesApproval) }),
        });
        renderAgentRun(next);
        if (next.status === "completed") {
          setStatus("Ready");
          setTerminal("$ dreamcoder agent\n\n✓ Agent completed and tests passed.\n" + ((next.validation && next.validation.stdout) || ""));
          toast("Agent completed", "success");
        } else {
          setStatus("Agent: " + next.status);
        }
      } catch (err) {
        toast("Agent approval failed: " + err.message, "error");
      }
    },
  });
}


async function getSuggestions() {
  const btn = document.getElementById("suggestBtn");
  btn.disabled = true;
  setStatus("Analyzing…");
  setTerminal("$ dreamcoder ai suggest\n\nSending context to model…");
  try {
    const data = await api("/api/ai/suggest", {
      method: "POST",
      body: JSON.stringify({
        model: modelSelect.value,
        language: "python",
        code: editor.value,
        selection: editor.value.substring(editor.selectionStart, editor.selectionEnd),
        filename: "main.py",
        use_cache: true,
      }),
    });
    renderSuggestions(data.suggestions);
    renderInsights(data.architecture_insights || []);
    renderHealth(data.health || {}, data.latency_ms, data.cached);
    setTerminal(`$ dreamcoder ai suggest\n\nModel: ${data.model}${data.cached ? " (cached)" : ""}\n→ ${data.suggestions.length} suggestions\n→ ${(data.architecture_insights || []).length} insights\nDone in ${data.latency_ms}ms`);
    setStatus("Ready");
    toast(`${data.suggestions.length} suggestions · ${data.latency_ms}ms`, "success");
  } catch (err) {
    setTerminal(`$ dreamcoder ai suggest\n\n✗ ${err.message}`);
    setStatus("Offline");
    toast("Suggest failed – backend offline?", "error");
  } finally {
    btn.disabled = false;
  }
}
document.getElementById("suggestBtn").onclick = getSuggestions;

modelSelect.onchange = async () => {
  modelCurrent.textContent = modelSelect.value;
  localStorage.setItem("dc_model", modelSelect.value);
  setStatus(`Model: ${modelSelect.value}`);
  await refreshModelHealth();
  toast(`Model → ${modelSelect.value}`, "info");
};

function renderSuggestions(suggestions) {
  const card = document.getElementById("suggestionsCard");
  card.querySelector(".card-head").innerHTML = `<span>Code Suggestions</span><span>${suggestions.length}</span>`;
  card.querySelectorAll(".suggestion, #sugEmpty").forEach((el) => el.remove());
  if (!suggestions.length) {
    const empty = document.createElement("div");
    empty.id = "sugEmpty";
    empty.className = "muted";
    empty.textContent = "No suggestions yet";
    card.appendChild(empty);
    return;
  }
  suggestions.forEach((s, i) => {
    const row = document.createElement("div");
    row.className = "suggestion";
    row.innerHTML = `
      <b>${String(i + 1).padStart(2, "0")}</b>
      <span style="flex:1">
        <strong>${escapeHtml(s.title)}</strong>
        <small>${escapeHtml(s.description)}</small>
        <div class="actions">
          <button class="apply">Apply</button>
          <button class="preview">Preview</button>
        </div>
      </span>`;
    row.querySelector(".apply").onclick = (e) => {
      e.stopPropagation();
      insertSuggestion(s.code);
      toast("Suggestion applied", "success");
    };
    row.querySelector(".preview").onclick = (e) => {
      e.stopPropagation();
      showModal({
        title: s.title,
        bodyHtml: `<p class="muted" style="margin:0 0 10px">${escapeHtml(s.description)}</p><pre>${escapeHtml(s.code)}</pre>`,
        applyLabel: "Insert into editor",
        onApply: () => { insertSuggestion(s.code); toast("Suggestion applied", "success"); },
      });
    };
    card.appendChild(row);
  });
}

function renderInsights(insights) {
  const card = document.getElementById("insightsCard");
  card.querySelector(".card-head").innerHTML = `<span>App Structure</span><span>${insights.length}</span>`;
  card.querySelectorAll(".insight").forEach((el) => el.remove());
  insights.forEach((ins) => {
    const div = document.createElement("div");
    div.className = "insight";
    div.innerHTML = `<span class="icon">${ins.icon || "•"}</span><div><strong>${escapeHtml(ins.title)}</strong><small>${escapeHtml(ins.detail || "")}</small></div>`;
    card.appendChild(div);
  });
}

function renderHealth(health, latency, cached) {
  const score = health.score ?? 87;
  document.getElementById("healthScore").textContent = `${score}%`;
  document.getElementById("healthBar").style.width = `${score}%`;
  document.getElementById("healthGrid").innerHTML = `
    <span>✓ ${health.files_indexed ?? "—"} files</span>
    <span>✓ ${health.symbols ?? "—"} symbols</span>
    <span>⚡ ${latency ?? health.ai_latency_ms ?? "—"}ms</span>
    <span>${cached ? "📦 cached" : "● live"}</span>`;
}

function insertSuggestion(snippet) {
  const start = editor.selectionStart, end = editor.selectionEnd;
  editor.setRangeText("\n# AI suggestion\n" + snippet + "\n", start, end, "end");
  updateLines(); syncStatus(); setStatus("Suggestion inserted");
}

/* ---- Evolve: live self-update ---- */

function renderPatches(patches) {
  patchList.innerHTML = "";
  if (!patches?.length) return;
  patches.forEach((p) => {
    const el = document.createElement("div");
    el.className = "patch";
    el.innerHTML = `
      <div class="patch-head">
        <span class="patch-title">${escapeHtml(p.title)}</span>
        <span class="patch-meta">${escapeHtml(p.target || "ui")}</span>
      </div>
      <div class="muted">${escapeHtml(p.description || "")}</div>
      <pre>${escapeHtml((p.code || "").slice(0, 600))}${(p.code || "").length > 600 ? "…" : ""}</pre>
      <div class="patch-actions">
        <button class="apply">Apply live</button>
        <button class="dismiss">Dismiss</button>
      </div>`;
    el.querySelector(".apply").onclick = () => applyPatch(p, el);
    el.querySelector(".dismiss").onclick = () => { if (el && el.remove) el.remove(); };
    patchList.appendChild(el);
  });
}

function applyPatch(patch, el) {
  if (!patch) return;
  if (patch.diff && !patch._confirmed) {
    showModal({
      title:"Review change: "+(patch.title||"patch"),
      bodyHtml:'<p class="muted">'+escapeHtml(patch.description||"")+'</p><div class="diff-toggle"><button class="btn diff-mode active" data-mode="unified">Unified</button><button class="btn diff-mode" data-mode="split">Side-by-side</button></div><pre class="diff-unified">'+escapeHtml(patch.diff)+'</pre><div class="diff-split" hidden>'+renderSplitDiff(patch.diff)+'</div>',
      applyLabel:"Apply",
      onApply:()=>applyPatch({...patch,_confirmed:true},el)
    });
    const root=document.getElementById("modalRoot");
    root?.querySelectorAll(".diff-mode").forEach(btn=>btn.onclick=()=>{
      root.querySelectorAll(".diff-mode").forEach(b=>b.classList.toggle("active",b===btn));
      const split=btn.dataset.mode==="split"; root.querySelector(".diff-unified").hidden=split; root.querySelector(".diff-split").hidden=!split;
    });
    return;
  }
  return applyPatchUnsafe(patch,el);
}
function renderSplitDiff(unified) {
  const lines=(unified||"").split("\n"),left=[],right=[];
  for(const line of lines){
    if(line.startsWith("-")&&!line.startsWith("---"))left.push(line);
    else if(line.startsWith("+")&&!line.startsWith("+++"))right.push(line);
    else{left.push(line);right.push(line);}
  }
  return '<div class="diff-cols"><pre class="diff-col">'+escapeHtml(left.join("\n"))+'</pre><pre class="diff-col">'+escapeHtml(right.join("\n"))+'</pre></div>';
}

function applyPatchUnsafe(patch, el) {
  if (!patch) return;
  const target = (patch.target || "css").toLowerCase();
  const code = patch.code || "";
  try {
    if (target === "css" || target === "style") {
      const style = document.createElement("style");
      style.textContent = code;
      document.head.appendChild(style);
      toast(`Applied CSS: ${patch.title}`, "success");
    } else if (target === "js" || target === "script") {
      const fn = new Function(code);
      fn();
      toast(`Applied JS: ${patch.title}`, "success");
    } else if (target === "html") {
      const slot = document.querySelector(".ai-panel");
      const wrap = document.createElement("div");
      wrap.className = "card";
      wrap.innerHTML = code;
      slot.insertBefore(wrap, slot.children[1] || null);
      toast(`Injected UI: ${patch.title}`, "success");
    } else {
      showModal({
        title: patch.title,
        bodyHtml: `<pre>${escapeHtml(code)}</pre>`,
        applyLabel: "Copy",
        onApply: () => { navigator.clipboard?.writeText(code); toast("Copied", "info"); },
      });
      return;
    }
    if (el && el.remove) if (el && el.remove) el.remove();
    setTerminal((terminal.textContent || "") + `\n\n$ evolve apply\n✓ Live patch: ${patch.title}`);
  } catch (err) {
    toast(`Patch failed: ${err.message}`, "error");
  }
}

function localEvolveFallback(prompt) {
  const p = prompt.toLowerCase();
  const patches = [];
  if (p.includes("shortcut") || p.includes("help") || p.includes("overlay")) {
    patches.push({
      id: "demo-help", title: "Keyboard shortcut overlay",
      description: "Floating help panel for Ctrl shortcuts",
      target: "html",
      code: `<div class="card-head"><span>⌨ Shortcuts</span><span class="badge">LIVE</span></div>
<div class="muted" style="line-height:1.7">
  <div><span class="kbd">Ctrl</span>+<span class="kbd">Enter</span> Run</div>
  <div><span class="kbd">Ctrl</span>+<span class="kbd">Shift</span>+<span class="kbd">S</span> Suggest</div>
  <div><span class="kbd">Ctrl</span>+<span class="kbd">E</span> Evolve</div>
</div>`,
    });
  }
  if (p.includes("terminal") || p.includes("font")) {
    patches.push({
      id: "demo-term", title: "Larger terminal",
      description: "Taller terminal + better contrast",
      target: "css",
      code: `.terminal{height:180px !important}
.terminal pre{font-size:12.5px !important;color:#c5d4e8 !important}`,
    });
  }
  if (p.includes("theme") || p.includes("transition") || p.includes("polish")) {
    patches.push({
      id: "demo-theme", title: "Smoother theme transitions",
      description: "Animate colors on theme switch",
      target: "css",
      code: `body,.app-shell,.files,.ai-panel,.editor-area,.topbar,.card{
  transition: background-color .35s ease, border-color .35s ease, color .25s ease;
}`,
    });
  }
  if (p.includes("file") || p.includes("tree") || p.includes("icon")) {
    patches.push({
      id: "demo-tree", title: "File tree accent",
      description: "Accent border on hover / active file",
      target: "css",
      code: `.file:hover{border-left:2px solid var(--accent);padding-left:10px}
.file.active-file{border-left:2px solid var(--accent2);padding-left:10px}`,
    });
  }
  if (p.includes("minimap") || p.includes("overview")) {
    patches.push({
      id: "demo-minimap", title: "Editor side accent bar",
      description: "Visual stand-in for a minimap",
      target: "css",
      code: `.editor-wrap{position:relative}
.editor-wrap::after{
  content:"";position:absolute;top:8px;right:6px;width:28px;height:calc(100% - 16px);
  background:linear-gradient(180deg,#7c8cff22,#4de0b811);border-radius:4px;
  border:1px solid #7c8cff22;pointer-events:none;
}`,
    });
  }
  if (/(more\s*theme|more\s*color|more\s*colour|add\s*theme|theme)/i.test(text)) {
    patches.push({
      id: "more-themes-local",
      title: "Add extra themes",
      description: "Peach, Shroom, Ocean, Ember buttons",
      target: "js",
      code: "['peach','shroom','ocean','ember','rose','mint','sand'].forEach(function(n){var row=document.querySelector('.theme-row');if(!row)return;if(document.querySelector('[data-theme=\''+n+'\']'))return;var b=document.createElement('button');b.className='theme';b.setAttribute('data-theme',n);b.textContent=n.charAt(0).toUpperCase()+n.slice(1);b.onclick=function(){if(typeof applyTheme==='function')applyTheme(n);};row.appendChild(b);});if(typeof toast==='function')toast('Themes expanded','success');",
    });
  }
  if (/(particle)/i.test(text)) {
    patches.push({
      id: "particles-fix",
      title: "Force-enable visible particles",
      description: "Rebuild particle layer",
      target: "js",
      code: "if(typeof setParticles==='function'){setParticles(false);setTimeout(function(){setParticles(true);},50);}",
    });
  }
  if (/(remove|hide).*(theme|these)/i.test(text)) {
    patches.push({
      id: "hide-themes-local",
      title: "Hide theme buttons",
      description: "Hide the theme row",
      target: "css",
      code: ".theme-row{display:none!important}",
    });
  }
  if (!patches.length) {
    patches.push({
      id: "demo-generic", title: "Evolve button pulse",
      description: "Subtle live pulse on Evolve control",
      target: "css",
      code: `.btn.evolve{animation:evolvePulse 2.2s infinite}
@keyframes evolvePulse{0%,100%{box-shadow:0 0 0 0 #4de0b833}50%{box-shadow:0 0 0 6px #4de0b800}}`,
    });
  }
  return { patches, model: "local-demo", latency_ms: 40 };
}

async function evolveApp(prompt) {
  const text = (prompt || evolveInput.value || "").trim();
  if (!text) { toast("Describe what to add or change", "info"); return; }
  const btn = document.getElementById("evolveSend");
  if (btn) btn.disabled = true;
  setStatus("Evolving…");
  setTerminal(`$ dreamcoder evolve\n\n"${text}"\n\nApplying UI changes…`);

  const applyAll = (patches) => {
    renderPatches(patches || []);
    (patches || []).forEach((p) => {
      try { applyPatch(p, null); } catch (e) { console.warn("patch", e); }
    });
  };

  try {
    const data = await api("/api/ai/evolve", {
      method: "POST",
      body: JSON.stringify({
        model: modelSelect.value,
        prompt: text,
        current_ui: {
          themes: ["midnight", "graphite", "violet", "peach", "shroom", "ocean", "ember"],
          panels: ["explorer", "editor", "terminal", "ai-assistant", "evolve"],
          features: ["run", "suggest", "evolve", "model-select", "health"],
        },
      }),
    });
    const patches = data.patches || [];
    applyAll(patches);
    setTerminal(`$ dreamcoder evolve\n\n"${text}"\n\nModel: ${data.model}\n→ Applied ${patches.length} change(s) in ${data.latency_ms}ms`);
    setStatus("Ready");
    toast(patches.length ? `Applied ${patches.length} change(s)` : "No matching patches", "success");
    evolveInput.value = "";
  } catch (err) {
    const demo = localEvolveFallback(text);
    applyAll(demo.patches);
    setTerminal(`$ dreamcoder evolve\n\n"${text}"\n\nLocal apply (backend offline)\n→ ${demo.patches.length} change(s)`);
    setStatus("Offline");
    toast(`Applied ${demo.patches.length} local change(s)`, "success");
  } finally {
    if (btn) btn.disabled = false;
  }
}


document.getElementById("evolveSend").onclick = () => evolveApp();
document.getElementById("evolveBtn").onclick = () => {
  evolveInput.focus();
  if (evolveInput.value.trim()) evolveApp();
  else toast("Type a change, or click a chip", "info");
};
document.getElementById("evolveChips").onclick = (e) => {
  const chip = e.target.closest(".chip");
  if (!chip) return;
  evolveInput.value = chip.dataset.prompt || chip.textContent;
  evolveApp(chip.dataset.prompt);
};
evolveInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); evolveApp(); }
});

document.querySelectorAll(".theme").forEach((btn) => {
  btn.onclick = () => {
    document.querySelectorAll(".theme").forEach((x) => x.classList.remove("active-theme"));
    btn.classList.add("active-theme");
    const t = btn.dataset.theme;
    if (t === "graphite") {
      document.documentElement.style.setProperty("--bg", "#101214");
      document.documentElement.style.setProperty("--panel", "#17191c");
      document.documentElement.style.setProperty("--accent", "#7c8cff");
    } else if (t === "violet") {
      document.documentElement.style.setProperty("--accent", "#b48cff");
      document.documentElement.style.setProperty("--bg", "#0e0b14");
      document.documentElement.style.setProperty("--panel", "#11151e");
    } else {
      document.documentElement.style.setProperty("--bg", "#0b0e14");
      document.documentElement.style.setProperty("--panel", "#11151e");
      document.documentElement.style.setProperty("--accent", "#7c8cff");
    }
    toast(`Theme: ${t}`, "info", 1500);
  };
});

document.addEventListener("keydown", (e) => {
  if (e.ctrlKey && e.key === "Enter") { e.preventDefault(); runCode(); }
  if (e.ctrlKey && e.shiftKey && (e.key === "S" || e.key === "s")) { e.preventDefault(); getSuggestions(); }
  if (e.ctrlKey && (e.key === "e" || e.key === "E")) { e.preventDefault(); evolveInput.focus(); }
});

(async () => {
  try {
    await api("/api/health");
    setStatus("Backend online");
    document.getElementById("liveDot").textContent = "LIVE";
    toast("Backend connected", "success", 2000);
  } catch {
    setStatus("Backend offline");
    document.getElementById("liveDot").textContent = "OFFLINE";
    document.getElementById("liveDot").style.color = "#ff6b7a";
    toast("Backend offline – Evolve still works with demo patches", "info", 4000);
  }
})();

/* ========== Multi-file buffer ========== */
const fileBuffers = {
  "src/main.py": editor.value,
  "src/ai_router.py": "class AIRouter:\n    def get_model(self, name: str):\n        ...\n",
  "src/suggestions.py": "# suggestions helpers\n",
  "src/cache.py": "# cache layer\n",
};
let currentPath = "src/main.py";

document.querySelectorAll(".file[data-path]").forEach((btn) => {
  btn.addEventListener("click", () => {
    const path = btn.dataset.path;
    if (!path) return;
    if (!(path in fileBuffers)) fileBuffers[path] = fileBuffers[path] || "";
    openPath(path);
  });
});

/* ========== Ask All models ========== */
async function askAllModels() {
  const btn = document.getElementById("askAllBtn");
  if (btn) btn.disabled = true;
  setStatus("Asking all models…");
  setTerminal("$ dreamcoder ask-all\n\nFiring parallel requests…");
  try {
    const catalog = await api("/api/models");
    const discovered = (catalog.models || []).filter(m => m.real).map(m => m.id).slice(0, 5);
    const models = discovered.length ? discovered : ["mock"];
    const data = await api("/api/ai/suggest-all", {
      method: "POST",
      body: JSON.stringify({
        models,
        code: editor.value,
        language: "python",
        filename: currentPath,
      }),
    });
    let out = `$ dreamcoder ask-all\n\nTotal ${data.total_latency_ms}ms\n\n`;
    const allSug = [];
    (data.results || []).forEach((r) => {
      out += `── ${r.model} ${r.ok ? "✓" : "✗"} (${r.latency_ms || "—"}ms)${r.cached ? " cached" : ""}\n`;
      (r.suggestions || []).forEach((s) => {
        out += `  • ${s.title}\n`;
        allSug.push({ ...s, title: `[${r.model}] ${s.title}` });
      });
      out += "\n";
    });
    setTerminal(out);
    renderSuggestions(allSug.slice(0, 12));
    setStatus("Ready");
    toast(`All models responded · ${data.total_latency_ms}ms`, "success");
  } catch (err) {
    setTerminal(`$ dreamcoder ask-all\n\n✗ ${err.message}`);
    toast("Ask All failed", "error");
    setStatus("Offline");
  } finally {
    if (btn) btn.disabled = false;
  }
}
const askAllBtn = document.getElementById("askAllBtn");
if (askAllBtn) askAllBtn.onclick = askAllModels;

/* ========== WebSocket streaming ========== */
let streamWs = null;

function streamComplete() {
  const btn = document.getElementById("streamBtn");
  if (btn) btn.disabled = true;
  setStatus("Streaming…");
  setTerminal("$ dreamcoder stream\n\nConnecting WebSocket…\n\n");

  const wsUrl = API_BASE.replace(/^http/, "ws") + "/ws/complete";
  try {
    streamWs = new WebSocket(wsUrl);
  } catch (e) {
    setTerminal(`$ dreamcoder stream\n\n✗ Cannot open WebSocket: ${e.message}`);
    if (btn) btn.disabled = false;
    return;
  }

  let buffer = "";
  streamWs.onopen = () => {
    streamWs.send(JSON.stringify({
      model: modelSelect.value,
      code: editor.value,
      language: "python",
      prompt: "Improve and continue this code with clear comments.",
    }));
  };
  streamWs.onmessage = (ev) => {
    try {
      const msg = JSON.parse(ev.data);
      if (msg.type === "start") {
        setTerminal(`$ dreamcoder stream\n\nModel: ${msg.model}\n\n`);
      } else if (msg.type === "token") {
        buffer += msg.text;
        setTerminal(`$ dreamcoder stream\n\n${buffer}`);
      } else if (msg.type === "done") {
        setTerminal(`$ dreamcoder stream\n\n${buffer}\n\n── done · ${msg.model} · ${msg.latency_ms}ms · ${msg.suggestion_count} suggestions`);
        setStatus("Ready");
        toast(`Stream complete · ${msg.latency_ms}ms`, "success");
        if (btn) btn.disabled = false;
        // offer to insert
        if (buffer.trim()) {
          showModal({
            title: "Streamed completion",
            bodyHtml: `<pre>${escapeHtml(buffer.slice(0, 3000))}</pre>`,
            applyLabel: "Insert at cursor",
            onApply: () => {
              insertSuggestion(buffer.trim());
              toast("Inserted streamed output", "success");
            },
          });
        }
      } else if (msg.type === "error") {
        setTerminal((terminal.textContent || "") + `\n✗ ${msg.message}`);
        if (btn) btn.disabled = false;
      }
    } catch (_) {}
  };
  streamWs.onerror = () => {
    setTerminal((terminal.textContent || "") + "\n✗ WebSocket error – is the backend running?");
    toast("Stream failed", "error");
    if (btn) btn.disabled = false;
  };
  streamWs.onclose = () => {
    if (btn) btn.disabled = false;
  };
}
const streamBtn = document.getElementById("streamBtn");
if (streamBtn) streamBtn.onclick = streamComplete;

/* extra shortcuts */
document.addEventListener("keydown", (e) => {
  if (e.ctrlKey && !e.shiftKey && (e.key === "a" || e.key === "A") && document.activeElement !== editor && document.activeElement !== evolveInput) {
    // only when not typing in inputs – actually Ctrl+A is select-all in editor; use Ctrl+Shift+A
  }
  if (e.ctrlKey && e.shiftKey && (e.key === "A" || e.key === "a")) {
    e.preventDefault();
    askAllModels();
  }
  if (e.ctrlKey && e.shiftKey && (e.key === "T" || e.key === "t")) {
    e.preventDefault();
    streamComplete();
  }
});

/* ========== Project context ========== */
async function loadProjectContext() {
  try {
    const ctx = await api("/api/project/context");
    document.getElementById("projectGoal").value = ctx.goal || "";
    document.getElementById("projectCmd").value = (ctx.commands && ctx.commands[0]) || "";
  } catch (_) {}
}

async function saveProjectContext() {
  const goal = document.getElementById("projectGoal").value.trim();
  const cmd = document.getElementById("projectCmd").value.trim();
  try {
    await api("/api/project/context", {
      method: "POST",
      body: JSON.stringify({ goal, description: goal, commands: cmd ? [cmd] : [] }),
    });
    toast("Project context saved", "success");
    refreshMonitor();
  } catch (err) {
    toast("Could not save context", "error");
  }
}
document.getElementById("saveContextBtn").onclick = saveProjectContext;

/* ========== Live monitor ========== */
function appendChat(role, content) {
  const log = document.getElementById("chatLog");
  const bubble = document.createElement("div");
  bubble.className = `chat-bubble ${role}`;
  const meta = role === "user" ? "You" : "Monitor";
  bubble.innerHTML = `<div class="meta">${meta}</div>${escapeHtml(content).replace(/\n/g, "<br>")}`;
  log.appendChild(bubble);
  log.scrollTop = log.scrollHeight;
}

async function refreshMonitor() {
  try {
    const data = await api("/api/ai/monitor");
    const box = document.getElementById("monitorInsights");
    box.innerHTML = (data.insights || [])
      .map(
        (i) =>
          `<div style="margin-bottom:5px"><strong>${escapeHtml(i.icon || "•")} ${escapeHtml(
            i.title
          )}</strong><br><span class="muted">${escapeHtml(i.detail || "")}</span></div>`
      )
      .join("");
    if (data.goal) {
      document.getElementById("monitorBadge").textContent = "GOAL SET";
    }
  } catch (_) {
    document.getElementById("monitorInsights").textContent =
      "Monitor offline – start backend for live project pulse.";
  }
}

async function sendChat(msg) {
  const text = (msg || document.getElementById("chatInput").value || "").trim();
  if (!text) return;
  appendChat("user", text);
  document.getElementById("chatInput").value = "";
  setStatus("Monitor thinking…");
  try {
    const data = await api("/api/ai/chat", {
      method: "POST",
      body: JSON.stringify({ message: text, model: modelSelect.value }),
    });
    appendChat("assistant", (data.model ? `[${data.model}${data.backend ? ` · ${data.backend}` : ""}]\n` : "") + (data.content || "(empty reply)"));
    setStatus("Ready");
    // If analysis payload, also render analysis card
    if (data.analysis) renderAnalysis(data.analysis);
    toast("Monitor replied", "success", 1800);
  } catch (err) {
    appendChat("assistant", `Offline: ${err.message}\n\nStart the backend to enable project-aware chat.`);
    setStatus("Offline");
  }
}

document.getElementById("chatSend").onclick = () => sendChat();
document.getElementById("chatInput").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendChat();
  }
});
document.getElementById("chatChips").onclick = (e) => {
  const chip = e.target.closest(".chip");
  if (!chip) return;
  sendChat(chip.dataset.chat || chip.textContent);
};

/* ========== Folder analysis ========== */
function openAnalysisDrawer() {
  const drawer = document.getElementById("analysisDrawer");
  const tab = document.getElementById("analysisTab");
  const backdrop = document.getElementById("analysisBackdrop");
  if (!drawer) return;
  drawer.classList.add("open");
  drawer.setAttribute("aria-hidden", "false");
  tab?.classList.add("open");
  tab?.setAttribute("aria-expanded", "true");
  if (backdrop) backdrop.hidden = false;
}
function closeAnalysisDrawer() {
  const drawer = document.getElementById("analysisDrawer");
  const tab = document.getElementById("analysisTab");
  const backdrop = document.getElementById("analysisBackdrop");
  drawer?.classList.remove("open");
  drawer?.setAttribute("aria-hidden", "true");
  tab?.classList.remove("open");
  tab?.setAttribute("aria-expanded", "false");
  if (backdrop) backdrop.hidden = true;
}
function initAnalysisDrawer() {
  const tab = document.getElementById("analysisTab");
  const close = document.getElementById("analysisClose");
  const backdrop = document.getElementById("analysisBackdrop");
  tab?.addEventListener("mouseenter", openAnalysisDrawer);
  tab?.addEventListener("click", () => {
    const open = document.getElementById("analysisDrawer")?.classList.contains("open");
    open ? closeAnalysisDrawer() : openAnalysisDrawer();
  });
  close?.addEventListener("click", closeAnalysisDrawer);
  backdrop?.addEventListener("click", closeAnalysisDrawer);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeAnalysisDrawer();
  });
}
initAnalysisDrawer();

function renderAnalysis(data) {
  openAnalysisDrawer();
  const modelInfo = data.model_analysis || {};
  const health = data.health ?? "—";
  document.getElementById("analysisTabHealth").textContent = health + "%";
  document.getElementById("analysisHealthDrawer").textContent = health + "%";
  document.getElementById("analysisModelDrawer").textContent =
    (modelInfo.model || modelSelect.value) + (modelInfo.backend ? " · " + modelInfo.backend : "");
  document.getElementById("analysisScope").textContent =
    "Current indexed folder only · " + ((data.scope && data.scope.files) || []).length + " files";
  document.getElementById("analysisSummaryDrawer").textContent =
    modelInfo.summary || data.summary || "";
  document.getElementById("analysisProjectType").innerHTML =
    "<strong>Project type:</strong> " + escapeHtml(modelInfo.project_type || "Not identified yet");

  let html = "";
  if (modelInfo.architecture?.length) {
    html += '<div class="analysis-section">Architecture</div><div class="analysis-model-note">' +
      modelInfo.architecture.map(escapeHtml).join("<br>") + "</div>";
  }
  if (modelInfo.strengths?.length) {
    html += '<div class="analysis-section">What is already working</div><div class="analysis-model-note">' +
      modelInfo.strengths.map(escapeHtml).join("<br>") + "</div>";
  }
  if (modelInfo.risks?.length) {
    html += '<div class="analysis-section">Risks / opportunities</div><div class="analysis-model-note">' +
      modelInfo.risks.map(escapeHtml).join("<br>") + "</div>";
  }

  const actions = data.actions || [];
  if (actions.length) {
    html += '<div class="analysis-section">Model-proposed live updates</div>';
    actions.forEach((a, i) => {
      html += '<div class="analysis-recommendation" data-analysis-action="' + i + '">' +
        '<div class="rec-head"><span class="rec-title">' + escapeHtml(a.title) + '</span>' +
        '<span class="rec-priority">' + escapeHtml(a.priority || "medium") + '</span></div>' +
        (a.path ? '<div class="rec-path">' + escapeHtml(a.path) + '</div>' : '') +
        '<div class="rec-detail">' + escapeHtml(a.detail || a.instruction || "") + '</div>' +
        (a.instruction ? '<div class="rec-detail"><strong>Model instruction:</strong> ' + escapeHtml(a.instruction) + '</div>' : '') +
        '<div class="rec-actions">' +
        (a.path ? '<button class="btn primary" data-generate-analysis="' + i + '">Generate update</button>' : '') +
        '</div></div>';
    });
  } else {
    html += '<div class="analysis-model-note">No model recommendations were returned for this folder. Try another selected model or refine the project goal.</div>';
  }

  const reports = data.file_reports || [];
  if (reports.length) {
    html += '<div class="analysis-section">File findings</div>';
    reports.forEach((f) => {
      const findings = [...(f.issues || []), ...(f.ideas || [])].slice(0, 4);
      if (!findings.length) return;
      html += '<div class="analysis-recommendation">' +
        '<div class="rec-title">' + escapeHtml(f.path) + '</div>' +
        '<div class="rec-detail">' + findings.map(escapeHtml).join('<br>') + '</div>' +
        '</div>';
    });
  }

  document.getElementById("analysisBodyDrawer").innerHTML = html;
  window._analysisActions = actions;
  window._analysisProposals = {};
  document.getElementById("analysisBodyDrawer").onclick = async (e) => {
    const generate = e.target.closest("[data-generate-analysis]");
    const apply = e.target.closest("[data-apply-analysis]");
    if (generate) {
      const idx = Number(generate.dataset.generateAnalysis);
      await generateAnalysisUpdate(idx);
    }
    if (apply) {
      const idx = Number(apply.dataset.applyAnalysis);
      await applyAnalysisProposal(idx);
    }
  };
}

async function generateAnalysisUpdate(index) {
  const action = (window._analysisActions || [])[index];
  if (!action?.path) return;
  const card = document.querySelector('[data-analysis-action="' + index + '"]');
  const button = card?.querySelector("[data-generate-analysis]");
  if (button) { button.disabled = true; button.textContent = "Generating…"; }
  try {
    const data = await api("/api/ai/analyze-action", {
      method: "POST",
      body: JSON.stringify({
        model: modelSelect.value,
        path: action.path,
        instruction: action.instruction || action.detail || action.title,
        project_type: document.getElementById("analysisProjectType")?.textContent || "",
      }),
    });
    window._analysisProposals[index] = data;
    if (card) {
      card.querySelector(".rec-actions").innerHTML =
        '<button class="btn" data-apply-analysis="' + index + '">Apply live</button>';
      const diff = document.createElement("div");
      diff.className = "analysis-diff";
      diff.textContent = data.diff || "(model made no file changes)";
      card.appendChild(diff);
    }
    toast("Model update generated — review the diff", "success");
  } catch (err) {
    if (button) { button.disabled = false; button.textContent = "Generate update"; }
    toast("Model update failed: " + err.message, "error");
  }
}

async function applyAnalysisProposal(index) {
  const proposal = (window._analysisProposals || {})[index];
  if (!proposal?.path || proposal.content == null) return;
  const action = (window._analysisActions || [])[index] || {};
  fileBuffers[proposal.path] = proposal.content;
  renderFileTree(Object.keys(fileBuffers));
  openPath(proposal.path);
  await api("/api/files/save", {
    method: "POST",
    body: JSON.stringify({
      path: proposal.path,
      content: proposal.content,
      language: langFromPath(proposal.path),
    }),
  });
  toast("Applied model update: " + (action.title || proposal.path), "success");
  setTerminal("$ dreamcoder model-update\\n\\n✓ " + proposal.path + "\\n  " + (proposal.summary || ""));
  refreshMonitor();
  closeAnalysisDrawer();
}


async function runFolderAnalysis() {
  const btn = document.getElementById("analyzeBtn");
  if (btn) btn.disabled = true;
  openAnalysisDrawer();
  setStatus("Analyzing folder with selected model…");
  setTerminal("$ dreamcoder analyze-folder\\n\\nScanning the indexed folder…");
  try {
    const data = await api("/api/ai/analyze-folder", {
      method: "POST",
      body: JSON.stringify({ model: modelSelect.value }),
    });
    renderAnalysis(data);
    setTerminal(
      "$ dreamcoder analyze-folder\\n\\n" +
      data.summary + "\\n\\n" +
      "Scope: " + ((data.scope && data.scope.files) || []).length + " indexed files\\n" +
      "Model: " + ((data.model_analysis && data.model_analysis.model) || modelSelect.value) + "\\n" +
      "Done in " + data.latency_ms + "ms"
    );
    setStatus("Ready");
    toast("Folder analysis complete", "success");
  } catch (err) {
    setTerminal("$ dreamcoder analyze-folder\\n\\n✗ " + err.message);
    toast("Analysis failed – selected model unavailable?", "error");
    setStatus("Offline");
  } finally {
    if (btn) btn.disabled = false;
  }
}
const analyzeBtn = document.getElementById("analyzeBtn");
if (analyzeBtn) analyzeBtn.onclick = runFolderAnalysis;

/* boot extras */
loadProjectContext();
refreshGithubSyncStatus();
refreshWorkspaceGitStatus();
setInterval(refreshWorkspaceGitStatus, 5000);
refreshMonitor();
setInterval(refreshMonitor, 45000); // keep monitor fresh

/* ========== Chat mode: Project vs General ========== */
let chatMode = "project";
const modeProjectBtn = document.getElementById("modeProject");
const modeGeneralBtn = document.getElementById("modeGeneral");
if (modeProjectBtn && modeGeneralBtn) {
  modeProjectBtn.onclick = () => {
    chatMode = "project";
    modeProjectBtn.classList.add("active-theme");
    modeGeneralBtn.classList.remove("active-theme");
    document.getElementById("monitorBadge").textContent = "PROJECT";
    document.getElementById("chatInput").placeholder = "Ask about this project, code, next steps…";
    toast("Chat mode: Project", "info", 1500);
  };
  modeGeneralBtn.onclick = () => {
    chatMode = "general";
    modeGeneralBtn.classList.add("active-theme");
    modeProjectBtn.classList.remove("active-theme");
    document.getElementById("monitorBadge").textContent = "GENERAL";
    document.getElementById("chatInput").placeholder = "Ask anything — coding concepts, ideas, general questions…";
    toast("Chat mode: General", "info", 1500);
  };
}

// Patch sendChat to include mode (override previous by redefining)
const _origSendChat = typeof sendChat === "function" ? sendChat : null;
async function sendChat(msg) {
  const text = (msg || document.getElementById("chatInput").value || "").trim();
  if (!text) return;
  appendChat("user", text);
  document.getElementById("chatInput").value = "";
  setStatus(chatMode === "general" ? "General chat…" : "Monitor thinking…");
  try {
    const data = await api("/api/ai/chat", {
      method: "POST",
      body: JSON.stringify({ message: text, model: modelSelect.value, mode: chatMode }),
    });
    appendChat("assistant", (data.model ? `[${data.model}]\n` : "") + (data.content || "(empty reply)"));
    setStatus("Ready");
    if (data.analysis) renderAnalysis(data.analysis);
    // Optional live updates from analysis / chat
    if (data.actions && data.actions.length) {
      const wrap = document.createElement("div");
      wrap.className = "chat-bubble assistant";
      wrap.innerHTML = "<div class=\"meta\">Live fixes</div>";
      data.actions.slice(0, 8).forEach((a, i) => {
        if (!a.path && a.target === "note") return;
        const row = document.createElement("div");
        row.style.marginTop = "6px";
        row.innerHTML = `<button class="btn primary" style="width:100%;margin-top:4px" data-ca="${i}">Apply: ${escapeHtml(a.title || a.id || "fix")}</button>`;
        wrap.appendChild(row);
      });
      wrap.onclick = (e) => {
        const b = e.target.closest("[data-ca]");
        if (!b) return;
        const a = data.actions[Number(b.dataset.ca)];
        if (!a) return;
        if (a.path && a.code != null && typeof applyAnalysisAction === "function") applyAnalysisAction(a);
        else if (typeof applyPatch === "function") applyPatch(a, null);
      };
      document.getElementById("chatLog")?.appendChild(wrap);
    }
    toast(chatMode === "general" ? "General reply" : "Project reply", "success", 1600);
  } catch (err) {
    appendChat("assistant", `Offline: ${err.message}`);
    setStatus("Offline");
  }
}
document.getElementById("chatSend").onclick = () => sendChat();
document.getElementById("chatInput").onkeydown = (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendChat();
  }
};

/* ========== Drag & drop folders / files ========== */
const TEXT_EXTS = new Set([
  "py","js","ts","tsx","jsx","html","css","md","json","toml","yaml","yml",
  "txt","rs","go","java","c","cpp","h","hpp","rb","php","sh","bat","ps1",
  "sql","env","ini","cfg","xml","svg",
]);

function langFromPath(path) {
  const ext = (path.split(".").pop() || "").toLowerCase();
  return {
    py: "python", js: "javascript", ts: "typescript", tsx: "typescript",
    jsx: "javascript", html: "html", css: "css", md: "markdown", json: "json",
  }[ext] || "text";
}

function readEntryFile(fileEntry) {
  return new Promise((resolve, reject) => {
    fileEntry.file((file) => {
      const reader = new FileReader();
      reader.onload = () => resolve({ path: fileEntry.fullPath.replace(/^\//, ""), content: reader.result, file });
      reader.onerror = reject;
      reader.readAsText(file);
    }, reject);
  });
}

function readDirectory(dirEntry) {
  return new Promise((resolve) => {
    const reader = dirEntry.createReader();
    const all = [];
    const readBatch = () => {
      reader.readEntries(async (entries) => {
        if (!entries.length) {
          resolve(all);
          return;
        }
        for (const entry of entries) {
          if (entry.isFile) all.push(entry);
          else if (entry.isDirectory) {
            if (entry.name.startsWith(".") || entry.name === "node_modules" || entry.name === "__pycache__" || entry.name === "venv") continue;
            const sub = await readDirectory(entry);
            all.push(...sub);
          }
        }
        readBatch();
      });
    };
    readBatch();
  });
}

async function collectDroppedItems(dataTransfer) {
  const items = dataTransfer.items;
  const fileEntries = [];
  if (items && items.length) {
    const entries = [];
    for (let i = 0; i < items.length; i++) {
      const entry = items[i].webkitGetAsEntry?.();
      if (entry) entries.push(entry);
    }
    for (const entry of entries) {
      if (entry.isFile) fileEntries.push(entry);
      else if (entry.isDirectory) {
        const sub = await readDirectory(entry);
        fileEntries.push(...sub);
      }
    }
  }
  // Fallback: plain files list
  if (!fileEntries.length && dataTransfer.files?.length) {
    return Array.from(dataTransfer.files).map((f) => ({
      path: f.webkitRelativePath || f.name,
      content: null,
      file: f,
    }));
  }
  const results = [];
  for (const entry of fileEntries) {
    try {
      const r = await readEntryFile(entry);
      results.push(r);
    } catch (_) {}
  }
  return results;
}

async function readFileBlob(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsText(file);
  });
}

async function ingestFiles(rawList, rootName, replaceExisting = false) {
  const payload = [];
  for (const item of rawList) {
    const path = (item.path || item.file?.name || "file").replace(/\\/g, "/");
    const ext = path.split(".").pop()?.toLowerCase() || "";
    if (ext && !TEXT_EXTS.has(ext)) continue;
    if (path.split("/").some((p) => p.startsWith(".") || p === "node_modules" || p === "__pycache__")) continue;
    let content = item.content;
    if (content == null && item.file) {
      try {
        content = await readFileBlob(item.file);
      } catch (_) {
        continue;
      }
    }
    if (typeof content !== "string") continue;
    // skip huge files
    if (content.length > 400000) continue;
    payload.push({ path, content, language: langFromPath(path) });
  }
  if (!payload.length) {
    toast("No text source files found in drop", "info");
    return;
  }

  if (replaceExisting) {
    fileBuffers = {};
    currentPath = "";
    renderFileTree([]);
  }

  setStatus(`Indexing ${payload.length} files…`);
  setTerminal(`$ dreamcoder import\n\nIndexing ${payload.length} files from drop…`);

  // Update local buffers + tree
  payload.forEach((f) => {
    fileBuffers[f.path] = f.content;
  });
  renderFileTree(Object.keys(fileBuffers));
  if (rootName) {
    document.getElementById("projectNameLabel").textContent = `◈ ${rootName}`;
  }

  // Open first file
  const first = payload[0];
  if (first) {
    currentPath = first.path;
    editor.value = first.content;
    updateLines();
    syncStatus();
    const tab = document.querySelector(".tab.active");
    if (tab) tab.innerHTML = `${first.path.split("/").pop()} <span>×</span>`;
  }

  try {
    const data = await api("/api/files/bulk", {
      method: "POST",
      body: JSON.stringify({ files: payload, root_name: rootName || "dropped-project", replace_existing: replaceExisting }),
    });
    setTerminal(
      `$ dreamcoder import\n\n✓ Indexed ${data.indexed} files\n` +
        `  symbols: ${data.stats?.symbols ?? "—"}\n` +
        `  root: ${data.root_name}`
    );
    setStatus("Ready");
    toast(`Imported ${data.indexed} files`, "success");
    refreshMonitor();
  } catch (err) {
    setTerminal(`$ dreamcoder import\n\n✓ Loaded ${payload.length} files locally\n✗ Backend index failed: ${err.message}`);
    setStatus("Local only");
    toast(`Loaded ${payload.length} files (backend offline)`, "info");
  }
}

async function openNativeWorkspace(root) {
  try {
    const data = await api("/api/workspace", { method: "POST", body: JSON.stringify({ root }) });
    await api("/api/watch", { method: "POST", body: JSON.stringify({ root }) });
    setStatus("Workspace connected");
    toast("Connected " + data.root, "success");
    await refreshWorkspaceGitStatus();
    await refreshMonitor();
    const listing = await api("/api/files");
    const files = listing?.files || [];
    fileBuffers = {};
    const paths = files.map(f => f.path).filter(Boolean);
    renderFileTree(paths);
    const first = paths[0];
    if (first) {
      const file = await api("/api/files/" + encodeURIComponent(first));
      fileBuffers[first] = file.content || "";
      openPath(first);
    }
  } catch (err) {
    toast("Workspace connection failed: " + err.message, "error");
    setStatus("Workspace error");
  }
}

function renderFileTree(paths) {
  const tree = document.getElementById("fileTree");
  if (!tree) return;
  // Group by top-level folder
  const sorted = [...paths].sort();
  tree.innerHTML = "";
  let lastDir = null;
  sorted.forEach((path) => {
    const parts = path.split("/");
    if (parts.length > 1) {
      const dir = parts[0];
      if (dir !== lastDir) {
        lastDir = dir;
        const folderBtn = document.createElement("button");
        folderBtn.className = "file active";
        folderBtn.textContent = `▾ ${dir}`;
        tree.appendChild(folderBtn);
      }
    }
    const btn = document.createElement("button");
    btn.className = "file" + (parts.length > 1 ? " indent" : "");
    if (path === currentPath) btn.classList.add("active-file");
    btn.dataset.path = path;
    btn.textContent = `◇ ${parts[parts.length - 1]}`;
    btn.onclick = () => openPath(path);
    tree.appendChild(btn);
  });
}

function openPath(path) {
  if (!path) return;
  const previousPath = currentPath;
  const previousContent = editor.value;
  fileBuffers[previousPath] = previousContent;

  if (previousPath && previousPath !== path) {
    githubSyncPromise = githubSyncPromise.catch(() => {}).then(async () => {
      try {
        const data = await api("/api/files/save", {
          method: "POST",
          body: JSON.stringify({
            path: previousPath,
            content: previousContent,
            language: langFromPath(previousPath),
            sync_github: true,
            commit_message: "DreamCoder file switch save: " + previousPath,
          }),
        });
        if (data.github?.ok) setGithubSyncState("synced ✓", "ready");
      } catch (_) {}
    });
  }

  if (!(path in fileBuffers)) fileBuffers[path] = "";
  currentPath = path;
  editor.value = fileBuffers[path] || "";
  updateLines();
  syncStatus();
  document.querySelectorAll(".file").forEach((f) => {
    f.classList.toggle("active-file", f.dataset.path === path);
  });
  if (typeof renderTabs === "function") renderTabs();
  setStatus(`Opened ${path}`);
}

// Drop zone wiring
const dropZone = document.getElementById("dropZone");
const folderInput = document.getElementById("folderInput");
const filesInput = document.getElementById("filesInput");

if (dropZone) {
  ["dragenter", "dragover"].forEach((ev) => {
    dropZone.addEventListener(ev, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropZone.classList.add("drag-over");
    });
  });
  ["dragleave", "drop"].forEach((ev) => {
    dropZone.addEventListener(ev, (e) => {
      e.preventDefault();
      e.stopPropagation();
      if (ev === "dragleave") dropZone.classList.remove("drag-over");
    });
  });
  dropZone.addEventListener("drop", async (e) => {
    dropZone.classList.remove("drag-over");
    const list = await collectDroppedItems(e.dataTransfer);
    let rootName = "dropped-project";
    if (e.dataTransfer.items?.[0]) {
      const entry = e.dataTransfer.items[0].webkitGetAsEntry?.();
      if (entry?.isDirectory) rootName = entry.name;
    }
    await ingestFiles(list, rootName, true);
  });
  dropZone.addEventListener("click", (e) => {
    if (e.target.closest("input")) return;
    // default open folder picker
    folderInput?.click();
  });
}

document.getElementById("browseFolderBtn")?.addEventListener("click", async (e) => {
  e.stopPropagation();
  if (window.dreamcoderDesktop?.chooseFolder) {
    const root = await window.dreamcoderDesktop.chooseFolder();
    if (root) await openNativeWorkspace(root);
    return;
  }
  folderInput?.click();
});
document.getElementById("browseFilesBtn")?.addEventListener("click", (e) => {
  e.stopPropagation();
  filesInput?.click();
});

folderInput?.addEventListener("change", async () => {
  const files = Array.from(folderInput.files || []);
  const list = files.map((f) => ({ path: f.webkitRelativePath || f.name, content: null, file: f }));
  const rootName = files[0]?.webkitRelativePath?.split("/")[0] || "folder";
  await ingestFiles(list, rootName);
  folderInput.value = "";
});

filesInput?.addEventListener("change", async () => {
  const files = Array.from(filesInput.files || []);
  const list = files.map((f) => ({ path: f.name, content: null, file: f }));
  await ingestFiles(list, "files");
  filesInput.value = "";
});

// Also allow dropping on the whole workspace
document.querySelector(".workspace")?.addEventListener("dragover", (e) => {
  e.preventDefault();
});
document.querySelector(".workspace")?.addEventListener("drop", async (e) => {
  if (e.target.closest("#dropZone")) return;
  e.preventDefault();
  const list = await collectDroppedItems(e.dataTransfer);
  if (list.length) await ingestFiles(list, "dropped-project", true);
});

/* ========== Hugging Face catalog ========== */
let hfCatalog = { organized: {}, models: [] };
let hfCategory = "all";

async function loadHfCatalog(search = "", refresh = false) {
  const list = document.getElementById("hfModelList");
  if (!list) return;
  list.textContent = refresh ? "Refreshing from Hugging Face…" : "Loading open models…";
  try {
    const q = new URLSearchParams();
    if (search) q.set("search", search);
    if (refresh) q.set("refresh", "true");
    const data = await api("/api/models/huggingface?" + q.toString());
    hfCatalog = data;
    renderHfCategories(data.organized || {});
    renderHfModels(data);
    const n = data.total || (data.models || []).length;
    toast(`${n} HF models${data.cached ? " (cached)" : ""}`, "success", 2000);
  } catch (err) {
    list.textContent = "Could not load HF catalog – backend offline? Curated list still available when API is up.";
  }
}

function renderHfCategories(organized) {
  const el = document.getElementById("hfCategories");
  if (!el) return;
  const cats = ["all", ...Object.keys(organized).filter((k) => (organized[k] || []).length)];
  el.innerHTML = cats
    .map(
      (c) =>
        `<button class="chip${c === hfCategory ? " active-theme" : ""}" data-hf-cat="${c}" type="button">${c}</button>`
    )
    .join("");
  el.onclick = (e) => {
    const btn = e.target.closest("[data-hf-cat]");
    if (!btn) return;
    hfCategory = btn.dataset.hfCat;
    renderHfCategories(hfCatalog.organized || {});
    renderHfModels(hfCatalog);
  };
}

function renderHfModels(data) {
  const list = document.getElementById("hfModelList");
  if (!list) return;
  let models = data.models || [];
  if (hfCategory !== "all" && data.organized?.[hfCategory]) {
    models = data.organized[hfCategory];
  }
  if (!models.length) {
    list.textContent = "No models in this category.";
    return;
  }
  list.innerHTML = "";
  models.slice(0, 40).forEach((m) => {
    const btn = document.createElement("button");
    btn.className = "hf-item";
    btn.type = "button";
    btn.innerHTML = `
      <span class="hf-id">${escapeHtml(m.id || m.name)}</span>
      <span class="hf-meta">${escapeHtml(m.category || "")} · ↓${formatNum(m.downloads)} · ♥${formatNum(m.likes)} · ${escapeHtml(m.source || "")}</span>`;
    btn.onclick = () => selectHfModel(m);
    list.appendChild(btn);
  });
}

function formatNum(n) {
  n = Number(n) || 0;
  if (n >= 1e6) return (n / 1e6).toFixed(1) + "M";
  if (n >= 1e3) return (n / 1e3).toFixed(1) + "k";
  return String(n);
}

async function selectHfModel(m) {
  const id = m.id || m.name;
  modelCurrent.textContent = id.split("/").pop();
  // Add to select if missing
  let opt = [...modelSelect.options].find((o) => o.value === id);
  if (!opt) {
    opt = document.createElement("option");
    opt.value = id;
    opt.textContent = id;
    modelSelect.appendChild(opt);
  }
  modelSelect.value = id;
  document.querySelectorAll(".hf-item").forEach((el) => el.classList.remove("active-hf"));
  // mark clicked roughly
  toast(`HF model → ${id}`, "success");
  setStatus(`Model: ${id}`);
  try {
    await api("/api/models/huggingface/select", {
      method: "POST",
      body: JSON.stringify({ model_id: id }),
    });
  } catch (_) {}
}

document.getElementById("hfRefresh")?.addEventListener("click", () => {
  loadHfCatalog(document.getElementById("hfSearch")?.value || "", true);
});
document.getElementById("hfSearch")?.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    loadHfCatalog(e.target.value || "", false);
  }
});

// Load catalog on boot
setTimeout(() => loadHfCatalog(), 800);

/* ========== Refresh / update animation ========== */
let _refreshTimer = null;
function playRefreshAnimation(label = "Updating…") {
  const overlay = document.getElementById("refreshOverlay");
  const text = document.getElementById("refreshText");
  const shell = document.querySelector(".app-shell");
  if (text) text.textContent = label;
  if (overlay) overlay.classList.add("show");
  if (shell) shell.classList.add("updating");
  document.querySelector(".topbar")?.classList.add("flash-update");
  clearTimeout(_refreshTimer);
  _refreshTimer = setTimeout(() => {
    overlay?.classList.remove("show");
    shell?.classList.remove("updating");
    document.querySelector(".topbar")?.classList.remove("flash-update");
  }, 650);
}

// Wrap toast to optionally trigger refresh feel on success updates
const _toast = toast;
toast = function (msg, type = "info", ms = 3200) {
  if (type === "success") playRefreshAnimation(msg);
  return _toast(msg, type, ms);
};

// Explicit refresh on major actions
const _runCode = runCode;
runCode = async function () {
  playRefreshAnimation("Running…");
  return _runCode.apply(this, arguments);
};
const _getSuggestions = getSuggestions;
getSuggestions = async function () {
  playRefreshAnimation("Suggesting…");
  return _getSuggestions.apply(this, arguments);
};
if (typeof askAllModels === "function") {
  const _askAll = askAllModels;
  askAllModels = async function () {
    playRefreshAnimation("Asking all models…");
    return _askAll.apply(this, arguments);
  };
}
if (typeof runFolderAnalysis === "function") {
  const _an = runFolderAnalysis;
  runFolderAnalysis = async function () {
    playRefreshAnimation("Analyzing folder…");
    return _an.apply(this, arguments);
  };
}
if (typeof loadHfCatalog === "function") {
  const _hf = loadHfCatalog;
  loadHfCatalog = async function () {
    playRefreshAnimation("Loading HF models…");
    return _hf.apply(this, arguments);
  };
}
if (typeof ingestFiles === "function") {
  const _ing = ingestFiles;
  ingestFiles = async function () {
    playRefreshAnimation("Importing files…");
    return _ing.apply(this, arguments);
  };
}
if (typeof evolveApp === "function") {
  const _ev = evolveApp;
  evolveApp = async function (prompt) {
    playRefreshAnimation("Evolving…");
    return _ev(prompt);
  };
}

// Keyboard: Ctrl+Shift+D → debug page
document.addEventListener("keydown", (e) => {
  if (e.ctrlKey && e.shiftKey && (e.key === "D" || e.key === "d")) {
    e.preventDefault();
    window.location.href = "debug.html";
  }
});

/* ========== Generate Project ========== */
let lastGenerated = null;

async function generateProject(downloadZip = false) {
  const prompt = (document.getElementById("generatePrompt")?.value || "").trim();
  if (!prompt) {
    toast("Describe the project to generate", "info");
    return;
  }
  playRefreshAnimation(downloadZip ? "Packaging zip…" : "Generating project…");
  setStatus("Generating…");
  setTerminal(`$ dreamcoder generate\n\n"${prompt.slice(0, 120)}…"\n\nScaffolding multi-file project…`);
  try {
    if (downloadZip) {
      const res = await fetch(`${API_BASE}/api/ai/generate-project/zip`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt,
          goal: document.getElementById("projectGoal")?.value || "",
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      const blob = await res.blob();
      const disp = res.headers.get("Content-Disposition") || "";
      const match = /filename="?([^"]+)"?/.exec(disp);
      const filename = match?.[1] || "project.zip";
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = filename;
      a.click();
      URL.revokeObjectURL(a.href);
      setTerminal(`$ dreamcoder generate --zip\n\n✓ Downloaded ${filename}`);
      toast(`Downloaded ${filename}`, "success");
      setStatus("Ready");
      return;
    }

    const data = await api("/api/ai/generate-project", {
      method: "POST",
      body: JSON.stringify({
        prompt,
        goal: document.getElementById("projectGoal")?.value || "",
      }),
    });
    lastGenerated = data;
    renderGenerated(data);
    setTerminal(
      `$ dreamcoder generate\n\n${data.summary}\n` +
        `Stack: ${data.stack?.language} / ${data.stack?.build}\n` +
        `Files: ${data.file_count}\n` +
        `Run: ${data.run_hint}\n` +
        `Done in ${data.latency_ms}ms`
    );
    setStatus("Ready");
    toast(data.summary, "success");
    appendChat("assistant", `${data.summary}\n\nRun hint:\n${data.run_hint}\n\nClick “Load into workspace” or Download zip.`);
  } catch (err) {
    setTerminal(`$ dreamcoder generate\n\n✗ ${err.message}`);
    toast("Generate failed", "error");
    setStatus("Offline");
  }
}

function renderGenerated(data) {
  const pagesEl = document.getElementById("generatePages");
  const filesEl = document.getElementById("generateFiles");
  const applyRow = document.getElementById("generateApplyRow");
  if (pagesEl) {
    pagesEl.innerHTML = (data.pages || [])
      .map((p, i) => `<div style="margin:3px 0"><b>${i + 1}. ${escapeHtml(p.title)}</b> — ${escapeHtml(p.detail || "")}</div>`)
      .join("");
  }
  if (filesEl) {
    filesEl.innerHTML = "";
    (data.files || []).forEach((f) => {
      const btn = document.createElement("button");
      btn.className = "hf-item";
      btn.type = "button";
      btn.innerHTML = `<span class="hf-id">${escapeHtml(f.path)}</span><span class="hf-meta">${(f.content || "").length} chars</span>`;
      btn.onclick = () => {
        showModal({
          title: f.path,
          bodyHtml: `<pre>${escapeHtml((f.content || "").slice(0, 4000))}</pre>`,
          applyLabel: "Open in editor",
          onApply: () => {
            fileBuffers[f.path] = f.content || "";
            openPath(f.path);
          },
        });
      };
      filesEl.appendChild(btn);
    });
  }
  if (applyRow) applyRow.style.display = data.files?.length ? "flex" : "none";
}

async function loadGeneratedIntoWorkspace() {
  if (!lastGenerated?.files?.length) {
    toast("Generate a project first", "info");
    return;
  }
  playRefreshAnimation("Writing + building project…");
  setStatus("Building generated project…");
  setTerminal("$ dreamcoder generate --build\\n\\nWriting generated files to the connected workspace…");
  try {
    const result = await api("/api/ai/generate-project/build", {
      method: "POST",
      body: JSON.stringify({ files: lastGenerated.files, name: lastGenerated.name || "generated-app", stack: lastGenerated.stack || {}, sync_github: true }),
    });
    lastGenerated.build = result;
    const files = lastGenerated.files;
    files.forEach((f) => { fileBuffers[f.path] = f.content || ""; });
    renderFileTree(Object.keys(fileBuffers));
    document.getElementById("projectNameLabel").textContent = `◈ ${lastGenerated.name || "generated"}`;
    const first = files[0];
    if (first) openPath(first.path);
    const v = result.validation || {};
    setTerminal(
      `$ dreamcoder generate --build\\n\\n` +
      `Project: ${result.name}\\n` +
      `Files written: ${result.file_count}\\n` +
      `Build: ${result.build_command || "materialized only"}\\n` +
      `${result.ok ? "✓ BUILD PASSED" : "✗ BUILD FAILED"}\\n\\n` +
      `${v.stdout || ""}${v.stderr || ""}${v.error || ""}`
    );
    if (result.ok) {
      setStatus("Build passed");
      toast(`Built ${result.name} successfully`, "success");
    } else {
      setStatus("Build failed");
      toast("Project was written, but the build failed. Use the validation output to self-heal.", "error", 5000);
    }
    refreshMonitor();
    refreshWorkspaceGitStatus();
  } catch (err) {
    setTerminal(`$ dreamcoder generate --build\\n\\n✗ ${err.message}`);
    setStatus("Build failed");
    toast("Build/load failed: " + err.message, "error");
  }
}

document.getElementById("generateBtn")?.addEventListener("click", () => {
  document.getElementById("generatePrompt")?.focus();
  toast("Describe the app below, then Generate", "info");
});
document.getElementById("generateGoBtn")?.addEventListener("click", () => generateProject(false));
document.getElementById("generateZipBtn")?.addEventListener("click", () => generateProject(true));
document.getElementById("generateApplyBtn")?.addEventListener("click", loadGeneratedIntoWorkspace);

/* ========== Self-Heal ========== */
async function runSelfHeal() {
  const errorText = (document.getElementById("healError")?.value || "").trim();
  if (!errorText) {
    toast("Paste an error message first", "info");
    return;
  }
  playRefreshAnimation("Self-healing…");
  const files = Object.keys(fileBuffers).map((path) => ({ path, content: fileBuffers[path] }));
  try {
    const data = await api("/api/ai/self-heal", {
      method: "POST",
      body: JSON.stringify({
        error_text: errorText,
        language: langFromPath(currentPath),
        files: files.slice(0, 40),
      }),
    });
    const box = document.getElementById("healResult");
    let html = (data.reasons || []).map((r) => `• ${escapeHtml(r)}`).join("<br>");
    if (data.patches?.length) {
      html += `<div style="margin-top:8px;font-weight:650">Patches (${data.patches.length})</div>`;
      data.patches.forEach((p) => {
        html += `<div class="hf-item"><span class="hf-id">${escapeHtml(p.action)} ${escapeHtml(p.path)}</span></div>`;
      });
      html += `<button class="btn primary" id="applyHealBtn" style="margin-top:8px;width:100%">Apply patches</button>`;
    }
    box.innerHTML = html || "No automatic fix found.";
    document.getElementById("applyHealBtn")?.addEventListener("click", () => {
      (data.patches || []).forEach((p) => {
        fileBuffers[p.path] = p.content || "";
      });
      renderFileTree(Object.keys(fileBuffers));
      toast("Heal patches applied", "success");
      if (data.patches[0]) openPath(data.patches[0].path);
    });
    setTerminal(`$ dreamcoder self-heal\n\n${(data.reasons || []).join("\n")}\nPatches: ${(data.patches || []).length}`);
    toast("Self-heal complete", "success");
  } catch (err) {
    toast("Self-heal failed", "error");
    setTerminal(`$ dreamcoder self-heal\n\n✗ ${err.message}`);
  }
}
document.getElementById("healBtn")?.addEventListener("click", runSelfHeal);

/* ========== Theme packs (incl. peach / shroom) ========== */
const THEMES = {
  midnight: { bg: "#0b0e14", panel: "#11151e", accent: "#7c8cff", accent2: "#4de0b8" },
  graphite: { bg: "#101214", panel: "#17191c", accent: "#7c8cff", accent2: "#4de0b8" },
  violet: { bg: "#0e0b14", panel: "#11151e", accent: "#b48cff", accent2: "#4de0b8" },
  peach: { bg: "#1a1210", panel: "#241a18", accent: "#ffb38a", accent2: "#ff8fab" },
  shroom: { bg: "#14101a", panel: "#1c1524", accent: "#e8a0bf", accent2: "#9dffb0" },
  ocean: { bg: "#0a1218", panel: "#0f1a22", accent: "#5ec8ff", accent2: "#3dffa8" },
  ember: { bg: "#140e0c", panel: "#1e1410", accent: "#ff7a45", accent2: "#ffd166" },
};

function applyTheme(name) {
  const t = THEMES[name] || THEMES.midnight;
  const root = document.documentElement;
  root.style.setProperty("--bg", t.bg);
  root.style.setProperty("--panel", t.panel);
  root.style.setProperty("--accent", t.accent);
  root.style.setProperty("--accent2", t.accent2);
  document.querySelectorAll(".theme[data-theme]").forEach((b) => {
    b.classList.toggle("active-theme", b.dataset.theme === name);
  });
  localStorage.setItem("dc_theme", name);
  playRefreshAnimation(`Theme: ${name}`);
}

// Rebind theme buttons (replace old handlers)
document.querySelectorAll(".theme[data-theme]").forEach((btn) => {
  btn.onclick = () => applyTheme(btn.dataset.theme);
});
const savedTheme = localStorage.getItem("dc_theme");
if (savedTheme && THEMES[savedTheme]) applyTheme(savedTheme);

/* ========== Interactive cursor ========== */
let cursorOn = false;
function setCursorFx(on) {
  cursorOn = on;
  document.body.classList.toggle("cursor-fx", on);
  document.getElementById("fxCursor")?.classList.toggle("active-theme", on);
  let dot = document.getElementById("cursorDot");
  let ring = document.getElementById("cursorRing");
  if (on) {
    if (!dot) {
      dot = document.createElement("div");
      dot.id = "cursorDot";
      document.body.appendChild(dot);
    }
    if (!ring) {
      ring = document.createElement("div");
      ring.id = "cursorRing";
      document.body.appendChild(ring);
    }
  } else {
    dot?.remove();
    ring?.remove();
  }
  localStorage.setItem("dc_cursor", on ? "1" : "0");
}
document.addEventListener("mousemove", (e) => {
  if (!cursorOn) return;
  const dot = document.getElementById("cursorDot");
  const ring = document.getElementById("cursorRing");
  if (dot) {
    dot.style.left = e.clientX + "px";
    dot.style.top = e.clientY + "px";
  }
  if (ring) {
    ring.style.left = e.clientX + "px";
    ring.style.top = e.clientY + "px";
  }
});
document.getElementById("fxCursor")?.addEventListener("click", () => setCursorFx(!cursorOn));
if (localStorage.getItem("dc_cursor") === "1") setCursorFx(true);

/* ========== Particles ========== */
let particlesOn = false;
let particleRaf = 0;
function setParticles(on) {
  particlesOn = !!on;
  document.getElementById("fxParticles")?.classList.toggle("active-theme", particlesOn);
  let canvas = document.getElementById("particleCanvas");
  cancelAnimationFrame(particleRaf);
  if (!particlesOn) {
    canvas?.remove();
    localStorage.setItem("dc_particles", "0");
    toast("Particles off", "info", 1200);
    return;
  }
  if (!canvas) {
    canvas = document.createElement("canvas");
    canvas.id = "particleCanvas";
    document.body.appendChild(canvas);
  }
  const ctx = canvas.getContext("2d");
  const resize = () => {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
  };
  resize();
  window.addEventListener("resize", resize);
  const opts = window.DC_PARTICLE_OPTS || {};
  const count = opts.count || 80;
  const spd = opts.speed || 0.8;
  const sz = opts.size || 2;
  const pts = Array.from({ length: count }, () => ({
    x: Math.random() * canvas.width,
    y: Math.random() * canvas.height,
    vx: (Math.random() - 0.5) * spd,
    vy: (Math.random() - 0.5) * spd,
    r: sz * (0.7 + Math.random()),
  }));
  const accent = () => getComputedStyle(document.documentElement).getPropertyValue("--accent").trim() || "#7c8cff";
  const accent2 = () => getComputedStyle(document.documentElement).getPropertyValue("--accent2").trim() || "#4de0b8";
  const loop = () => {
    if (!particlesOn) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    for (let i = 0; i < pts.length; i++) {
      const p = pts[i];
      p.x += p.vx; p.y += p.vy;
      if (p.x < 0 || p.x > canvas.width) p.vx *= -1;
      if (p.y < 0 || p.y > canvas.height) p.vy *= -1;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fillStyle = i % 2 ? accent() : accent2();
      ctx.globalAlpha = 0.65;
      ctx.fill();
    }
    ctx.globalAlpha = 0.25;
    ctx.strokeStyle = accent();
    ctx.lineWidth = 1;
    for (let i = 0; i < pts.length; i++) {
      for (let j = i + 1; j < pts.length; j++) {
        const dx = pts[i].x - pts[j].x, dy = pts[i].y - pts[j].y;
        const d = Math.hypot(dx, dy);
        if (d < 150) {
          ctx.beginPath();
          ctx.moveTo(pts[i].x, pts[i].y);
          ctx.lineTo(pts[j].x, pts[j].y);
          ctx.stroke();
        }
      }
    }
    particleRaf = requestAnimationFrame(loop);
  };
  loop();
  localStorage.setItem("dc_particles", "1");
  toast("Particles on — look at the background", "success", 2000);
}

document.getElementById("fxParticles")?.addEventListener("click", () => setParticles(!particlesOn));
if (localStorage.getItem("dc_particles") === "1") setParticles(true);

/* ========== Project tabs from saved context ========== */
const PROJECTS_KEY = "dc_projects";
function loadProjects() {
  try {
    return JSON.parse(localStorage.getItem(PROJECTS_KEY) || "[]");
  } catch {
    return [];
  }
}
function saveProjects(list) {
  localStorage.setItem(PROJECTS_KEY, JSON.stringify(list));
}
function renderProjectTabs(activeId) {
  const el = document.getElementById("projectTabs");
  if (!el) return;
  const list = loadProjects();
  el.innerHTML = list
    .map(
      (p) =>
        `<button class="project-tab${p.id === activeId ? " active-project" : ""}" data-pid="${p.id}" type="button" title="${escapeHtml(p.goal || p.name)}">${escapeHtml(p.name)} <span class="x" data-close="${p.id}">×</span></button>`
    )
    .join("");
  el.onclick = (e) => {
    const close = e.target.closest("[data-close]");
    if (close) {
      e.stopPropagation();
      const id = close.dataset.close;
      saveProjects(loadProjects().filter((p) => p.id !== id));
      renderProjectTabs();
      toast("Project tab removed", "info");
      return;
    }
    const tab = e.target.closest("[data-pid]");
    if (!tab) return;
    const id = tab.dataset.pid;
    const proj = loadProjects().find((p) => p.id === id);
    if (!proj) return;
    activateProject(proj);
  };
}

function activateProject(proj) {
  document.getElementById("projectNameLabel").textContent = `◈ ${proj.name}`;
  document.getElementById("projectGoal").value = proj.goal || "";
  document.getElementById("projectCmd").value = proj.cmd || "";
  // Restore file buffers if stored
  if (proj.files && typeof proj.files === "object") {
    Object.keys(fileBuffers).forEach((k) => delete fileBuffers[k]);
    Object.assign(fileBuffers, proj.files);
    const paths = Object.keys(fileBuffers);
    renderFileTree(paths);
    if (paths[0]) openPath(paths[0]);
  }
  renderProjectTabs(proj.id);
  localStorage.setItem("dc_active_project", proj.id);
  // sync backend context
  api("/api/project/context", {
    method: "POST",
    body: JSON.stringify({
      goal: proj.goal || "",
      description: proj.goal || "",
      commands: proj.cmd ? [proj.cmd] : [],
    }),
  }).catch(() => {});
  refreshMonitor();
  toast(`Project: ${proj.name}`, "success");
  playRefreshAnimation(`Switched to ${proj.name}`);
}

// Override save context to also create explorer project tab
const _saveCtx = saveProjectContext;
saveProjectContext = async function () {
  await _saveCtx();
  const goal = document.getElementById("projectGoal").value.trim();
  const cmd = document.getElementById("projectCmd").value.trim();
  if (!goal) return;
  const name = goal.split(/\s+/).slice(0, 3).join(" ") || "Project";
  const id = "p_" + Date.now();
  // snapshot current files
  fileBuffers[currentPath] = editor.value;
  const list = loadProjects();
  list.push({
    id,
    name: name.slice(0, 28),
    goal,
    cmd,
    files: { ...fileBuffers },
    created: Date.now(),
  });
  saveProjects(list);
  renderProjectTabs(id);
  document.getElementById("projectNameLabel").textContent = `◈ ${name.slice(0, 28)}`;
  localStorage.setItem("dc_active_project", id);
  toast(`Project tab “${name.slice(0, 28)}” created`, "success");
};

renderProjectTabs(localStorage.getItem("dc_active_project"));

/* Clarify mode difference in UI when switching */
if (modeProjectBtn && modeGeneralBtn) {
  modeProjectBtn.onclick = () => {
    chatMode = "project";
    modeProjectBtn.classList.add("active-theme");
    modeGeneralBtn.classList.remove("active-theme");
    document.getElementById("monitorBadge").textContent = "PROJECT";
    document.getElementById("chatInput").placeholder =
      "Project mode: uses your files, symbols, and goal…";
    toast("Project mode — answers grounded in this repo", "info", 2200);
  };
  modeGeneralBtn.onclick = () => {
    chatMode = "general";
    modeGeneralBtn.classList.add("active-theme");
    modeProjectBtn.classList.remove("active-theme");
    document.getElementById("monitorBadge").textContent = "GENERAL";
    document.getElementById("chatInput").placeholder =
      "General mode: any topic — not limited to this project…";
    toast("General mode — free-form chat", "info", 2200);
  };
}

/* ========== Undo stack for live patches ========== */
const undoStack = [];
function pushUndo(label, fn) {
  undoStack.push({ label, fn });
  if (undoStack.length > 30) undoStack.shift();
}
function undoLast() {
  const item = undoStack.pop();
  if (!item) {
    toast("Nothing to undo", "info");
    return;
  }
  try {
    item.fn();
    toast(`Undid: ${item.label}`, "success");
    playRefreshAnimation("Undo");
  } catch (e) {
    toast("Undo failed", "error");
  }
}
document.addEventListener("keydown", (e) => {
  if (e.ctrlKey && !e.shiftKey && (e.key === "z" || e.key === "Z")) {
    if (document.activeElement === editor || document.activeElement?.tagName === "TEXTAREA" || document.activeElement?.tagName === "INPUT") {
      // allow native undo in inputs unless alt
      if (!e.altKey) return;
    }
    e.preventDefault();
    undoLast();
  }
});

// Enhance applyPatch to support undo for CSS
const _applyPatch = applyPatch;
applyPatch = function (patch, el) {
  const target = (patch.target || "css").toLowerCase();
  if (target === "css" || target === "style") {
    const style = document.createElement("style");
    style.textContent = patch.code || "";
    document.head.appendChild(style);
    pushUndo(patch.title || "css patch", () => style.remove());
    toast(`Applied CSS: ${patch.title}`, "success");
    if (el && el.remove) if (el && el.remove) el.remove();
    setTerminal((terminal.textContent || "") + `\n\n$ evolve apply\n✓ ${patch.title}`);
    return;
  }
  if (target === "js" || target === "script") {
    try {
      const fn = new Function(patch.code || "");
      fn();
      pushUndo(patch.title || "js patch", () => toast("JS patches may need manual revert", "info"));
      toast(`Applied JS: ${patch.title}`, "success");
      if (el && el.remove) if (el && el.remove) el.remove();
    } catch (err) {
      toast(`Patch failed: ${err.message}`, "error");
    }
    return;
  }
  return _applyPatch(patch, el);
};

/* ========== Command palette (Ctrl+K) ========== */
const COMMANDS = [
  { label: "Theme: Midnight", run: () => applyTheme("midnight") },
  { label: "Theme: Graphite", run: () => applyTheme("graphite") },
  { label: "Theme: Violet", run: () => applyTheme("violet") },
  { label: "Theme: Peach", run: () => applyTheme("peach") },
  { label: "Theme: Shroom", run: () => applyTheme("shroom") },
  { label: "Theme: Ocean", run: () => applyTheme("ocean") },
  { label: "Theme: Ember", run: () => applyTheme("ember") },
  { label: "Particles on", run: () => setParticles(true) },
  { label: "Particles off", run: () => setParticles(false) },
  { label: "Cursor FX on", run: () => setCursorFx(true) },
  { label: "Cursor FX off", run: () => setCursorFx(false) },
  { label: "Run code", run: () => runCode() },
  { label: "Suggest", run: () => getSuggestions() },
  { label: "Ask all models", run: () => askAllModels() },
  { label: "Analyze folder", run: () => runFolderAnalysis() },
  { label: "Run project agent", run: () => runProjectAgent() },
  { label: "Stream completion", run: () => streamComplete() },
  { label: "Open Debug page", run: () => (window.location.href = "debug.html") },
  { label: "Undo last patch", run: () => undoLast() },
  { label: "Focus Evolve", run: () => document.getElementById("evolveInput")?.focus() },
  { label: "Focus Chat", run: () => document.getElementById("chatInput")?.focus() },
];

function openCommandPalette() {
  const pal = document.getElementById("commandPalette");
  const input = document.getElementById("cmdInput");
  if (!pal) return;
  pal.style.display = "flex";
  input.value = "";
  renderCmdResults("");
  setTimeout(() => input.focus(), 10);
}
function closeCommandPalette() {
  const pal = document.getElementById("commandPalette");
  if (pal) pal.style.display = "none";
}
function renderCmdResults(q) {
  const box = document.getElementById("cmdResults");
  if (!box) return;
  const qq = (q || "").toLowerCase();
  const items = COMMANDS.filter((c) => !qq || c.label.toLowerCase().includes(qq));
  box.innerHTML = items
    .map((c, i) => `<button class="cmd-item${i === 0 ? " active" : ""}" data-cmd="${i}" type="button">${escapeHtml(c.label)}</button>`)
    .join("");
  box._items = items;
  box.querySelectorAll(".cmd-item").forEach((btn) => {
    btn.onclick = () => {
      const c = items[Number(btn.dataset.cmd)];
      closeCommandPalette();
      c?.run();
    };
  });
}
document.getElementById("cmdInput")?.addEventListener("input", (e) => renderCmdResults(e.target.value));
document.getElementById("cmdInput")?.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeCommandPalette();
  if (e.key === "Enter") {
    const items = document.getElementById("cmdResults")?._items || [];
    if (items[0]) {
      closeCommandPalette();
      items[0].run();
    }
  }
});
document.addEventListener("keydown", (e) => {
  if (e.ctrlKey && (e.key === "k" || e.key === "K")) {
    e.preventDefault();
    openCommandPalette();
  }
  if (e.key === "Escape") closeCommandPalette();
});

// Evolve chips for themes
const evolveChips = document.getElementById("evolveChips");
if (evolveChips && !document.getElementById("chipThemePeach")) {
  const extra = [
    ["Switch to peach theme", "theme peach"],
    ["Enable particles", "particles"],
    ["Enable cursor FX", "cursor"],
    ["Compact UI", "compact"],
  ];
  extra.forEach(([label, key]) => {
    const b = document.createElement("button");
    b.className = "chip";
    b.dataset.prompt = label;
    b.textContent = label;
    if (key === "theme peach") b.id = "chipThemePeach";
    evolveChips.appendChild(b);
  });
}

/* ========== Interactive local terminal ========== */
const termInput = document.getElementById("termInput");
const termHistory = [];
let termHistIdx = -1;
let termCwd = "";

async function refreshTermCwd() {
  try {
    const d = await api("/api/terminal/cwd");
    termCwd = d.cwd || "";
    const p = document.getElementById("termPrompt");
    if (p) p.title = termCwd;
  } catch (_) {}
}
refreshTermCwd();

function appendTerminal(text) {
  const cur = terminal.textContent || "";
  setTerminal((cur.endsWith("\n") || !cur ? cur : cur + "\n") + text);
}

async function runTerminalCommand(cmd) {
  const line = (cmd || "").trim();
  if (!line) return;
  termHistory.push(line);
  termHistIdx = termHistory.length;
  appendTerminal(`$ ${line}`);
  if (termInput) termInput.value = "";
  setStatus("Shell…");
  try {
    const data = await api("/api/terminal/run", {
      method: "POST",
      body: JSON.stringify({ command: line, cwd: termCwd || "" }),
    });
    const out = (data.output || "").replace(/\r\n/g, "\n");
    appendTerminal(out);
    if (data.exit_code !== 0) appendTerminal(`[exit ${data.exit_code}]`);
    // track cd on Windows/unix heuristically
    if (/^(cd|chdir)\s+/i.test(line) && data.ok) {
      await refreshTermCwd();
    }
    setStatus(data.ok ? "Ready" : "Shell error");
  } catch (err) {
    appendTerminal(`✗ terminal offline: ${err.message}\n  Is the backend running?`);
    setStatus("Offline");
  }
}

if (termInput) {
  termInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      runTerminalCommand(termInput.value);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      if (!termHistory.length) return;
      termHistIdx = Math.max(0, termHistIdx - 1);
      termInput.value = termHistory[termHistIdx] || "";
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      termHistIdx = Math.min(termHistory.length, termHistIdx + 1);
      termInput.value = termHistIdx >= termHistory.length ? "" : termHistory[termHistIdx];
    }
  });
}

// Click terminal panel focuses input
document.getElementById("terminalPanel")?.addEventListener("click", () => {
  termInput?.focus();
});

document.getElementById("termClear")?.addEventListener("click", (e) => {
  e.stopPropagation();
  setTerminal("$ ");
});

// Add to command palette if present
if (typeof COMMANDS !== "undefined") {
  COMMANDS.push({
    label: "Focus terminal",
    run: () => termInput?.focus(),
  });
}

/* ========== Live editor tabs ========== */
function renderTabs() {
  const bar = document.getElementById("editorTabs");
  if (!bar) return;
  const addBtn = document.getElementById("tabAdd");
  bar.querySelectorAll(".tab[data-tab-path]").forEach((t) => t.remove());
  if (currentPath && !(currentPath in fileBuffers)) {
    fileBuffers[currentPath] = editor.value;
  }
  // Show open tabs: prefer files already in buffers, current first
  const paths = Object.keys(fileBuffers);
  if (!paths.includes(currentPath) && currentPath) paths.unshift(currentPath);
  const ordered = paths.length ? paths : [currentPath || "untitled.py"];
  ordered.forEach((path) => {
    const tab = document.createElement("div");
    tab.className = "tab" + (path === currentPath ? " active" : "");
    tab.dataset.tabPath = path;
    tab.style.cursor = "pointer";
    const name = (path || "untitled").split("/").pop();
    tab.innerHTML = `${escapeHtml(name)} <span class="tab-close" title="Close">×</span>`;
    tab.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      if (e.target.classList.contains("tab-close")) {
        closeTab(path);
        return;
      }
      switchTab(path);
    });
    if (addBtn) bar.insertBefore(tab, addBtn);
    else bar.appendChild(tab);
  });
}

function switchTab(path) {
  if (!path) return;
  // Always save current buffer first
  fileBuffers[currentPath] = editor.value;
  if (!(path in fileBuffers)) fileBuffers[path] = "";
  currentPath = path;
  editor.value = fileBuffers[path] || "";
  updateLines();
  syncStatus();
  document.querySelectorAll(".file").forEach((f) => {
    f.classList.toggle("active-file", f.dataset.path === path);
  });
  renderTabs();
  setStatus(`Tab: ${path}`);
  if (typeof playRefreshAnimation === "function") playRefreshAnimation(path.split("/").pop());
}

function closeTab(path) {
  const keys = Object.keys(fileBuffers);
  if (keys.length <= 1) {
    toast("Keep at least one tab", "info");
    return;
  }
  delete fileBuffers[path];
  if (currentPath === path) {
    const next = Object.keys(fileBuffers)[0];
    currentPath = next;
    editor.value = fileBuffers[next] || "";
    updateLines();
    syncStatus();
  }
  renderTabs();
  renderFileTree(Object.keys(fileBuffers));
}

function openInTab(path, content) {
  if (content != null) fileBuffers[path] = content;
  else if (!(path in fileBuffers)) fileBuffers[path] = "";
  switchTab(path);
  renderFileTree(Object.keys(fileBuffers));
}

// Hook existing openPath to keep tabs in sync
const _openPath = openPath;
openPath = function (path) {
  fileBuffers[currentPath] = editor.value;
  if (!(path in fileBuffers)) fileBuffers[path] = fileBuffers[path] || "";
  _openPath(path);
  renderTabs();
};

document.getElementById("tabAdd")?.addEventListener("click", () => {
  const name = prompt("New file name", "untitled.py");
  if (!name) return;
  const path = name.includes("/") ? name : name;
  openInTab(path, "");
  toast(`Opened ${path}`, "success");
});

// Initial tabs
renderTabs();



async function refreshQuota(){
  try{
    const data=await api("/api/quota"), el=document.getElementById("quotaDisplay"); if(!el)return;
    let html="";
    if(data.local_lanes?.length) html+=data.local_lanes.map(l=>'<div class="quota-row"><span>'+escapeHtml(l.name)+'</span><span class="quota-inf">∞</span></div>').join("");
    if(data.hf_remaining!=null&&data.hf_limit!=null){const pct=data.hf_percent_remaining??0,cls=pct<20?"quota-warn":"quota-ok";html+='<div class="quota-row"><span>HF quota</span><span class="'+cls+'">'+data.hf_remaining+'/'+data.hf_limit+'</span></div>';if(data.hf_seconds_until_reset)html+='<div class="quota-row muted">Resets in '+Math.round(data.hf_seconds_until_reset)+'s</div>';}
    else html+='<div class="quota-row muted">HF quota: not recorded yet</div>';
    el.innerHTML=html;
  }catch(_){}
}
async function validateAndLoadOllama(){
  const url=document.getElementById("ollamaUrlInput")?.value?.trim();if(!url){toast("Enter a URL","info");return;}
  try{const data=await api("/api/ollama/validate",{method:"POST",body:JSON.stringify({url})});renderOllamaModels(data);toast(data.model_count+" models loaded","success");}catch(err){toast("Validation failed: "+err.message,"error");}
}
function renderOllamaModels(data){
  const box=document.getElementById("ollamaModelList");if(!box)return;box.innerHTML="";const recommended=data.recommended?.name||"";
  (data.models||[]).forEach(m=>{const row=document.createElement("button");row.className="hf-item";row.innerHTML='<span class="hf-id">'+escapeHtml(m.name)+(m.name===recommended?" ★":"")+'</span><span class="hf-meta">'+escapeHtml(m.parameter_size||"?")+" · "+escapeHtml(m.quantization||"?")+" · score "+m.score+'</span>';row.onclick=()=>setPrimaryOllama(data.url,m.name);box.appendChild(row);});
}
async function setPrimaryOllama(url,model){try{await api("/api/ollama/primary",{method:"POST",body:JSON.stringify({url,model})});toast("Primary set: "+model,"success");refreshQuota();}catch(err){toast("Could not set primary","error");}}

/* ========== Vision / image analysis ========== */
let visionDataUrl = "";

function setVisionPreview(dataUrl) {
  visionDataUrl = dataUrl;
  const prev = document.getElementById("visionPreview");
  const img = document.getElementById("visionImg");
  if (img) img.src = dataUrl;
  if (prev) prev.style.display = "block";
}

async function analyzeVision() {
  if (!visionDataUrl) {
    toast("Drop or paste an image first", "info");
    return;
  }
  playRefreshAnimation("Analyzing image…");
  setStatus("Vision…");
  try {
    const data = await api("/api/ai/vision", {
      method: "POST",
      body: JSON.stringify({
        image_base64: visionDataUrl,
        prompt: document.getElementById("visionPrompt")?.value || "",
        model: modelSelect.value,
      }),
    });
    const box = document.getElementById("visionResult");
    let html = escapeHtml(data.content || "").replace(/\n/g, "<br>").replace(/\n/g, "<br>");
    if (data.actions && data.actions.length) {
      html += '<div style="margin-top:8px;font-weight:650">Apply live</div>';
      data.actions.forEach((a, i) => {
        html += '<div class="patch"><div class="patch-head"><span class="patch-title">' + escapeHtml(a.title || "") + '</span></div>' +
          '<div class="muted">' + escapeHtml(a.description || "") + '</div>' +
          '<div class="patch-actions"><button class="apply" data-vision-action="' + i + '">Apply</button></div></div>';
      });
    }
    if (box) {
      box.innerHTML = html;
      box.onclick = (e) => {
        const btn = e.target.closest("[data-vision-action]");
        if (!btn) return;
        const a = data.actions[Number(btn.dataset.visionAction)];
        if (a && typeof applyPatch === "function") applyPatch(a, btn.closest(".patch"));
      };
    }
    appendChat("assistant", data.content || "Vision done");
    setTerminal("$ dreamcoder vision\n\n" + (data.content || ""));
    toast(data.actions && data.actions.length ? data.actions.length + " action(s) ready" : "Image analyzed", "success");
    setStatus("Ready");
  } catch (err) {
    toast("Vision failed – is backend up?", "error");
    setStatus("Offline");
  }
}

const visionDrop = document.getElementById("visionDrop");
const visionFile = document.getElementById("visionFile");
visionDrop?.addEventListener("click", () => visionFile?.click());
visionFile?.addEventListener("change", () => {
  const f = visionFile.files?.[0];
  if (!f) return;
  const reader = new FileReader();
  reader.onload = () => {
    setVisionPreview(reader.result);
    toast("Image loaded – click Analyze", "info");
  };
  reader.readAsDataURL(f);
});
["dragenter", "dragover"].forEach((ev) => {
  visionDrop?.addEventListener(ev, (e) => {
    e.preventDefault();
    visionDrop.classList.add("drag-over");
  });
});
visionDrop?.addEventListener("dragleave", () => visionDrop.classList.remove("drag-over"));
visionDrop?.addEventListener("drop", (e) => {
  e.preventDefault();
  visionDrop.classList.remove("drag-over");
  const f = e.dataTransfer.files?.[0];
  if (!f || !f.type.startsWith("image/")) {
    toast("Drop an image file", "info");
    return;
  }
  const reader = new FileReader();
  reader.onload = () => setVisionPreview(reader.result);
  reader.readAsDataURL(f);
});
document.getElementById("visionAnalyzeBtn")?.addEventListener("click", analyzeVision);
document.getElementById("ollamaValidateBtn")?.addEventListener("click", validateAndLoadOllama);

// Paste image anywhere in app
document.addEventListener("paste", (e) => {
  const items = e.clipboardData?.items;
  if (!items) return;
  for (const it of items) {
    if (it.type.startsWith("image/")) {
      const file = it.getAsFile();
      if (!file) continue;
      const reader = new FileReader();
      reader.onload = () => {
        setVisionPreview(reader.result);
        toast("Image pasted – open Image analysis & Analyze", "success");
        document.getElementById("visionCard")?.scrollIntoView({ behavior: "smooth", block: "nearest" });
      };
      reader.readAsDataURL(file);
      break;
    }
  }
});

if (typeof COMMANDS !== "undefined") {
  COMMANDS.push({ label: "Analyze last image", run: () => analyzeVision() });
  COMMANDS.push({ label: "New editor tab", run: () => document.getElementById("tabAdd")?.click() });
}


/* Final: ensure theme buttons use full THEMES map (overrides early 3-theme handler) */
document.querySelectorAll(".theme[data-theme]").forEach((btn) => {
  btn.onclick = () => {
    if (typeof applyTheme === "function") applyTheme(btn.dataset.theme);
  };
});



/* ========== FINAL BOOT (tabs + themes must work) ========== */
(function finalBoot() {
  function showAiPanel(id) {
    id = id || "panel-chat";
    document.querySelectorAll(".ai-subtab").forEach((b) => {
      b.classList.toggle("active", b.dataset.panel === id);
    });
    document.querySelectorAll("[data-ai-panel]").forEach((el) => {
      if (el.getAttribute("data-ai-panel") === id) {
        el.classList.add("ai-panel-show");
        if (el.style) el.style.display = "";
      } else {
        el.classList.remove("ai-panel-show");
      }
    });
    try { localStorage.setItem("dc_ai_panel", id); } catch (_) {}
  }
  window.showAiPanel = showAiPanel;

  const tabs = document.getElementById("aiSubTabs");
  if (tabs) {
    tabs.onclick = (e) => {
      const btn = e.target.closest(".ai-subtab");
      if (!btn) return;
      showAiPanel(btn.dataset.panel);
    };
  }

  // Themes
  document.querySelectorAll(".theme[data-theme]").forEach((btn) => {
    btn.onclick = () => {
      const name = btn.dataset.theme;
      if (typeof applyTheme === "function") applyTheme(name);
      else {
        document.querySelectorAll(".theme").forEach((x) => x.classList.remove("active-theme"));
        btn.classList.add("active-theme");
      }
    };
  });

  // Start on chat (or saved)
  let start = "panel-chat";
  try { start = localStorage.getItem("dc_ai_panel") || "panel-chat"; } catch (_) {}
  showAiPanel(start);

  // Status
  const st = document.getElementById("status");
  if (st && (!st.textContent || st.textContent === "Ready")) {
    /* keep */
  }
  loadAvailableModels().catch(() => {});
  refreshQuota();
  setInterval(refreshQuota,30000);
  console.log("DreamCoder UI ready");
})();


/* Production control center: GitHub, Git, terminal, recovery and settings. */
(function productionUI(){
  const style=document.createElement("style"); style.textContent=".dc-prod{position:fixed;right:16px;bottom:48px;width:min(620px,94vw);max-height:72vh;overflow:auto;z-index:10000;background:#111722;border:1px solid var(--border);border-radius:12px;box-shadow:0 20px 70px #0008;padding:12px}.dc-tabs{display:flex;gap:5px;flex-wrap:wrap;margin-bottom:10px}.dc-tabs button,.dc-prod button{border:1px solid var(--border);background:#0d1118;color:var(--text);border-radius:6px;padding:6px 9px;cursor:pointer}.dc-tabs button.active{border-color:var(--accent)}.dc-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px}.dc-grid input,.dc-prod select{width:100%;box-sizing:border-box;background:#0b1018;color:var(--text);border:1px solid var(--border);padding:7px;border-radius:6px}.dc-row{display:flex;gap:6px;margin:6px 0;flex-wrap:wrap}.dc-log{background:#080b10;padding:8px;border-radius:7px;white-space:pre-wrap;font:10px ui-monospace;max-height:220px;overflow:auto}.dc-ok{color:var(--accent2)}.dc-err{color:var(--danger)}";document.head.appendChild(style);
  const b=document.createElement("button");b.className="chip";b.textContent="⚙ Production";b.style.position="fixed";b.style.right="12px";b.style.bottom="12px";b.style.zIndex="9999";document.body.appendChild(b);
  const box=document.createElement("div");box.className="dc-prod";box.hidden=true;document.body.appendChild(box);
  const tabs=["GitHub","Git","Terminal","Settings","Recovery","Diagnostics"];
  function shell(tab){
    box.innerHTML='<div class="dc-tabs">'+tabs.map(x=>'<button data-tab="'+x+'">'+x+'</button>').join("")+'<button data-close>×</button></div><div id="dc-body"></div>';
    box.querySelectorAll("[data-tab]").forEach(x=>x.onclick=()=>render(x.dataset.tab));
    box.querySelector("[data-close]").onclick=()=>box.hidden=true; render(tab);
  }
  async function post(path,body){return api(path,{method:"POST",body:JSON.stringify(body||{})})}
  async function render(tab){
    const body=box.querySelector("#dc-body"); body.innerHTML="<div class=muted>Loading…</div>";
    if(tab==="GitHub"){
      const me=await api("/api/github/me").catch(()=>({connected:false})); const cfg=await api("/api/github/oauth/config").catch(()=>({configured:false}));
      const repos=me.connected?await api("/api/github/repositories").catch(()=>({repositories:[]})):{repositories:[]};
      body.innerHTML='<h3>GitHub connection</h3><div class="muted">'+(me.connected?"Connected as "+escapeHtml(me.login):"Not connected")+'</div><div class=dc-row>'+(me.connected?'<button id=dcDisconnect>Disconnect</button>':'<button id=dcConnect>Connect GitHub</button>')+'</div><div class=dc-grid><select id=dcRepo>'+repos.repositories.map(x=>'<option value="'+escapeHtml(x.full_name)+'">'+escapeHtml(x.full_name)+'</option>').join("")+'</select><input id=dcBranch placeholder="branch (main)"/></div><div class=dc-row><button id=dcRepoSet>Use repository</button><button id=dcRefreshRepos>Refresh repositories</button></div><div id=dcGhLog class=dc-log></div>';
      body.querySelector("#dcConnect")?.addEventListener("click",()=>{ if(!cfg.configured){toast("Set DREAMCODER_GITHUB_CLIENT_ID/SECRET and OAUTH_STATE_SECRET first","error");return;} window.open(API_BASE+"/api/github/oauth/start","_blank","width=900,height=800"); setTimeout(()=>render("GitHub"),3000);});
      body.querySelector("#dcDisconnect")?.addEventListener("click",async()=>{await post("/api/github/disconnect");render("GitHub")});
      body.querySelector("#dcRepoSet")?.addEventListener("click",async()=>{const d=await post("/api/github/select-repository",{repo:body.querySelector("#dcRepo").value,branch:body.querySelector("#dcBranch").value||"main"});body.querySelector("#dcGhLog").textContent=JSON.stringify(d,null,2);refreshGithubSyncStatus()});
      body.querySelector("#dcRefreshRepos")?.addEventListener("click",()=>render("GitHub"));
      return;
    }
    if(tab==="Git"){
      const s=await api("/api/git/workflow/status").catch(e=>({error:String(e)})); const br=await api("/api/git/workflow/branches").catch(e=>({error:String(e)}));
      const files=await api("/api/git/workflow/files").catch(()=>({files:[]})); body.innerHTML='<h3>Git workflow</h3><div class=dc-row><button data-git=fetch>Fetch</button><button data-git=pull>Pull</button><button data-git=push>Push</button><button data-git=stash>Stash</button><button data-git=merge>Merge</button></div><div class=dc-grid><input id=dcBranchName placeholder="new/switch branch"/><button data-git=branch>Create & switch branch</button><input id=dcCommit placeholder="commit message"/><button data-git=commit>Commit staged</button></div><div class=dc-log id=dcGitFiles>'+((files.files||[]).map(f=>'<div><button data-stage="'+escapeHtml(f.path)+'">'+(f.index!==" "?"Unstage":"Stage")+'</button> <code>'+escapeHtml(f.path)+'</code></div>').join("")||"Working tree clean")+'</div><pre class=dc-log>'+escapeHtml(JSON.stringify({status:s,branches:br},null,2))+'</pre>';
