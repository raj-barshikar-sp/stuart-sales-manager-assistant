const taskMenu = document.getElementById("task-menu");
const chatHistory = document.getElementById("chat-history");
const canvas = document.getElementById("canvas");
const form = document.getElementById("composer");
const prompt = document.getElementById("prompt");
const send = document.getElementById("send");
const stop = document.getElementById("stop");
const newChat = document.getElementById("new-chat");
const attachInput = document.getElementById("attach");
const attachBtn = document.getElementById("attach-btn");
const attachChips = document.getElementById("attach-chips");
const filterGeos = document.getElementById("filter-geos");
const filterReps = document.getElementById("filter-reps");
const filterHorizon = document.getElementById("filter-horizon");
const filterOpps = document.getElementById("filter-opps");
const filterClear = document.getElementById("filter-clear");
const emptyReps = document.getElementById("empty-reps");
const emptyOpps = document.getElementById("empty-opps");
const filterHint = document.getElementById("filter-hint");
const workspaceEl = document.getElementById("workspace");
const toggleLeft = document.getElementById("toggle-left");
const toggleRight = document.getElementById("toggle-right");
const queryNav = document.getElementById("query-nav");
const dictateBtn = document.getElementById("dictate");
const voiceCallBtn = document.getElementById("voice-call-btn");
const voiceCall = document.getElementById("voice-call");
const voiceCallStatus = document.getElementById("voice-call-status");
const voiceCallCaption = document.getElementById("voice-call-caption");
const hangup = document.getElementById("hangup");
const SpeechCtor = window.SpeechRecognition || window.webkitSpeechRecognition;

const WORKSPACE_KEY = "gru-workspace-open";

function showWorkspace({ focus } = { focus: true }) {
  document.getElementById("landing").hidden = true;
  workspaceEl.hidden = false;
  document.body.classList.add("in-workspace");
  try {
    localStorage.setItem(WORKSPACE_KEY, "1");
  } catch {
    /* private mode */
  }
  resizePrompt();
  if (focus) prompt.focus();
}

document.getElementById("open-workspace").addEventListener("click", () => {
  showWorkspace();
});

// Restore before first paint so a reload does not flash the landing page.
try {
  if (localStorage.getItem(WORKSPACE_KEY) === "1") showWorkspace({ focus: false });
} catch {
  /* private mode */
}

const ALLOWED_ATTACH = new Set([".pdf", ".csv", ".txt", ".xlsx", ".xls", ".docx", ".doc"]);
const MAX_ATTACH = 5;
const MAX_ATTACH_BYTES = 8 * 1024 * 1024;

let sessionId = "";
let workspace = null;
let activeTask = "";
let abortController = null;
let requestGen = 0;
let chats = [];
let activeChatId = "";
let attachments = [];
const CHATS_KEY = "gru-chats";
const CHATS_LIMIT = 40;

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function selectedValues(name) {
  return [...document.querySelectorAll(`input[name="${name}"]:checked`)].map((node) => node.value);
}

function currentFilters() {
  const scopes = findTask(activeTask)?.scopes;
  const enabled = (name) => !Array.isArray(scopes) || scopes.includes(name);
  return {
    geos: enabled("geos") ? selectedValues("geo") : [],
    boats: enabled("boats") ? selectedValues("boat") : [],
    opps: enabled("opps") ? selectedValues("opp") : [],
    report_types: enabled("report_types") ? selectedValues("report") : [],
  };
}

function findTask(taskId) {
  for (const group of workspace?.tasks || []) {
    const hit = group.items?.find((item) => item.id === taskId);
    if (hit) return hit;
  }
  return null;
}

function composeDraft(taskId) {
  const task = findTask(taskId);
  if (!task) return "";
  const filters = currentFilters();
  const opps = workspace?.filters?.opps || [];
  const oppMap = Object.fromEntries(opps.map((item) => [item.id, item]));
  let account = "";
  for (const id of filters.opps) {
    if (oppMap[id]) {
      account = oppMap[id].account;
      break;
    }
  }
  if (!account) {
    for (const geo of filters.geos) {
      const hit = opps.find((item) => item.territory === geo);
      if (hit) {
        account = hit.account;
        break;
      }
    }
  }
  if (!account) {
    for (const boat of filters.boats) {
      const hit = opps.find((item) => item.owner === boat);
      if (hit) {
        account = hit.account;
        break;
      }
    }
  }
  let territory = filters.geos[0] || "";
  if (!territory && account) {
    territory = opps.find((item) => item.account === account)?.territory || "";
  }
  territory = territory || "central";
  let text = task.default_prompt || "";
  if (account && task.scoped_prompt) {
    text = task.scoped_prompt.replaceAll("{account}", account).replaceAll("{territory}", territory);
  } else if (filters.geos.length && task.scoped_prompt) {
    text = task.scoped_prompt.replaceAll("{account}", account || territory).replaceAll("{territory}", territory);
  }
  const notes = [];
  if (filters.geos.length) notes.push("Territory: " + filters.geos.join(", "));
  if (filters.boats.length) notes.push("Reps: " + filters.boats.join(", "));
  if (filters.opps.length) {
    const labels = filters.opps.map((id) => oppMap[id]?.label).filter(Boolean);
    if (labels.length) notes.push("Deals: " + labels.join("; "));
  }
  if (filters.report_types.length) {
    const labels = (workspace?.filters?.report_types || [])
      .filter((item) => filters.report_types.includes(item.id))
      .map((item) => item.label);
    if (labels.length) notes.push("Horizon: " + labels.join(", "));
  }
  if (notes.length) text += "\n\nWorking filters:\n" + notes.map((note) => `- ${note}`).join("\n");
  return text;
}

function fillComposer(taskId) {
  activeTask = taskId;
  prompt.value = composeDraft(taskId);
  resizePrompt();
  prompt.focus();
}

const CLIPBOARD_ICON =
  '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="8" y="8" width="12" height="12" rx="2"></rect><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"></path></svg>';
const CHECK_ICON =
  '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12.5 9.5 17 19 7.5"></path></svg>';

function addCopy(parent, text, label) {
  const button = el("button", "copy");
  button.type = "button";
  button.dataset.copy = text;
  button.setAttribute("aria-label", label || "Copy");
  button.title = label || "Copy";
  button.innerHTML = CLIPBOARD_ICON;
  parent.append(button);
}

canvas.addEventListener("click", async (event) => {
  const button = event.target.closest("button.copy");
  if (!button || !canvas.contains(button)) return;
  await navigator.clipboard.writeText(button.dataset.copy || "");
  button.classList.remove("copied");
  void button.offsetWidth;
  button.classList.add("copied");
  button.innerHTML = CHECK_ICON;
  const prior = button.getAttribute("aria-label");
  button.setAttribute("aria-label", "Copied");
  clearTimeout(button._copyTimer);
  button._copyTimer = setTimeout(() => {
    button.classList.remove("copied");
    button.innerHTML = CLIPBOARD_ICON;
    button.setAttribute("aria-label", prior || "Copy");
  }, 1200);
});

const INLINE_RE = /\*\*([^*]+)\*\*|`([^`]+)`/g;
const HEADING_RE = /^(#{1,6})\s+(.+)$/;
const BULLET_RE = /^\s*[-*]\s+(.+)$/;
const STEP_RE = /^\s*(\d+)[.)]\s+(.+)$/;
const RULE_RE = /^(-{3,}|\*{3,}|_{3,})$/;

function inlineMarkdown(text) {
  const frag = document.createDocumentFragment();
  let cursor = 0;
  for (const match of text.matchAll(INLINE_RE)) {
    if (match.index > cursor) {
      frag.append(document.createTextNode(text.slice(cursor, match.index)));
    }
    frag.append(match[1] ? el("strong", "", match[1]) : el("code", "", match[2]));
    cursor = match.index + match[0].length;
  }
  if (cursor < text.length) frag.append(document.createTextNode(text.slice(cursor)));
  return frag;
}

function line(tag, className, text) {
  const node = el(tag, className);
  node.append(inlineMarkdown(text));
  return node;
}

function nested(raw) {
  return raw.length - raw.trimStart().length >= 2 ? " draft-indent" : "";
}

function formatDraft(text) {
  const frag = document.createDocumentFragment();
  let fence = null;
  const closeFence = () => {
    frag.append(el("pre", "draft-code", fence.join("\n")));
    fence = null;
  };
  for (const raw of text.split("\n")) {
    const trimmed = raw.trim();
    if (trimmed.startsWith("```")) {
      if (fence) closeFence();
      else fence = [];
      continue;
    }
    if (fence) {
      fence.push(raw);
      continue;
    }
    const heading = trimmed.match(HEADING_RE);
    const bullet = raw.match(BULLET_RE);
    const step = raw.match(STEP_RE);
    if (!trimmed) {
      frag.append(el("div", "draft-gap"));
    } else if (heading) {
      const tag = heading[1].length <= 2 ? "draft-head" : "draft-subhead";
      frag.append(line("h4", tag, heading[2]));
    } else if (RULE_RE.test(trimmed)) {
      frag.append(el("hr", "draft-rule"));
    } else if (bullet) {
      frag.append(line("div", `draft-bullet${nested(raw)}`, bullet[1]));
    } else if (step) {
      const row = line("div", `draft-step${nested(raw)}`, step[2]);
      row.dataset.marker = `${step[1]}.`;
      frag.append(row);
    } else {
      frag.append(line("div", `draft-line${nested(raw)}`, trimmed));
    }
  }
  if (fence) closeFence();
  return frag;
}

function addReplyCopy(parent, text) {
  if (!text) return;
  const tools = el("div", "reply-tools");
  addCopy(tools, text, "Copy response");
  parent.append(tools);
}

function briefingText(payload) {
  const chunks = [];
  if (payload.summary) chunks.push("Summary", payload.summary);
  if (payload.insights?.length) {
    chunks.push("", "Key insights", ...payload.insights.map((item) => `- ${item}`));
  }
  if (payload.actions?.length) {
    chunks.push("", "Recommended actions");
    payload.actions.forEach((action, index) => {
      chunks.push(`${index + 1}. ${action.action}`);
      const bits = [
        action.owner && `owner: ${action.owner}`,
        action.due && `when: ${action.due}`,
      ]
        .filter(Boolean)
        .join(" · ");
      if (bits) chunks.push(bits);
      if (action.paste) chunks.push(action.paste);
    });
  }
  if (payload.artifacts?.length) {
    chunks.push("", "Artifacts");
    for (const artifact of payload.artifacts) {
      if (artifact.title) chunks.push(artifact.title);
      if (artifact.body) chunks.push(artifact.body);
    }
  }
  return chunks.join("\n").trim();
}

function renderBriefing(payload) {
  const wrap = el("div", "briefing");
  const summary = el("article", "card");
  summary.append(el("h3", "", "Summary"));
  summary.append(el("p", "", payload.summary));
  wrap.append(summary);

  if (payload.insights?.length) {
    const insights = el("article", "card");
    insights.append(el("h3", "", "Key insights"));
    const list = el("ul");
    for (const item of payload.insights) list.append(line("li", "", item));
    insights.append(list);
    wrap.append(insights);
  }

  if (payload.actions?.length) {
    const actions = el("article", "card");
    actions.append(el("h3", "", "Recommended actions"));
    for (const action of payload.actions) {
      const row = el("div", "action");
      row.append(line("p", "", action.action));
      const genericOwner = /^(you|sales manager|manager)$/i.test((action.owner || "").trim());
      const bits = [
        action.owner && !genericOwner && `owner: ${action.owner}`,
        action.due && `when: ${action.due}`,
      ]
        .filter(Boolean)
        .join(" · ");
      if (bits) row.append(el("p", "meta", bits));
      if (action.paste) {
        const paste = el("div", "paste");
        paste.append(el("p", "", action.paste));
        addCopy(paste, action.paste, "Copy paste line");
        row.append(paste);
      }
      actions.append(row);
    }
    wrap.append(actions);
  }

  if (payload.artifacts?.length) {
    const artifacts = el("article", "card");
    artifacts.append(el("h3", "", "Artifacts"));
    for (const artifact of payload.artifacts) {
      const block = el("div", "artifact");
      block.append(el("strong", "", artifact.title));
      block.append(el("pre", "", artifact.body));
      addCopy(block, artifact.body, "Copy artifact");
      artifacts.append(block);
    }
    wrap.append(artifacts);
  }
  addReplyCopy(wrap, briefingText(payload));
  return wrap;
}

function placeholderNode() {
  const node = el("div", "placeholder");
  node.id = "placeholder";
  const img = document.createElement("img");
  img.src = "/static/bob.png?v=36";
  img.alt = "";
  img.className = "placeholder-bob";
  node.append(
    img,
    el("h2", "", "What should Stuart work on?"),
    el("p", "", "Pick a task, adjust filters, edit the draft, then send.")
  );
  const picks = [];
  for (const group of workspace?.tasks || []) {
    if (group.items?.[0]) picks.push(group.items[0]);
    if (picks.length === 4) break;
  }
  if (picks.length) {
    const row = el("div", "starters");
    for (const item of picks) {
      const chip = el("button", "starter", item.label);
      chip.type = "button";
      chip.addEventListener("click", () => selectTask(item.id));
      row.append(chip);
    }
    node.append(row);
  }
  return node;
}

function setStatus(node, label) {
  let gif = node.querySelector(".status-bob");
  let text = node.querySelector(".status-label");
  if (!gif) {
    gif = document.createElement("img");
    gif.src = "/static/bob_confused.gif";
    gif.alt = "";
    gif.className = "status-bob";
    node.replaceChildren(gif, el("span", "status-label", label));
    return;
  }
  if (text) text.textContent = label;
  else node.append(el("span", "status-label", label));
}

function resizePrompt() {
  prompt.style.height = "auto";
  prompt.style.height = `${Math.min(prompt.scrollHeight, 160)}px`;
}

function canvasHasTurns() {
  return Boolean(canvas.querySelector(".turn"));
}

function showEmptyCanvas() {
  canvas.replaceChildren(placeholderNode());
  renderQueryNav();
}

function snapshotActive() {
  const chat = chats.find((item) => item.id === activeChatId);
  if (!chat) return;
  chat.html = canvas.innerHTML;
  persistChats();
}

function persistChats() {
  const payload = {
    activeChatId,
    chats: chats.slice(0, CHATS_LIMIT).map((item) => ({
      id: item.id,
      sessionId: item.sessionId || "",
      title: item.title || "Chat",
      html: item.html || "",
    })),
  };
  try {
    localStorage.setItem(CHATS_KEY, JSON.stringify(payload));
  } catch {
    payload.chats = payload.chats.map((item, index) =>
      index < 8 ? item : { ...item, html: "" }
    );
    try {
      localStorage.setItem(CHATS_KEY, JSON.stringify(payload));
    } catch {
      /* quota */
    }
  }
}

function loadChats() {
  try {
    const raw = JSON.parse(localStorage.getItem(CHATS_KEY) || "");
    if (!raw || !Array.isArray(raw.chats)) return;
    chats = raw.chats.filter((item) => item && item.id);
    activeChatId = chats.some((item) => item.id === raw.activeChatId)
      ? raw.activeChatId
      : chats[0]?.id || "";
  } catch {
    chats = [];
    activeChatId = "";
  }
}

function restoreActiveChat() {
  const chat = chats.find((item) => item.id === activeChatId);
  if (chat?.sessionId) sessionId = chat.sessionId;
  if (chat?.html && chat.html.includes("turn")) {
    canvas.innerHTML = chat.html;
    for (const turn of canvas.querySelectorAll(".turn.pending")) {
      turn.classList.remove("pending");
      turn.querySelector(".status")?.remove();
      turn.querySelector(".caret")?.remove();
    }
    renderQueryNav();
    canvas.scrollTop = canvas.scrollHeight;
    return true;
  }
  return false;
}

function historyTitle(text) {
  const compact = text.replace(/\s+/g, " ").trim();
  return compact.length > 42 ? `${compact.slice(0, 41)}…` : compact;
}

function renderHistory() {
  chatHistory.replaceChildren();
  if (!chats.length) {
    chatHistory.append(el("p", "history-empty", "No chats yet."));
    return;
  }
  for (const chat of chats) {
    const button = el("button", "history-item", chat.title);
    button.type = "button";
    button.title = chat.title;
    if (chat.id === activeChatId) {
      button.classList.add("active");
      button.setAttribute("aria-current", "true");
    }
    button.addEventListener("click", () => openChat(chat.id));
    chatHistory.append(button);
  }
}

function ensureActiveChat(title) {
  if (activeChatId) {
    const existing = chats.find((item) => item.id === activeChatId);
    if (existing) return existing;
  }
  const chat = {
    id: crypto.randomUUID(),
    sessionId,
    title: historyTitle(title),
    html: "",
  };
  chats.unshift(chat);
  activeChatId = chat.id;
  renderHistory();
  persistChats();
  return chat;
}

function settleIncompleteTurn() {
  const last = canvas.querySelector(".turn:last-child");
  if (!last) return;
  const inFlight = last.classList.contains("pending");
  last.querySelector(".status")?.remove();
  last.querySelector(".caret")?.remove();
  last.classList.remove("pending");
  if (inFlight && !last.querySelector(".stopped")) {
    last.append(el("p", "error stopped", "Stopped. Stuart cancelled this reply."));
  }
}

function abandonInFlight() {
  abortController?.abort();
  abortController = null;
  requestGen += 1;
  setBusy(false);
}

function openChat(chatId) {
  const chat = chats.find((item) => item.id === chatId);
  if (!chat || chat.id === activeChatId) return;
  abandonInFlight();
  settleIncompleteTurn();
  snapshotActive();
  activeChatId = chat.id;
  sessionId = chat.sessionId;
  if (chat.html && chat.html.includes("turn")) canvas.innerHTML = chat.html;
  else showEmptyCanvas();
  renderHistory();
  persistChats();
  renderQueryNav();
  canvas.scrollTop = canvas.scrollHeight;
  prompt.focus();
}

async function createSession() {
  const session = await fetch("/api/session", { method: "POST" }).then((res) => res.json());
  sessionId = session.session_id;
  return sessionId;
}

async function startNewChat() {
  endCall();
  abandonInFlight();
  settleIncompleteTurn();
  snapshotActive();
  if (!canvasHasTurns() && !activeChatId) {
    prompt.focus();
    return;
  }
  await createSession();
  activeChatId = "";
  activeTask = "";
  for (const node of taskMenu.querySelectorAll(".task")) node.classList.remove("active");
  applyTaskScope();
  prompt.value = "";
  resizePrompt();
  clearAttachments();
  showEmptyCanvas();
  renderHistory();
  persistChats();
  prompt.focus();
}

function renderQueryNav() {
  if (!queryNav) return;
  const turns = [...canvas.querySelectorAll(".turn")];
  queryNav.replaceChildren();
  queryNav.hidden = turns.length === 0;
  turns.forEach((turn, index) => {
    if (!turn.id) turn.id = `turn-${index + 1}`;
    const mark = el("button", "query-mark");
    mark.type = "button";
    const preview = turn.querySelector(".bubble.user")?.textContent || `Query ${index + 1}`;
    const label = preview.replace(/\s+/g, " ").trim().slice(0, 80);
    mark.dataset.preview = label;
    mark.setAttribute("aria-label", `Jump to query ${index + 1}: ${label}`);
    mark.addEventListener("click", () => {
      turn.scrollIntoView({ behavior: "smooth", block: "start" });
    });
    queryNav.append(mark);
  });
  highlightQueryNav();
}

function highlightQueryNav() {
  const turns = [...canvas.querySelectorAll(".turn")];
  const marks = [...queryNav.querySelectorAll(".query-mark")];
  if (!turns.length || !marks.length) return;
  const target = canvas.getBoundingClientRect().top + canvas.clientHeight * 0.28;
  let active = 0;
  turns.forEach((turn, index) => {
    if (turn.getBoundingClientRect().top <= target) active = index;
  });
  marks.forEach((mark, index) => mark.classList.toggle("active", index === active));
}

function appendTurn(userText) {
  document.getElementById("placeholder")?.remove();
  const turn = el("section", "turn pending");
  turn.id = `turn-${crypto.randomUUID()}`;
  const userBubble = el("div", "bubble user", userText);
  const status = el("p", "status");
  setStatus(status, "Stuart is working…");
  const reply = el("div");
  turn.append(userBubble, status, reply);
  canvas.append(turn);
  canvas.scrollTop = canvas.scrollHeight;
  ensureActiveChat(userText);
  snapshotActive();
  renderQueryNav();
  return { userBubble, status, reply, turn };
}

function setBusy(busy) {
  send.disabled = busy;
  send.hidden = busy;
  stop.hidden = !busy;
  attachBtn.disabled = busy;
  dictateBtn.disabled = busy;
  if (busy) stopDictation();
}

function selectTask(taskId) {
  activeTask = taskId;
  for (const node of taskMenu.querySelectorAll(".task")) {
    node.classList.toggle("active", node.dataset.taskId === taskId);
  }
  applyTaskScope();
  fillComposer(taskId);
}

function applyTaskScope() {
  const scopes = findTask(activeTask)?.scopes;
  const constrained = Array.isArray(scopes);
  for (const block of document.querySelectorAll("#rail-right [data-scope]")) {
    block.hidden = constrained && !scopes.includes(block.dataset.scope);
  }
  const hasScope = !constrained || scopes.length > 0;
  filterClear.hidden = !hasScope;
  filterHint.textContent = hasScope
    ? "Scope Stuart to a territory, rep, quarter, or deal before you ask."
    : "This knowledge task uses approved documents and does not need book filters.";
}

function renderAttachChips() {
  attachChips.replaceChildren();
  attachChips.hidden = !attachments.length;
  for (const item of attachments) {
    const chip = el("div", "attach-chip");
    chip.append(el("span", "", item.filename));
    const remove = el("button", "", "×");
    remove.type = "button";
    remove.setAttribute("aria-label", `Remove ${item.filename}`);
    remove.addEventListener("click", () => {
      attachments = attachments.filter((file) => file !== item);
      renderAttachChips();
    });
    chip.append(remove);
    attachChips.append(chip);
  }
}

function clearAttachments() {
  attachments = [];
  attachInput.value = "";
  renderAttachChips();
}

function suffixOf(name) {
  const dot = name.lastIndexOf(".");
  return dot === -1 ? "" : name.slice(dot).toLowerCase();
}

function readFileAsAttachment(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = String(reader.result || "");
      const base64 = result.includes(",") ? result.split(",")[1] : result;
      resolve({
        filename: file.name,
        mime_type: file.type,
        content_base64: base64,
      });
    };
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

async function addFiles(fileList) {
  const incoming = [...fileList];
  for (const file of incoming) {
    if (attachments.length >= MAX_ATTACH) break;
    if (!ALLOWED_ATTACH.has(suffixOf(file.name))) continue;
    if (file.size > MAX_ATTACH_BYTES) continue;
    attachments.push(await readFileAsAttachment(file));
  }
  renderAttachChips();
  attachInput.value = "";
}

async function readSse(response, onEvent, signal) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  const onAbort = () => reader.cancel();
  signal?.addEventListener("abort", onAbort, { once: true });
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const chunks = buffer.split("\n\n");
      buffer = chunks.pop() || "";
      for (const chunk of chunks) {
        const line = chunk
          .split("\n")
          .filter((part) => part.startsWith("data:"))
          .map((part) => part.slice(5).trim())
          .join("");
        if (!line) continue;
        onEvent(JSON.parse(line));
      }
    }
  } finally {
    signal?.removeEventListener("abort", onAbort);
  }
}

async function askStuart({ text }) {
  abortController?.abort();
  const gen = ++requestGen;
  abortController = new AbortController();
  const { signal } = abortController;
  settleIncompleteTurn();
  const filters = currentFilters();
  const files = attachments.map((item) => ({ ...item }));
  const preview = files.length
    ? `${text}\n\nAttached: ${files.map((item) => item.filename).join(", ")}`
    : text;
  const { userBubble, status, reply, turn } = appendTurn(preview);
  const chatId = activeChatId;
  const onThisChat = () => gen === requestGen && canvas.contains(reply);
  let spoken = "";
  let streamEl = null;
  let caret = null;
  let draft = "";
  let shown = 0;
  let timer = null;

  const paint = () => {
    streamEl.replaceChildren(formatDraft(draft.slice(0, shown)), caret);
    canvas.scrollTop = canvas.scrollHeight;
  };
  const stopTimer = () => {
    if (timer) {
      clearInterval(timer);
      timer = null;
    }
  };
  // Reveal at reading speed, but never fall behind what the model has sent.
  const startTimer = () => {
    if (timer) return;
    timer = setInterval(() => {
      if (shown >= draft.length) {
        stopTimer();
        return;
      }
      const backlog = draft.length - shown;
      shown += Math.max(2, Math.ceil(backlog / 14));
      paint();
    }, 16);
  };
  setBusy(true);
  const body = { session_id: sessionId, message: text, task_id: activeTask, filters };
  if (files.length) body.attachments = files;
  clearAttachments();
  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    });
    const headerSession = response.headers.get("X-Session-Id");
    if (headerSession) {
      sessionId = headerSession;
      const chat = chats.find((item) => item.id === chatId);
      if (chat) chat.sessionId = headerSession;
    }
    if (!response.ok) {
      if (!onThisChat()) return;
      status.remove();
      turn.classList.remove("pending");
      reply.append(el("p", "error", "Could not send that. Try again."));
      return;
    }
    await readSse(
      response,
      (event) => {
        if (!onThisChat()) return;
        if (event.type === "prompt") {
          userBubble.textContent = event.text;
          const chat = chats.find((item) => item.id === chatId);
          if (chat && canvas.querySelectorAll(".turn").length === 1) {
            chat.title = historyTitle(event.text);
            renderHistory();
          }
        }
        if (event.type === "status") setStatus(status, event.label);
        if (event.type === "reset") {
          stopTimer();
          draft = "";
          shown = 0;
          if (streamEl) paint();
        }
        if (event.type === "delta") {
          if (!streamEl) {
            streamEl = el("div", "stream draft");
            caret = el("span", "caret");
            streamEl.append(caret);
            reply.append(streamEl);
          }
          draft += event.text;
          startTimer();
        }
        if (event.type === "reply") {
          spoken = event.kind === "briefing" ? briefingText(event) : event.text || "";
          stopTimer();
          if (streamEl) {
            shown = draft.length;
            paint();
          }
          caret?.remove();
          status.remove();
          turn.classList.remove("pending");
          if (event.kind === "briefing") {
            streamEl?.remove();
            reply.append(renderBriefing(event));
          } else if (streamEl) {
            streamEl.className = "stream answer";
            streamEl.replaceChildren(formatDraft(event.text));
            addReplyCopy(reply, event.text);
          } else {
            const answer = el("div", "stream answer");
            answer.append(formatDraft(event.text));
            reply.append(answer);
            addReplyCopy(reply, event.text);
          }
          canvas.scrollTop = canvas.scrollHeight;
          snapshotActive();
        }
        if (event.type === "error") {
          stopTimer();
          status.remove();
          turn.classList.remove("pending");
          reply.append(el("p", "error", event.message));
          canvas.scrollTop = canvas.scrollHeight;
          snapshotActive();
        }
      },
      signal
    );
    if (signal.aborted) {
      const abortError = new DOMException("Aborted", "AbortError");
      throw abortError;
    }
  } catch (err) {
    if (!onThisChat()) return;
    if (err.name === "AbortError") {
      settleIncompleteTurn();
    } else {
      status.remove();
      turn.classList.remove("pending");
      reply.append(el("p", "error", "Stuart lost the connection. Try that again."));
    }
  } finally {
    stopTimer();
    if (gen !== requestGen) return;
    abortController = null;
    setBusy(false);
    snapshotActive();
    prompt.focus();
  }
  return spoken;
}

function addChecks(root, items, name) {
  for (const item of items) {
    const row = el("label", "check");
    const input = document.createElement("input");
    input.type = "checkbox";
    input.name = name;
    input.value = item.id;
    if (item.territory) row.dataset.territory = item.territory;
    if (item.owner) row.dataset.owner = item.owner;
    if (item.geos?.length) row.dataset.geos = item.geos.join(",");
    row.append(input, document.createTextNode(item.label));
    root.append(row);
  }
}

function applyBookScope() {
  const geos = selectedValues("geo");
  let visibleReps = 0;
  let visibleOpps = 0;
  for (const row of filterReps.querySelectorAll(".check")) {
    const rowGeos = (row.dataset.geos || "").split(",").filter(Boolean);
    const show = !geos.length || rowGeos.some((geo) => geos.includes(geo));
    row.hidden = !show;
    if (!show) row.querySelector("input").checked = false;
    if (show) visibleReps += 1;
  }
  const liveBoats = selectedValues("boat");
  for (const row of filterOpps.querySelectorAll(".check")) {
    const territory = row.dataset.territory || "";
    const owner = row.dataset.owner || "";
    const geoOk = !geos.length || geos.includes(territory);
    const boatOk = !liveBoats.length || liveBoats.includes(owner);
    const show = geoOk && boatOk;
    row.hidden = !show;
    if (!show) row.querySelector("input").checked = false;
    if (show) visibleOpps += 1;
  }
  if (emptyReps) emptyReps.hidden = visibleReps > 0;
  if (emptyOpps) emptyOpps.hidden = visibleOpps > 0;
}

function bindSmoothGroup(block) {
  const summary = block.querySelector("summary");
  const panel = block.querySelector(".group-panel");
  summary.addEventListener("click", (event) => {
    if (!block.open) return;
    event.preventDefault();
    if (block.classList.contains("closing")) return;
    block.classList.add("closing");
    const finish = (end) => {
      if (end && end.target !== panel) return;
      if (end && end.propertyName && end.propertyName !== "grid-template-rows") return;
      clearTimeout(timer);
      panel.removeEventListener("transitionend", finish);
      block.open = false;
      block.classList.remove("closing");
    };
    const timer = setTimeout(finish, 280);
    panel.addEventListener("transitionend", finish);
  });
}

function renderTasks(groups) {
  taskMenu.replaceChildren();
  for (const group of groups) {
    const block = document.createElement("details");
    block.className = "group";
    const summary = el("summary", "group-toggle", group.label);
    const panel = el("div", "group-panel");
    const list = el("div", "group-items");
    for (const item of group.items) {
      const button = el("button", "task", item.label);
      button.type = "button";
      button.dataset.taskId = item.id;
      button.addEventListener("click", () => selectTask(item.id));
      list.append(button);
    }
    panel.append(list);
    block.append(summary, panel);
    bindSmoothGroup(block);
    taskMenu.append(block);
  }
}

function paneKey(side) {
  return `gru-${side}-collapsed`;
}

function applyPane(side, collapsed) {
  workspaceEl.classList.toggle(`${side}-collapsed`, collapsed);
  const button = side === "left" ? toggleLeft : toggleRight;
  button.setAttribute("aria-expanded", collapsed ? "false" : "true");
  button.setAttribute(
    "aria-label",
    collapsed ? `Expand ${side === "left" ? "task" : "filter"} pane` : `Collapse ${side === "left" ? "task" : "filter"} pane`
  );
  localStorage.setItem(paneKey(side), collapsed ? "1" : "0");
}

function bootPanes() {
  applyPane("left", localStorage.getItem(paneKey("left")) === "1");
  applyPane("right", localStorage.getItem(paneKey("right")) === "1");
}

function speechRec() {
  if (!SpeechCtor) return null;
  const rec = new SpeechCtor();
  rec.lang = "en-US";
  rec.interimResults = true;
  return rec;
}

function speechOk() {
  if (SpeechCtor) return true;
  window.alert("Voice needs Chrome or Edge.");
  return false;
}

function stopDictation() {
  dictating = false;
  dictateBtn.classList.remove("listening");
  dictateBtn.setAttribute("aria-pressed", "false");
  dictateBtn.setAttribute("aria-label", "Start voice input");
  try {
    dictateRec?.stop();
  } catch {
    /* already stopped */
  }
  dictateRec = null;
}

function toggleDictation() {
  if (dictating) {
    stopDictation();
    return;
  }
  if (!speechOk() || send.disabled) return;
  const rec = speechRec();
  dictating = true;
  dictateBase = prompt.value.trim();
  dictateFinal = "";
  dictateBtn.classList.add("listening");
  dictateBtn.setAttribute("aria-pressed", "true");
  dictateBtn.setAttribute("aria-label", "Stop voice input");
  rec.continuous = true;
  rec.onresult = (event) => {
    let interim = "";
    for (let i = event.resultIndex; i < event.results.length; i++) {
      const piece = event.results[i][0].transcript.trim();
      if (event.results[i].isFinal) dictateFinal = `${dictateFinal} ${piece}`.trim();
      else interim = piece;
    }
    prompt.value = [dictateBase, dictateFinal, interim].filter(Boolean).join(" ");
    resizePrompt();
  };
  rec.onend = () => {
    if (dictating) rec.start();
  };
  rec.onerror = () => stopDictation();
  dictateRec = rec;
  rec.start();
}

function setCallStatus(label, caption) {
  voiceCallStatus.textContent = label;
  if (caption !== undefined) voiceCallCaption.textContent = caption;
}

function speak(text) {
  return new Promise((resolve) => {
    speechSynthesis.cancel();
    const utter = new SpeechSynthesisUtterance(String(text || "").slice(0, 4000));
    utter.onend = resolve;
    utter.onerror = resolve;
    speechSynthesis.speak(utter);
  });
}

function stopCallListen() {
  try {
    callRec?.stop();
  } catch {
    /* already stopped */
  }
  callRec = null;
}

function endCall() {
  inCall = false;
  callBusy = false;
  stopCallListen();
  speechSynthesis.cancel();
  callStream?.getTracks().forEach((track) => track.stop());
  callStream = null;
  voiceCall.hidden = true;
}

function listenThenSend() {
  if (!inCall || callBusy) return;
  const rec = speechRec();
  if (!rec) return;
  rec.continuous = false;
  let heard = "";
  rec.onresult = (event) => {
    let interim = "";
    for (let i = event.resultIndex; i < event.results.length; i++) {
      const piece = event.results[i][0].transcript.trim();
      if (event.results[i].isFinal) heard = `${heard} ${piece}`.trim();
      else interim = piece;
    }
    setCallStatus("Listening…", heard || interim);
  };
  rec.onerror = () => {
    if (inCall && !callBusy) rec.start();
  };
  rec.onend = async () => {
    if (!inCall || callBusy) return;
    if (!heard) {
      rec.start();
      return;
    }
    callBusy = true;
    setCallStatus("Thinking…", heard);
    const spoken = await askStuart({ text: heard });
    if (!inCall) return;
    if (spoken) {
      setCallStatus("Speaking…", "");
      await speak(spoken);
    }
    callBusy = false;
    if (inCall) {
      setCallStatus("Listening…", "");
      listenThenSend();
    }
  };
  callRec = rec;
  rec.start();
}

async function startCall() {
  if (inCall) return;
  if (!speechOk()) return;
  stopDictation();
  try {
    // ponytail: getUserMedia is the WebRTC capture. RTCPeerConnection to Gemini Live
    // only if we accept bypassing the orchestrator.
    callStream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch {
    window.alert("Microphone permission is required for a voice call.");
    return;
  }
  inCall = true;
  voiceCall.hidden = false;
  setCallStatus("Listening…", "");
  listenThenSend();
}

let dictating = false;
let dictateRec = null;
let dictateBase = "";
let dictateFinal = "";
let inCall = false;
let callRec = null;
let callStream = null;
let callBusy = false;

form.addEventListener("submit", (event) => {
  event.preventDefault();
  stopDictation();
  const text = prompt.value.trim();
  if ((!text && !attachments.length) || send.disabled) return;
  prompt.value = "";
  resizePrompt();
  askStuart({ text: text || "Review the attached files." });
});

stop.addEventListener("click", () => {
  settleIncompleteTurn();
  snapshotActive();
  canvas.scrollTop = canvas.scrollHeight;
  abortController?.abort();
  setBusy(false);
});

newChat.addEventListener("click", () => {
  startNewChat();
});

attachBtn.addEventListener("click", () => attachInput.click());
attachInput.addEventListener("change", () => addFiles(attachInput.files || []));
dictateBtn.addEventListener("click", toggleDictation);
voiceCallBtn.addEventListener("click", startCall);
hangup.addEventListener("click", endCall);

toggleLeft.addEventListener("click", () => {
  applyPane("left", !workspaceEl.classList.contains("left-collapsed"));
});
toggleRight.addEventListener("click", () => {
  applyPane("right", !workspaceEl.classList.contains("right-collapsed"));
});

prompt.addEventListener("input", resizePrompt);

canvas.addEventListener("scroll", highlightQueryNav);

prompt.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

function currentTheme() {
  return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
}

function applyTheme(theme) {
  const next = theme === "dark" ? "dark" : "light";
  document.documentElement.dataset.theme = next;
  localStorage.setItem("gru-theme", next);
  const dark = next === "dark";
  for (const button of document.querySelectorAll("[data-theme-toggle]")) {
    button.setAttribute("aria-pressed", dark ? "true" : "false");
    button.setAttribute("aria-label", dark ? "Switch to light mode" : "Switch to dark mode");
  }
}

function bootTheme() {
  applyTheme(currentTheme());
  for (const button of document.querySelectorAll("[data-theme-toggle]")) {
    button.addEventListener("click", () => {
      applyTheme(currentTheme() === "dark" ? "light" : "dark");
    });
  }
}

async function boot() {
  bootTheme();
  bootPanes();
  loadChats();
  const saved = chats.find((item) => item.id === activeChatId);
  if (saved?.sessionId) sessionId = saved.sessionId;
  if (!sessionId) await createSession();
  workspace = await fetch("/api/workspace").then((res) => res.json());
  renderTasks(workspace.tasks);
  renderHistory();
  if (!restoreActiveChat()) showEmptyCanvas();
  addChecks(filterGeos, workspace.filters.geos, "geo");
  addChecks(filterReps, workspace.filters.boats, "boat");
  addChecks(filterHorizon, workspace.filters.report_types, "report");
  addChecks(filterOpps, workspace.filters.opps, "opp");
  applyBookScope();
  const refreshDraft = () => {
    applyBookScope();
    if (activeTask) fillComposer(activeTask);
  };
  filterGeos.addEventListener("change", refreshDraft);
  filterReps.addEventListener("change", refreshDraft);
  filterHorizon.addEventListener("change", refreshDraft);
  filterOpps.addEventListener("change", refreshDraft);
  filterClear.addEventListener("click", () => {
    for (const input of document.querySelectorAll("#rail-right input[type=checkbox]")) {
      input.checked = false;
    }
    refreshDraft();
  });
}

boot();
