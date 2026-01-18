/* =========================
   Helpers / Storage
========================= */
const STORAGE_KEY = "codeblue_queue_v1";
const NURSE_PIN = "2468"; // demo PIN

function nowTime() {
  const d = new Date();
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function loadQueue() {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]"); }
  catch { return []; }
}

function saveQueue(q) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(q));
}

/* =========================
   Tabs
========================= */
const tabButtons = document.querySelectorAll(".tab");
const pages = {
  kiosk: document.getElementById("tab-kiosk"),
  nurse: document.getElementById("tab-nurse"),
};

tabButtons.forEach(btn => {
  btn.addEventListener("click", () => {
    tabButtons.forEach(b => b.classList.remove("active"));
    btn.classList.add("active");

    const key = btn.dataset.tab;
    Object.values(pages).forEach(p => p.classList.remove("active"));
    pages[key].classList.add("active");

    if (key === "nurse") renderNurseQueue();
  });
});

/* =========================
   Kiosk logic
========================= */
const submitBtn = document.getElementById("submitBtn");
const resultSection = document.getElementById("result");
const kioskSuccess = document.getElementById("kioskSuccess");
const esiBadge = document.getElementById("esiBadge");
const analysisEl = document.getElementById("analysis");
const copyBtn = document.getElementById("copyBtn");
const newBtn = document.getElementById("newBtn");
const goNurseBtn = document.getElementById("goNurseBtn");

function setLoading(isLoading) {
  submitBtn.classList.toggle("loading", isLoading);
  submitBtn.disabled = isLoading;
}

/* very simple demo rules based only on complaint text + age */
function mockESI(intake) {
  const c = intake.complaint.toLowerCase();

  if (c.includes("unconscious") || c.includes("not breathing") || c.includes("cardiac arrest"))
    return 1;

  if (
    c.includes("chest pain") ||
    c.includes("trouble breathing") ||
    c.includes("shortness of breath") ||
    c.includes("severe bleeding")
  ) return 2;

  if (c.includes("fever") || c.includes("vomit") || c.includes("fracture")) return 3;

  return 4;
}

function renderResult(esi, text) {
  esiBadge.className = "esi-badge";
  esiBadge.textContent = `ESI LEVEL ${esi}`;
  esiBadge.classList.add(`esi${esi}`);

  analysisEl.textContent = text;

  resultSection.classList.remove("hidden");
  kioskSuccess.classList.remove("hidden");
  resultSection.scrollIntoView({ behavior: "smooth", block: "start" });
}

submitBtn.addEventListener("click", async () => {
  const name = document.getElementById("name").value.trim();
  const age = Number(document.getElementById("age").value);
  const sex = document.getElementById("sex").value;
  const complaint = document.getElementById("complaint").value.trim();

  const hr = Number(document.getElementById("hr").value || 0);
  const sbp = Number(document.getElementById("sbp").value || 0);
  const rr = Number(document.getElementById("rr").value || 0);
  const temp = Number(document.getElementById("temp").value || 0);

  if (!name || !complaint) {
    alert("Please enter name and symptoms.");
    return;
  }

  const intake = {
    id: crypto.randomUUID(),
    time: nowTime(),
    name,
    age,
    sex,
    vitals: { hr, sbp, rr, temp },
    complaint,
  };

  setLoading(true);
  await new Promise(r => setTimeout(r, 600));

  const esi = mockESI(intake);

  const vitalsText = [
    hr ? `HR ${hr}` : null,
    sbp ? `SBP ${sbp}` : null,
    rr ? `RR ${rr}` : null,
    temp ? `Temp ${temp}` : null,
  ].filter(Boolean).join(" • ") || "No vitals provided";

  const summary =
    `Patient: ${intake.name} (${intake.age}y, ${intake.sex}). ` +
    `Symptoms: ${intake.complaint} ` +
    `Vitals: ${vitalsText}. ` +
    `Recommended: obtain full vitals, focused assessment, and escalate if deterioration occurs.`;

  const q = loadQueue();
  q.push({ ...intake, esi, analysis: summary });
  saveQueue(q);

  renderResult(esi, summary);
  setLoading(false);
});

copyBtn?.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(analysisEl.textContent || "");
    copyBtn.textContent = "Copied!";
    setTimeout(() => (copyBtn.textContent = "Copy summary"), 900);
  } catch {
    alert("Copy failed. (Browser blocked clipboard)");
  }
});

newBtn?.addEventListener("click", () => {
  resultSection.classList.add("hidden");
  kioskSuccess.classList.add("hidden");
  document.getElementById("complaint").value = "";
  document.getElementById("name").focus();
});

goNurseBtn?.addEventListener("click", () => {
  document.querySelector('[data-tab="nurse"]').click();
});

/* =========================
   Nurse dashboard
========================= */
const nurseLock = document.getElementById("nurseLock");
const nurseDash = document.getElementById("nurseDash");
const unlockBtn = document.getElementById("unlockBtn");
const pinEl = document.getElementById("pin");

unlockBtn?.addEventListener("click", () => {
  const pin = (pinEl.value || "").trim();
  if (pin !== NURSE_PIN) {
    alert("Wrong PIN.");
    return;
  }
  nurseLock.classList.add("hidden");
  nurseDash.classList.remove("hidden");
  renderNurseQueue();
});

document.getElementById("refreshBtn")?.addEventListener("click", renderNurseQueue);

document.getElementById("clearBtn")?.addEventListener("click", () => {
  if (!confirm("Clear all patients from queue?")) return;
  saveQueue([]);
  renderNurseQueue();
  document.getElementById("selectedCard").innerHTML = `
    <div class="card-head"><h2>Selected Patient</h2><span class="pill blue">Details</span></div>
    <p class="analysis muted">Queue cleared.</p>
  `;
});

function renderNurseQueue() {
  const q = loadQueue().sort((a, b) => a.esi - b.esi);
  const list = document.getElementById("queueList");
  const mCritical = document.getElementById("mCritical");
  const mTotal = document.getElementById("mTotal");

  if (!list) return;

  mTotal.textContent = String(q.length);
  mCritical.textContent = String(q.filter(p => p.esi <= 2).length);

  list.innerHTML = "";

  if (!q.length) {
    list.innerHTML = `<div class="empty">No patients in queue.</div>`;
    return;
  }

  q.forEach(p => {
    const item = document.createElement("button");
    item.className = `queueItem esi${p.esi}`;
    item.type = "button";
    item.innerHTML = `
      <div class="qLeft">
        <div class="qTop">
          <span class="badge">ESI ${p.esi}</span>
          <span class="name">${escapeHtml(p.name)}</span>
        </div>
        <div class="qSub">${p.age}y • ${escapeHtml(p.time)}</div>
      </div>
      <div class="qRight">${shorten(p.complaint, 42)}</div>
    `;
    item.addEventListener("click", () => showSelected(p));
    list.appendChild(item);
  });
}

function showSelected(p) {
  const card = document.getElementById("selectedCard");
  const vit = p.vitals || {};
  const vitText = [
    vit.hr ? `HR ${vit.hr}` : null,
    vit.sbp ? `SBP ${vit.sbp}` : null,
    vit.rr ? `RR ${vit.rr}` : null,
    vit.temp ? `Temp ${vit.temp}` : null,
  ].filter(Boolean).join(" • ") || "Not provided";

  card.innerHTML = `
    <div class="card-head">
      <h2>${escapeHtml(p.name)} <span class="muted">(${p.age}y)</span></h2>
      <span class="pill blue">ESI ${p.esi}</span>
    </div>

    <div class="detailGrid">
      <div class="detail">
        <div class="k">Time</div><div class="v">${escapeHtml(p.time)}</div>
      </div>
      <div class="detail">
        <div class="k">Sex</div><div class="v">${escapeHtml(p.sex)}</div>
      </div>
      <div class="detail">
        <div class="k">Vitals</div><div class="v">${escapeHtml(vitText)}</div>
      </div>
    </div>

    <div class="divider"></div>

    <div class="k">Complaint</div>
    <div class="vBox">${escapeHtml(p.complaint)}</div>

    <div class="k" style="margin-top:10px;">AI summary</div>
    <div class="vBox">${escapeHtml(p.analysis)}</div>
  `;
}

/* =========================
   Video feed (camera + embed)
========================= */
const cam = document.getElementById("cam");
const camHint = document.getElementById("camHint");
let camStream = null;

document.getElementById("startCamBtn")?.addEventListener("click", async () => {
  try {
    camStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
    cam.srcObject = camStream;
    camHint.classList.add("hidden");
  } catch (e) {
    alert("Camera blocked. Allow camera permission in your browser.");
  }
});

document.getElementById("stopCamBtn")?.addEventListener("click", () => {
  if (camStream) {
    camStream.getTracks().forEach(t => t.stop());
    camStream = null;
  }
  cam.srcObject = null;
  camHint.classList.remove("hidden");
});

document.getElementById("loadStreamBtn")?.addEventListener("click", () => {
  const url = (document.getElementById("streamUrl").value || "").trim();
  const wrap = document.getElementById("embedWrap");
  if (!url) return;

  wrap.classList.remove("hidden");
  wrap.innerHTML = `
    <iframe
      src="${escapeAttr(url)}"
      frameborder="0"
      allow="autoplay; encrypted-media; picture-in-picture"
      allowfullscreen
    ></iframe>
  `;
});

/* =========================
   Utils
========================= */
function shorten(s, n) {
  const t = (s || "").trim();
  return t.length > n ? escapeHtml(t.slice(0, n - 1) + "…") : escapeHtml(t);
}

function escapeHtml(str) {
  return String(str)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function escapeAttr(str) {
  return escapeHtml(str).replaceAll("`", "");
}
