"use strict";

const $ = (id) => document.getElementById(id);
const state = { history: [], selected: new Set(), controller: null };
let allDocs = [];

// ---------- helpers ----------

async function api(path, options) {
  const res = await fetch(path, options);
  if (!res.ok) {
    let msg = res.statusText;
    try { msg = (await res.json()).detail || msg; } catch {}
    throw new Error(msg);
  }
  return res;
}

// Parse a Server-Sent Events stream coming from a fetch() response.
async function* readSSE(response) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop();                       // keep the incomplete tail
    for (const part of parts) {
      let event = "message";
      let data = "";
      for (const line of part.split("\n")) {
        if (line.startsWith("event: ")) event = line.slice(7);
        else if (line.startsWith("data: ")) data += line.slice(6);
      }
      if (data) yield { event, data: JSON.parse(data) };
    }
  }
}

const scrollDown = () => {
  const box = $("messages");
  box.scrollTop = box.scrollHeight;
};

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

// Auto-grow textarea
function autoGrow(textarea) {
  textarea.style.height = "auto";
  textarea.style.height = Math.min(textarea.scrollHeight, 160) + "px";
}

// ---------- documents sidebar ----------

async function loadDocs() {
  allDocs = await (await api("/api/docs")).json();
  state.selected = new Set([...state.selected].filter((n) => allDocs.some((d) => d.name === n)));
  renderDocs();
}

function renderDocs() {
  const list = $("doc-list");
  list.textContent = "";
  if (!allDocs.length) {
    const li = el("li");
    li.style.cssText = "color: var(--fg-dim); font-size: 12px; padding: 8px 0;";
    li.textContent = "No documents yet. Upload a PDF.";
    list.append(li);
    return;
  }
  for (const d of allDocs) {
    const li = el("li");

    const label = el("label");
    const cb = el("input");
    cb.type = "checkbox";
    cb.checked = state.selected.has(d.name);
    cb.addEventListener("change", () =>
      cb.checked ? state.selected.add(d.name) : state.selected.delete(d.name)
    );
    const nameSpan = el("span", "doc-name", d.name);
    const countSpan = el("span", "doc-count", `${d.chunks}`);
    label.append(cb, nameSpan, countSpan);

    const del = el("button", "btn-delete");
    del.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>';
    del.title = `Delete ${d.name}`;
    del.addEventListener("click", () => deleteDoc(d.name));

    li.append(label, del);
    list.append(li);
  }
}

async function deleteDoc(name) {
  if (!confirm(`Delete "${name}" and all its indexed chunks?`)) return;
  try {
    await api(`/api/docs/${encodeURIComponent(name)}`, { method: "DELETE" });
    await loadDocs();
  } catch (err) {
    $("upload-status").textContent = err.message;
  }
}

$("file-input").addEventListener("change", async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  const status = $("upload-status");
  const label = $("upload-label");
  status.textContent = "Uploading and indexing…";
  label.style.pointerEvents = "none";
  label.style.opacity = ".5";

  const form = new FormData();
  form.append("file", file);
  try {
    const data = await (await api("/api/upload", { method: "POST", body: form })).json();
    status.textContent = `✓ Indexed ${data.name} (${data.chunks} chunks)`;
    await loadDocs();
  } catch (err) {
    status.textContent = `✗ ${err.message}`;
  }
  label.style.pointerEvents = "";
  label.style.opacity = "";
  e.target.value = "";
});

// ---------- sidebar toggle (mobile) ----------

$("sidebar-toggle").addEventListener("click", () => {
  $("sidebar").classList.toggle("open");
});

// Close sidebar when clicking outside on mobile
document.addEventListener("click", (e) => {
  const sidebar = $("sidebar");
  const toggle = $("sidebar-toggle");
  if (
    sidebar.classList.contains("open") &&
    !sidebar.contains(e.target) &&
    !toggle.contains(e.target)
  ) {
    sidebar.classList.remove("open");
  }
});

// ---------- get selected mode ----------

function getMode() {
  const checked = document.querySelector('input[name="mode"]:checked');
  return checked ? checked.value : "hybrid_rerank";
}

// ---------- chat rendering ----------

function hideWelcome() {
  const w = $("welcome");
  if (w) w.remove();
}

function addMessage(role, text = "") {
  hideWelcome();
  const wrap = el("div", `msg ${role}`);
  const body = el("div", "body", text);
  wrap.append(body);
  $("messages").append(wrap);
  scrollDown();
  return { wrap, body };
}

// Turn "[1]" markers into clickable buttons, safely (no innerHTML).
function renderWithCitations(body, text, sources) {
  body.textContent = "";
  for (const part of text.split(/(\[\d+\])/g)) {
    const m = part.match(/^\[(\d+)\]$/);
    const idx = m ? Number(m[1]) : 0;
    if (m && sources[idx - 1]) {
      const s = sources[idx - 1];
      const btn = el("button", "cite", part);
      btn.title = `${s.source}, p. ${s.page}`;
      btn.addEventListener("click", () => highlightSource(body.closest(".msg"), idx));
      body.append(btn);
    } else if (part) {
      body.append(document.createTextNode(part));
    }
  }
}

function renderSources(wrap, sources) {
  if (!sources.length) return;
  const details = el("details", "sources");
  details.append(el("summary", "", `${sources.length} source${sources.length > 1 ? "s" : ""} retrieved`));
  const ol = el("ol");
  sources.forEach((s, i) => {
    const li = el("li");
    li.dataset.index = String(i + 1);

    const meta = el("span", "source-meta", `${s.source}, p. ${s.page}`);
    const score = el("span", "source-score", `score ${s.score}`);
    meta.append(score);
    li.append(meta);
    li.append(el("pre", "", s.text));
    ol.append(li);
  });
  details.append(ol);
  wrap.append(details);
}

function highlightSource(wrap, idx) {
  const details = wrap.querySelector("details.sources");
  if (!details) return;
  details.open = true;
  const li = details.querySelector(`li[data-index="${idx}"]`);
  if (!li) return;
  li.scrollIntoView({ block: "nearest", behavior: "smooth" });
  li.classList.add("hl");
  setTimeout(() => li.classList.remove("hl"), 2000);
}

function addFeedback(wrap, question, answer, latencyMs) {
  const bar = el("div", "feedback");

  for (const [emoji, label, rating] of [["👍", "Helpful", 1], ["👎", "Not helpful", -1]]) {
    const b = el("button", "feedback-btn", emoji);
    b.title = label;
    b.addEventListener("click", async () => {
      try {
        await api("/api/feedback", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question, answer, rating, mode: getMode() }),
        });
        b.classList.add("active");
        // Disable both buttons after clicking
        bar.querySelectorAll(".feedback-btn").forEach((btn) => { btn.disabled = true; });
        const thanks = el("span", "feedback-thanks", "Thanks!");
        bar.append(thanks);
      } catch (err) {
        const errSpan = el("span", "feedback-thanks", err.message);
        bar.append(errSpan);
      }
    });
    bar.append(b);
  }

  if (latencyMs) {
    bar.append(el("span", "latency", `${(latencyMs / 1000).toFixed(1)}s`));
  }

  wrap.append(bar);
}

function setBusy(busy) {
  $("send-btn").disabled = busy;
  $("stop-btn").hidden = !busy;
  $("send-btn").style.display = busy ? "none" : "";
}

// ---------- sending a question ----------

async function send(question) {
  addMessage("user", question);
  const { wrap, body } = addMessage("assistant");
  body.classList.add("pending");

  let text = "";
  let sources = [];
  let stopped = false;
  let failed = false;
  let latencyMs = 0;

  setBusy(true);
  state.controller = new AbortController();

  try {
    const res = await api("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal: state.controller.signal,
      body: JSON.stringify({
        question,
        history: state.history.slice(-6),
        sources: [...state.selected],
        mode: getMode(),
      }),
    });

    for await (const { event, data } of readSSE(res)) {
      if (event === "rewrite" && data !== question) {
        wrap.prepend(el("div", "rewrite", `Searched for: ${data}`));
      } else if (event === "sources") {
        sources = data;
      } else if (event === "token") {
        text += data;
        body.classList.remove("pending");
        body.textContent = text;
        scrollDown();
      } else if (event === "error") {
        failed = true;
        body.classList.remove("pending");
        body.textContent = data;
      } else if (event === "done") {
        latencyMs = data.latency_ms || 0;
      }
    }
  } catch (err) {
    body.classList.remove("pending");
    if (err.name === "AbortError") {
      stopped = true;
    } else {
      failed = true;
      body.textContent = err.message;
    }
  } finally {
    setBusy(false);
    state.controller = null;
  }

  if (stopped) wrap.append(el("div", "stopped", "⏹ Generation stopped."));
  if (failed || !text) return;

  renderWithCitations(body, text, sources);
  renderSources(wrap, sources);
  addFeedback(wrap, question, text, latencyMs);
  state.history.push({ role: "user", content: question }, { role: "assistant", content: text });
  scrollDown();
}

// ---------- events ----------

$("chat-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const q = $("question").value.trim();
  if (!q || state.controller) return;
  $("question").value = "";
  autoGrow($("question"));
  send(q);
});

$("question").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    $("chat-form").requestSubmit();
  }
});

$("question").addEventListener("input", () => autoGrow($("question")));

$("stop-btn").addEventListener("click", () => state.controller && state.controller.abort());

$("clear-btn").addEventListener("click", () => {
  state.history = [];
  $("messages").textContent = "";
  // Re-add welcome screen
  const welcome = el("div", "welcome");
  welcome.id = "welcome";
  welcome.innerHTML = `
    <div class="welcome-icon">
      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="url(#welcome-grad)" stroke-width="1.5"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/><defs><linearGradient id="welcome-grad" x1="3" y1="3" x2="21" y2="19"><stop stop-color="#6366f1"/><stop offset="1" stop-color="#a855f7"/></linearGradient></defs></svg>
    </div>
    <h2>Welcome to CampusGPT</h2>
    <p>Upload a college document and ask questions. Answers are cited with page numbers.</p>
    <div class="welcome-chips">
      <button class="chip" data-q="What is the minimum attendance required?">📋 Attendance policy</button>
      <button class="chip" data-q="What are the hostel rules?">🏠 Hostel rules</button>
      <button class="chip" data-q="How do I apply for a fee refund?">💰 Fee refund process</button>
    </div>
  `;
  $("messages").append(welcome);
  bindChips();
});

// ---------- welcome chips ----------

function bindChips() {
  document.querySelectorAll(".chip[data-q]").forEach((chip) => {
    chip.addEventListener("click", () => {
      const q = chip.dataset.q;
      if (q && !state.controller) send(q);
    });
  });
}

// ---------- init ----------

loadDocs().catch((err) => { $("upload-status").textContent = err.message; });
bindChips();
