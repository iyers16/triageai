// Keep the same backend base URL
const API = "http://localhost:5000/api";

let currentStream = null;

// ============ INIT ============
document.addEventListener("DOMContentLoaded", () => {
  setupTabs();
  setupKiosk();
  setupNurse();
  setupVideo();
  startQueuePolling();
});

// ============ TABS ============
function setupTabs() {
  const tabs = document.querySelectorAll(".tab");
  const pages = document.querySelectorAll(".tab-page");

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      const target = tab.dataset.tab; // "kiosk" or "nurse"

      tabs.forEach((t) => t.classList.remove("active"));
      pages.forEach((p) => p.classList.remove("active"));

      tab.classList.add("active");
      const page = document.getElementById(`tab-${target}`);
      if (page) page.classList.add("active");

      // Auto-refresh queue when opening nurse tab
      if (target === "nurse") {
        fetchQueue();
      }
    });
  });
}

// ============ KIOSK (PATIENT) ============
function setupKiosk() {
  const submitBtn = document.getElementById("submitBtn");
  const copyBtn = document.getElementById("copyBtn");
  const newBtn = document.getElementById("newBtn");
  const goNurseBtn = document.getElementById("goNurseBtn");

  if (submitBtn) {
    submitBtn.addEventListener("click", submitPatient);
  }

  if (copyBtn) {
    copyBtn.addEventListener("click", () => {
      const analysis = document.getElementById("analysis")?.innerText || "";
      const badge = document.getElementById("esiBadge")?.innerText || "";
      const text = `${badge}\n\n${analysis}`;
      navigator.clipboard.writeText(text).catch(() => {});
    });
  }

  if (newBtn) {
    newBtn.addEventListener("click", () => {
      document.getElementById("complaint").value = "";
      document.getElementById("name").value = "";
      document.getElementById("age").value = "30";
      document.getElementById("result").classList.add("hidden");
      document.getElementById("kioskSuccess").classList.add("hidden");
    });
  }

  if (goNurseBtn) {
    goNurseBtn.addEventListener("click", () => {
      // Switch to nurse tab
      const nurseTabBtn = document.querySelector('.tab[data-tab="nurse"]');
      if (nurseTabBtn) nurseTabBtn.click();
    });
  }
}

async function submitPatient() {
  const btn = document.getElementById("submitBtn");
  const errorEl = document.getElementById("kioskError");
  const resultCard = document.getElementById("result");
  const successCard = document.getElementById("kioskSuccess");

  errorEl.classList.add("hidden");
  resultCard.classList.add("hidden");
  successCard.classList.add("hidden");

  btn.disabled = true;
  btn.classList.add("loading");

  const data = {
    // Keep required fields exactly as backend expects
    name: document.getElementById("name").value,
    age: document.getElementById("age").value,
    complaint: document.getElementById("complaint").value,
    // Extra fields (backend can ignore safely)
    sex: document.getElementById("sex").value,
    hr: document.getElementById("hr").value || null,
    sbp: document.getElementById("sbp").value || null,
    rr: document.getElementById("rr").value || null,
    temp: document.getElementById("temp").value || null,
  };

  try {
    const res = await fetch(`${API}/submit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });

    if (!res.ok) {
      throw new Error("Network error");
    }

    const result = await res.json(); // expect { esi, analysis?, ... }

    // Show triage result right away
    updateKioskResult(result);
    successCard.classList.remove("hidden");

    // Clear complaint text for next patient
    document.getElementById("complaint").value = "";
  } catch (err) {
    console.error(err);
    errorEl.classList.remove("hidden");
  } finally {
    btn.disabled = false;
    btn.classList.remove("loading");
  }
}

function updateKioskResult(result) {
  const resultCard = document.getElementById("result");
  const badge = document.getElementById("esiBadge");
  const analysisEl = document.getElementById("analysis");

  if (!resultCard || !badge || !analysisEl) return;

  const esi = typeof result.esi === "number" ? result.esi : "-";

  // Reset classes
  badge.className = "esi-badge";
  if (esi === 1) badge.classList.add("esi1");
  else if (esi === 2) badge.classList.add("esi2");
  else if (esi === 3) badge.classList.add("esi3");
  else if (esi === 4 || esi === 5) badge.classList.add("esi4");

  badge.textContent = `ESI LEVEL ${esi}`;

  const analysisText =
    result.analysis ||
    "Patient has been triaged. Please follow local triage protocol and reassess if symptoms change.";

  analysisEl.textContent = analysisText;
  resultCard.classList.remove("hidden");
}

// ============ NURSE DASHBOARD ============

document.addEventListener("DOMContentLoaded", () => {
  fetch("/session")
    .then(res => res.json())
    .then(data => {
        console.log("DATA: ");
        console.log(data);
      if (data.logged_in) {
        // lock.classList.add("hidden");
        // dash.classList.remove("hidden");
        document.getElementById("loginBtn").hidden = true; 
        const lock = document.getElementById("nurseLock");
        const dash = document.getElementById("nurseDash");
        lock.classList.add("hidden");
        dash.classList.remove("hidden");
        fetchQueue();
      }
    });
});

function setupNurse() {
//   const unlockBtn = document.getElementById('unlockBtn');
  const loginBtn = document.getElementById("loginBtn");
  const logoutBtn = document.getElementById("logoutBtn");
  const clearBtn = document.getElementById("clearBtn");

    fetch("/session")
    .then(res => res.json())
    .then(data => {
      console.log("DATA: ", data);
      console.log("IN: ", data.logged_in); 
      if (data.logged_in) {
        if (loginBtn){
            console.log("In this");
            console.log("loginBtn:", loginBtn);
            document.getElementById('loginStr').style.display = "none"; 
            loginBtn.style.display = "none";
            if (loginBtn) loginBtn.hidden = true;
            if (logoutBtn) logoutBtn.hidden = false;
        }
        // if (lock && dash) {
        //   lock.classList.add("hidden");
        //   dash.classList.remove("hidden");
        // }
        fetchQueue();
      }
    });

  // Setup login button
  if (loginBtn) {
    loginBtn.addEventListener("click", () => {
      window.location.href = "/login";
    });
  }

  if (logoutBtn) {
    logoutBtn.addEventListener("click", () => {
      window.location.href = "/logout"; // your Flask logout route
      // window.location.reload();
    });
  }


        // // Simple demo PIN; adjust if you want, doesn't touch backend
        // const PIN = "1234";

        // if (pinInput.value === PIN) {
        // lock.classList.add("hidden");
        // dash.classList.remove("hidden");
        // fetchQueue();
        // } else {
        // pinInput.value = "";
        // pinInput.placeholder = "Wrong PIN";
        // }
//     });
//   }

  if (refreshBtn) {
    refreshBtn.addEventListener("click", fetchQueue);
  }

  if (clearBtn) {
    // We DON'T call a backend clear endpoint to avoid changing your API.
    clearBtn.addEventListener("click", () => {
      alert("Clear queue is UI-only for now. Wire this to a backend endpoint if you want.");
    });
  }

  // Expose fetchQueue/markDone globally if you need them elsewhere
  window.fetchQueue = fetchQueue;
  window.markDone = markDone;
}

async function fetchQueue() {
  const list = document.getElementById("queueList");
  const mCritical = document.getElementById("mCritical");
  const mTotal = document.getElementById("mTotal");

  if (!list) return;

  list.innerHTML = "";

  try {
    const res = await fetch(`${API}/queue`);
    if (!res.ok) throw new Error("Network error");
    let patients = await res.json();
    // reverse patients array
    patients = patients.reverse();
    if (!Array.isArray(patients) || patients.length === 0) {
      list.innerHTML = `<div class="empty">No patients in queue.</div>`;
      if (mCritical) mCritical.textContent = "0";
      if (mTotal) mTotal.textContent = "0";
      return;
    }

    // Metrics
    const total = patients.length;
    const critical = patients.filter((p) => p.esi === 1 || p.esi === 2).length;
    if (mCritical) mCritical.textContent = critical;
    if (mTotal) mTotal.textContent = total;

    patients.forEach((p) => {
      const item = document.createElement("div");
      item.classList.add("queueItem", `esi${p.esi || "x"}`);

      const status = p.status === "completed" ? "DONE" : "ACTIVE";
      const badgeLabel = `ESI ${p.esi}`;
      const time = p.time || "";

      item.innerHTML = `
        <div>
          <div class="qTop">
            <span class="badge">${badgeLabel}</span>
            <span>${p.name || "Unknown"}</span>
          </div>
          <div class="qSub">
            ${p.age ? `${p.age} yrs • ` : ""}${status}${time ? " • " + time : ""}
          </div>
        </div>
        <div class="qRight">
          ${p.complaint || ""}
        </div>
      `;

      item.addEventListener("click", () => {
        showSelectedPatient(p);
      });

      list.appendChild(item);
    });
  } catch (err) {
    console.error(err);
    list.innerHTML = `<div class="empty">Unable to load queue.</div>`;
    if (mCritical) mCritical.textContent = "0";
    if (mTotal) mTotal.textContent = "0";
  }
}

function showSelectedPatient(p) {
  const card = document.getElementById("selectedCard");
  if (!card) return;

  const esiText = typeof p.esi === "number" ? `ESI ${p.esi}` : "—";
  const status = p.status || "active";

  card.innerHTML = `
    <div class="card-head">
      <h2>Selected Patient</h2>
      <span class="pill blue">Details</span>
    </div>

    <div class="detailGrid">
      <div class="detail">
        <div class="k">Name</div>
        <div class="v">${p.name || "Unknown"}</div>
      </div>
      <div class="detail">
        <div class="k">Age</div>
        <div class="v">${p.age || "-"}</div>
      </div>
      <div class="detail">
        <div class="k">ESI</div>
        <div class="v">${esiText}</div>
      </div>
      <div class="detail">
        <div class="k">Status</div>
        <div class="v">${status}</div>
      </div>
    </div>

    <div class="divider"></div>

    <div class="k">Chief complaint</div>
    <div class="vBox">
      <p>${p.complaint || "—"}</p>
    </div>

    <div class="divider"></div>

    <div class="k">AI analysis</div>
    <div class="vBox">
      ${p.analysis || "No additional analysis."}
    </div>

    <div class="divider"></div>

    <button id="resolveBtn" class="primary small">
      ✅ Mark Resolved
    </button>
  `;

  const resolveBtn = document.getElementById("resolveBtn");
  if (resolveBtn && p.id && p.status !== "completed") {
    resolveBtn.addEventListener("click", async () => {
      await markDone(p.id);
      fetchQueue();
      // After resolving, show generic text again
      card.innerHTML = `
        <div class="card-head">
          <h2>Selected Patient</h2>
          <span class="pill blue">Details</span>
        </div>
        <p class="analysis muted">Click a patient in the queue to view details here.</p>
      `;
    });
  } else if (resolveBtn) {
    resolveBtn.disabled = true;
    resolveBtn.textContent = "Already resolved";
  }
}

async function markDone(id) {
  try {
    await fetch(`${API}/complete/${id}`, { method: "POST" });
  } catch (err) {
    console.error(err);
  }
}

// Poll every 5 seconds if nurse tab is active and unlocked
function startQueuePolling() {
  setInterval(() => {
    const nursePage = document.getElementById("tab-nurse");
    const dash = document.getElementById("nurseDash");
    if (nursePage && nursePage.classList.contains("active") && dash && !dash.classList.contains("hidden")) {
      fetchQueue();
    }
  }, 5000);
}

// ============ VIDEO ============

function setupVideo() {
  const startBtn = document.getElementById("startCamBtn");
  const stopBtn = document.getElementById("stopCamBtn");
  const loadBtn = document.getElementById("loadStreamBtn");

  if (startBtn) startBtn.addEventListener("click", startCamera);
  if (stopBtn) stopBtn.addEventListener("click", stopCamera);
  if (loadBtn) loadBtn.addEventListener("click", loadStreamUrl);
}

async function startCamera() {
  const video = document.getElementById("cam");
  const hint = document.getElementById("camHint");
  const embedWrap = document.getElementById("embedWrap");

  try {
    if (embedWrap) {
      embedWrap.classList.add("hidden");
      embedWrap.innerHTML = "";
    }

    const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
    currentStream = stream;
    if (video) video.srcObject = stream;
    if (hint) hint.textContent = "Camera running";
    hint.style.opacity = "0";
  } catch (err) {
    console.error(err);
    if (hint) {
      hint.textContent = "Unable to access camera";
      hint.style.opacity = "1";
    }
  }
}

function stopCamera() {
  const video = document.getElementById("cam");
  const hint = document.getElementById("camHint");

  if (currentStream) {
    currentStream.getTracks().forEach((t) => t.stop());
    currentStream = null;
  }
  if (video) video.srcObject = null;
  if (hint) {
    hint.textContent = "Camera is off";
    hint.style.opacity = "1";
  }
}

function loadStreamUrl() {
  const urlInput = document.getElementById("streamUrl");
  const embedWrap = document.getElementById("embedWrap");
  const hint = document.getElementById("camHint");

  if (!urlInput || !embedWrap) return;
  const url = urlInput.value.trim();
  if (!url) return;

  // Stop webcam if running
  stopCamera();

  embedWrap.classList.remove("hidden");
  embedWrap.innerHTML = `
    <iframe
      src="${url}"
      frameborder="0"
      allow="autoplay; encrypted-media"
      allowfullscreen
    ></iframe>
  `;

  if (hint) {
    hint.textContent = "Embedded stream";
    hint.style.opacity = "0";
  }
}
