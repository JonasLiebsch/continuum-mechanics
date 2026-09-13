import { initializeApp } from "https://www.gstatic.com/firebasejs/12.18.0/firebase-app.js";
import {
  getAuth,
  onAuthStateChanged,
  signInAnonymously,
  setPersistence,
  browserLocalPersistence
} from "https://www.gstatic.com/firebasejs/12.18.0/firebase-auth.js";
import {
  getFirestore,
  collection,
  addDoc,
  doc,
  updateDoc,
  deleteDoc,
  onSnapshot,
  serverTimestamp,
  writeBatch
} from "https://www.gstatic.com/firebasejs/12.18.0/firebase-firestore.js";

const CFG = window.FLEXURE_CONFIG;
const $ = (id) => document.getElementById(id);

const COLORS = ["#64B5F6", "#62E3D5", "#FFB86B", "#64D98B", "#C792EA", "#F78C6C", "#89DDFF", "#FFD166"];
const MODEL_COLOR = "#EDF2F7";
const GRID = "#2A3852";
const MUTED = "#9FB0C7";
const BG = "#0B1020";

let auth = null;
let db = null;
let currentUser = null;
let unsubscribeMeasurements = null;
let measurements = [];
let selectedLength = "all";
let editingId = null;
let chart = null;
let demoMode = !CFG.firebaseConfig?.apiKey || CFG.firebaseConfig.apiKey.includes("PASTE_");

const localOwnerKey = "flexure_classroom_owner_uid";
const localDataKey = () => `flexure_classroom_${CFG.currentSession}`;
const nameKey = "flexure_classroom_group_name";

function randomId(prefix = "local") {
  return `${prefix}_${Math.random().toString(36).slice(2)}_${Date.now().toString(36)}`;
}

function getLocalOwner() {
  let id = localStorage.getItem(localOwnerKey);
  if (!id) {
    id = randomId("owner");
    localStorage.setItem(localOwnerKey, id);
  }
  return id;
}

function uid() {
  return demoMode ? getLocalOwner() : currentUser?.uid;
}

function setMessage(el, text = "", kind = "") {
  el.textContent = text;
  el.classList.toggle("error", kind === "error");
  el.classList.toggle("success", kind === "success");
}

function fmt(value, digits = 2) {
  if (!Number.isFinite(value)) return "—";
  return Number(value).toLocaleString(undefined, {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits
  });
}

function formatLength(value) {
  if (!Number.isFinite(Number(value))) return "—";
  return Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function sci(value, digits = 2) {
  if (!Number.isFinite(value) || value === 0) return `${value}`;
  const exp = Math.floor(Math.log10(Math.abs(value)));
  const mant = value / 10 ** exp;
  const supers = String(exp)
    .replace(/-/g, "⁻")
    .replace(/0/g,"⁰").replace(/1/g,"¹").replace(/2/g,"²")
    .replace(/3/g,"³").replace(/4/g,"⁴").replace(/5/g,"⁵")
    .replace(/6/g,"⁶").replace(/7/g,"⁷").replace(/8/g,"⁸").replace(/9/g,"⁹");
  return `${mant.toFixed(digits)} × 10${supers}`;
}

function qValue() { return Number($("qSlider").value); }
function dValue() { return 10 ** Number($("dSlider").value); }

// Cantilever plate, fixed at x=0 and free at x=L, under q(x)=constant:
// w = (q x^2 / D) * (x^2/24 - Lx/6 + L^2/4)
function modelWcm(xCm, Lcm, q = qValue(), D = dValue()) {
  const x = xCm / 100;
  const L = Lcm / 100;
  const wM = (q * x * x / D) * (x * x / 24 - L * x / 6 + L * L / 4);
  return 100 * wM;
}

function maxWcm(Lcm, q = qValue(), D = dValue()) {
  const L = Lcm / 100;
  return 100 * q * L ** 4 / (8 * D);
}

function availableLengths() {
  return [...new Set(
    measurements
      .map(m => Number(m.Lcm))
      .filter(v => Number.isFinite(v) && v > 0)
      .map(v => Math.round(v * 1000) / 1000)
  )].sort((a, b) => a - b);
}

function hashColor(text) {
  let h = 0;
  for (let i = 0; i < text.length; i++) h = ((h << 5) - h + text.charCodeAt(i)) | 0;
  return COLORS[Math.abs(h) % COLORS.length];
}

function groupName() {
  return ($("groupName").value.trim() || "Unnamed group").slice(0, 32);
}

function classPasswordOk() {
  return $("toolPassword").value === CFG.classPassword;
}

function setupControls() {
  $("sessionBadge").textContent = CFG.currentSession;
  $("groupName").value = localStorage.getItem(nameKey) || "";

  const q = $("qSlider");
  q.min = CFG.qMin; q.max = CFG.qMax; q.step = CFG.qStep; q.value = CFG.initialQ;

  const d = $("dSlider");
  d.min = CFG.dExponentMin; d.max = CFG.dExponentMax; d.step = CFG.dExponentStep;
  d.value = Math.log10(CFG.initialD);

  renderTabs();
  updateModelLabels();
}

function renderTabs() {
  const tabs = $("lengthTabs");
  tabs.innerHTML = "";

  for (const L of availableLengths()) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = `tab ${Number(selectedLength) === Number(L) ? "active" : ""}`;
    btn.textContent = `L = ${formatLength(L)} cm`;
    btn.setAttribute("role", "tab");
    btn.setAttribute("aria-selected", Number(selectedLength) === Number(L) ? "true" : "false");
    btn.addEventListener("click", () => selectLength(L));
    tabs.appendChild(btn);
  }

  const all = document.createElement("button");
  all.type = "button";
  all.className = `tab ${selectedLength === "all" ? "active" : ""}`;
  all.textContent = "All lengths";
  all.setAttribute("role", "tab");
  all.setAttribute("aria-selected", selectedLength === "all" ? "true" : "false");
  all.addEventListener("click", () => selectLength("all"));
  tabs.appendChild(all);
}

function selectLength(L) {
  selectedLength = L;
  editingId = null;
  resetForm({ preserveLength: true });
  if (L !== "all") $("lInput").value = L;
  renderTabs();
  updateModelLabels();
  renderAll();
}

function updateModelLabels() {
  $("qValue").textContent = `${fmt(qValue(), 2)} N m⁻²`;
  $("dValue").textContent = `${sci(dValue(), 2)} N m`;

  if (selectedLength === "all") {
    $("metricL").textContent = "all";
    $("metricWmax").textContent = "—";
    $("xInput").removeAttribute("max");
  } else {
    $("metricL").textContent = `${formatLength(selectedLength)} cm`;
    $("metricWmax").textContent = `${fmt(maxWcm(Number(selectedLength)), 2)} cm`;
    $("xInput").max = selectedLength;
  }
}

function modelDataset(Lcm, color = MODEL_COLOR, label = "Model") {
  const pts = [];
  const n = 180;
  for (let i = 0; i <= n; i++) {
    const x = (Lcm * i) / n;
    pts.push({ x, y: modelWcm(x, Lcm) });
  }
  return {
    type: "line",
    label,
    data: pts,
    borderColor: color,
    backgroundColor: color,
    borderWidth: 2.5,
    pointRadius: 0,
    tension: 0,
    order: 10
  };
}

function measurementDatasetsForLength(Lcm) {
  const relevant = measurements.filter(m => Number(m.Lcm) === Number(Lcm));
  const groups = new Map();

  for (const m of relevant) {
    const key = `${m.ownerUid || "imported"}::${m.groupName || "Imported"}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(m);
  }

  return [...groups.entries()].map(([key, items]) => {
    const [owner, name] = key.split("::");
    const own = owner === uid();
    const color = own ? "#62E3D5" : hashColor(key);
    return {
      type: "scatter",
      label: own ? `${name} (you)` : name,
      data: items.sort((a,b) => a.xCm-b.xCm).map(m => ({ x: m.xCm, y: m.wCm, _id: m.id })),
      pointRadius: own ? 6 : 5,
      pointHoverRadius: 8,
      pointBackgroundColor: color,
      pointBorderColor: own ? "#FFFFFF" : BG,
      pointBorderWidth: own ? 1.5 : 1,
      order: 1
    };
  });
}

function allLengthsDatasets() {
  const datasets = [];
  availableLengths().forEach((L, i) => {
    const color = COLORS[i % COLORS.length];
    const pts = measurements
      .filter(m => Number(m.Lcm) === Number(L))
      .sort((a,b) => a.xCm-b.xCm)
      .map(m => ({ x: m.xCm, y: m.wCm }));

    datasets.push({
      type: "scatter",
      label: `Data L=${formatLength(L)} cm`,
      data: pts,
      pointRadius: 4.5,
      pointBackgroundColor: color,
      pointBorderColor: BG,
      pointBorderWidth: 1,
      order: 1
    });
    datasets.push(modelDataset(L, color, `Model L=${formatLength(L)} cm`));
  });
  return datasets;
}

function chartOptions() {
  const lengths = availableLengths();
  const typedL = Number($("lInput").value);
  const fallback = Number.isFinite(typedL) && typedL > 0 ? typedL : (CFG.emptyGraphLengthCm || 40);
  const maxL = selectedLength === "all"
    ? (lengths.length ? Math.max(...lengths) : fallback)
    : Number(selectedLength);

  return {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    parsing: false,
    interaction: { mode: "nearest", intersect: false },
    plugins: {
      legend: {
        labels: { color: MUTED, boxWidth: 16, boxHeight: 3, usePointStyle: false, font: { size: 11 } }
      },
      tooltip: {
        backgroundColor: "#172033",
        borderColor: GRID,
        borderWidth: 1,
        titleColor: "#EDF2F7",
        bodyColor: "#EDF2F7",
        callbacks: {
          label: (ctx) => `${ctx.dataset.label}: x=${fmt(ctx.parsed.x,1)} cm, w=${fmt(ctx.parsed.y,2)} cm`
        }
      }
    },
    scales: {
      x: {
        type: "linear",
        min: 0,
        max: maxL,
        title: { display: true, text: "x [cm] from fixed end", color: MUTED },
        ticks: { color: MUTED },
        grid: { color: GRID }
      },
      y: {
        reverse: true,
        beginAtZero: true,
        title: { display: true, text: "downward deflection w [cm]", color: MUTED },
        ticks: { color: MUTED },
        grid: { color: GRID }
      }
    }
  };
}

function renderChart() {
  const lengths = availableLengths();
  const datasets = selectedLength === "all"
    ? allLengthsDatasets()
    : [...measurementDatasetsForLength(selectedLength), modelDataset(Number(selectedLength))];

  const ctx = $("flexureChart");
  if (chart) chart.destroy();
  chart = new Chart(ctx, { type: "scatter", data: { datasets }, options: chartOptions() });

  const n = selectedLength === "all"
    ? measurements.length
    : measurements.filter(m => Number(m.Lcm) === Number(selectedLength)).length;
  $("pointCount").textContent = `${n} point${n === 1 ? "" : "s"}`;

  if (!lengths.length) {
    $("graphTitle").textContent = "No class measurements yet";
    $("graphSubtitle").textContent = "Enter L, x and w; the first L tab will appear automatically.";
  } else if (selectedLength === "all") {
    $("graphTitle").textContent = "All class measurements";
    $("graphSubtitle").textContent = "The same local q and D values are applied to every length.";
  } else {
    $("graphTitle").textContent = `Class measurements · L = ${formatLength(selectedLength)} cm`;
    $("graphSubtitle").textContent = "x is measured from the fixed end; downward deflection is positive.";
  }
}

function renderOwnTable() {
  const body = $("ownMeasurementsBody");
  body.innerHTML = "";
  const own = measurements
    .filter(m => m.ownerUid === uid())
    .sort((a,b) => a.Lcm-b.Lcm || a.xCm-b.xCm);

  if (!own.length) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td colspan="4" class="empty-row">No measurements yet.</td>`;
    body.appendChild(tr);
    return;
  }

  for (const m of own) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${formatLength(m.Lcm)}</td>
      <td>${fmt(m.xCm, 1)}</td>
      <td>${fmt(m.wCm, 2)}</td>
      <td class="actions">
        <button type="button" class="table-button edit">Edit</button>
        <button type="button" class="table-button delete">Delete</button>
      </td>`;
    tr.querySelector(".edit").addEventListener("click", () => startEdit(m.id));
    tr.querySelector(".delete").addEventListener("click", () => removeMeasurement(m.id));
    body.appendChild(tr);
  }
}

function renderAll() {
  const lengths = availableLengths();
  if (selectedLength !== "all" && !lengths.some(L => Number(L) === Number(selectedLength))) {
    selectedLength = "all";
  }
  renderTabs();
  updateModelLabels();
  renderChart();
  renderOwnTable();
}

function resetForm({ preserveLength = true } = {}) {
  editingId = null;
  if (!preserveLength) $("lInput").value = "";
  if (selectedLength !== "all") $("lInput").value = selectedLength;
  $("xInput").value = "";
  $("wInput").value = "";
  $("submitMeasurement").textContent = "Add point";
  $("cancelEdit").classList.add("hidden");
  setMessage($("formMessage"), "");
}

function startEdit(id) {
  const m = measurements.find(x => x.id === id && x.ownerUid === uid());
  if (!m) return;
  selectedLength = Number(m.Lcm);
  editingId = id;
  $("lInput").value = m.Lcm;
  $("xInput").value = m.xCm;
  $("wInput").value = m.wCm;
  $("submitMeasurement").textContent = "Update point";
  $("cancelEdit").classList.remove("hidden");
  renderTabs();
  updateModelLabels();
  renderChart();
  $("lInput").focus();
}

function validateMeasurement(Lcm, xCm, wCm) {
  if (!Number.isFinite(Lcm) || Lcm <= 0) return "Enter a positive plate length L.";
  if (!Number.isFinite(xCm) || !Number.isFinite(wCm)) return "Enter numeric L, x and w values.";
  if (xCm < 0 || xCm > Lcm) return `x must lie between 0 and ${formatLength(Lcm)} cm.`;
  if (Math.abs(wCm) > 1000) return "w looks implausibly large; check the sign/units.";
  return "";
}

async function upsertMeasurement(event) {
  event.preventDefault();
  if (!uid()) return setMessage($("formMessage"), "Authentication is not ready yet.", "error");

  const Lcm = Number($("lInput").value);
  const xCm = Number($("xInput").value);
  const wCm = Number($("wInput").value);
  const err = validateMeasurement(Lcm, xCm, wCm);
  if (err) return setMessage($("formMessage"), err, "error");

  const payload = {
    Lcm,
    xCm,
    wCm,
    groupName: groupName(),
    ownerUid: uid()
  };

  try {
    if (demoMode) {
      if (editingId) {
        const i = measurements.findIndex(m => m.id === editingId && m.ownerUid === uid());
        if (i >= 0) measurements[i] = { ...measurements[i], ...payload };
      } else {
        measurements.push({ id: randomId("m"), ...payload, createdAt: new Date().toISOString() });
      }
      saveLocalMeasurements();
    } else if (editingId) {
      await updateDoc(doc(db, "sessions", CFG.currentSession, "measurements", editingId), {
        Lcm, xCm, wCm, groupName: payload.groupName, updatedAt: serverTimestamp()
      });
    } else {
      await addDoc(collection(db, "sessions", CFG.currentSession, "measurements"), {
        ...payload,
        createdAt: serverTimestamp()
      });
    }

    selectedLength = Lcm;
    resetForm({ preserveLength: true });
    $("lInput").value = Lcm;
    if (demoMode) renderAll();
  } catch (e) {
    setMessage($("formMessage"), friendlyError(e), "error");
  }
}

async function removeMeasurement(id) {
  const m = measurements.find(x => x.id === id);
  if (!m || m.ownerUid !== uid()) return;
  if (!confirm(`Delete point L=${formatLength(m.Lcm)} cm, x=${m.xCm} cm, w=${m.wCm} cm?`)) return;

  try {
    if (demoMode) {
      measurements = measurements.filter(x => x.id !== id);
      saveLocalMeasurements();
      renderAll();
    } else {
      await deleteDoc(doc(db, "sessions", CFG.currentSession, "measurements", id));
    }
  } catch (e) {
    setMessage($("formMessage"), friendlyError(e), "error");
  }
}

function saveLocalMeasurements() {
  localStorage.setItem(localDataKey(), JSON.stringify(measurements));
}

function loadLocalMeasurements() {
  try { measurements = JSON.parse(localStorage.getItem(localDataKey()) || "[]"); }
  catch { measurements = []; }
}

async function saveGroupName() {
  const name = groupName();
  $("groupName").value = name;
  localStorage.setItem(nameKey, name);
  setMessage($("formMessage"), "Group name saved.", "success");

  const own = measurements.filter(m => m.ownerUid === uid() && m.groupName !== name);
  try {
    if (demoMode) {
      own.forEach(m => m.groupName = name);
      saveLocalMeasurements();
      renderAll();
    } else {
      for (const chunk of chunkArray(own, 400)) {
        const batch = writeBatch(db);
        chunk.forEach(m => batch.update(
          doc(db, "sessions", CFG.currentSession, "measurements", m.id),
          { groupName: name }
        ));
        await batch.commit();
      }
    }
  } catch (e) {
    setMessage($("formMessage"), friendlyError(e), "error");
  }
}

function downloadJson() {
  const payload = {
    format: "flexure-classroom-v2",
    session: CFG.currentSession,
    exportedAt: new Date().toISOString(),
    model: { q_N_m2: qValue(), D_N_m: dValue() },
    lengthsCm: availableLengths(),
    measurements: measurements.map(({id, ...m}) => ({ ...m, sourceId: id }))
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `flexure_${CFG.currentSession}.json`;
  a.click();
  URL.revokeObjectURL(a.href);
}

function chunkArray(arr, size) {
  const out = [];
  for (let i = 0; i < arr.length; i += size) out.push(arr.slice(i, i + size));
  return out;
}

async function clearSession({ silent = false } = {}) {
  if (demoMode) {
    measurements = [];
    saveLocalMeasurements();
    selectedLength = "all";
    renderAll();
    return;
  }

  for (const chunk of chunkArray(measurements, 400)) {
    const batch = writeBatch(db);
    chunk.forEach(m => batch.delete(doc(db, "sessions", CFG.currentSession, "measurements", m.id)));
    await batch.commit();
  }
  if (!silent) setMessage($("adminMessage"), "Session cleared.", "success");
}

async function importJson() {
  if (!classPasswordOk()) {
    return setMessage($("adminMessage"), "Incorrect classroom password.", "error");
  }

  const file = $("jsonFile").files?.[0];
  if (!file) return setMessage($("adminMessage"), "Choose a JSON file first.", "error");

  try {
    const parsed = JSON.parse(await file.text());
    const rows = Array.isArray(parsed) ? parsed : parsed.measurements;
    if (!Array.isArray(rows)) throw new Error("JSON does not contain a measurements array.");
    if ($("replaceOnImport").checked) await clearSession({ silent: true });

    const cleaned = rows.map((m, i) => ({
      Lcm: Number(m.Lcm),
      xCm: Number(m.xCm),
      wCm: Number(m.wCm),
      groupName: String(m.groupName || `Imported ${i+1}`).slice(0, 32),
      ownerUid: String(m.ownerUid || `imported_${i+1}`),
      imported: true
    })).filter(m =>
      Number.isFinite(m.Lcm) && m.Lcm > 0
      && Number.isFinite(m.xCm) && m.xCm >= 0 && m.xCm <= m.Lcm
      && Number.isFinite(m.wCm)
    );

    if (demoMode) {
      cleaned.forEach(m => measurements.push({
        id: randomId("import"), ...m, createdAt: new Date().toISOString()
      }));
      saveLocalMeasurements();
      renderAll();
    } else {
      for (const chunk of chunkArray(cleaned, 350)) {
        const batch = writeBatch(db);
        chunk.forEach(m => {
          const ref = doc(collection(db, "sessions", CFG.currentSession, "measurements"));
          batch.set(ref, { ...m, createdAt: serverTimestamp() });
        });
        await batch.commit();
      }
    }
    setMessage($("adminMessage"), `Imported ${cleaned.length} measurement(s).`, "success");
  } catch (e) {
    setMessage($("adminMessage"), friendlyError(e), "error");
  }
}

async function clearAllClicked() {
  if (!classPasswordOk()) {
    return setMessage($("adminMessage"), "Incorrect classroom password.", "error");
  }

  const confirmText = $("clearConfirm").value.trim();
  if (confirmText !== CFG.currentSession) {
    return setMessage($("adminMessage"), `Type “${CFG.currentSession}” exactly to confirm.`, "error");
  }
  if (!confirm(`Delete ALL measurements in ${CFG.currentSession}?`)) return;

  try {
    await clearSession();
    $("clearConfirm").value = "";
  } catch (e) {
    setMessage($("adminMessage"), friendlyError(e), "error");
  }
}

function friendlyError(e) {
  const msg = e?.message || String(e);
  return msg.replace(/^Firebase:\s*/i, "").replace(/\(auth\/[\w-]+\)\.?/g, "").trim();
}

function subscribeToMeasurements() {
  if (unsubscribeMeasurements) unsubscribeMeasurements();
  const ref = collection(db, "sessions", CFG.currentSession, "measurements");
  unsubscribeMeasurements = onSnapshot(ref, snap => {
    measurements = snap.docs.map(d => ({ id: d.id, ...d.data() }));
    renderAll();
    $("connectionBadge").textContent = "live · shared";
    $("connectionBadge").style.color = "#64D98B";
  }, err => {
    $("connectionBadge").textContent = "database error";
    $("connectionBadge").style.color = "#FF6B6B";
    setMessage($("formMessage"), friendlyError(err), "error");
  });
}

async function startFirebase() {
  try {
    const app = initializeApp(CFG.firebaseConfig);
    auth = getAuth(app);
    db = getFirestore(app);
    await setPersistence(auth, browserLocalPersistence);

    onAuthStateChanged(auth, async user => {
      currentUser = user;
      if (!user) {
        try { await signInAnonymously(auth); }
        catch (e) {
          $("connectionBadge").textContent = "auth error";
          setMessage($("formMessage"), friendlyError(e), "error");
        }
        return;
      }
      subscribeToMeasurements();
    });
  } catch (e) {
    demoMode = true;
    loadLocalMeasurements();
    $("connectionBadge").textContent = "local preview";
    setMessage($("formMessage"), `Firebase unavailable; using local preview. ${friendlyError(e)}`, "error");
    renderAll();
  }
}

function bindEvents() {
  $("qSlider").addEventListener("input", renderAll);
  $("dSlider").addEventListener("input", renderAll);
  $("measurementForm").addEventListener("submit", upsertMeasurement);
  $("cancelEdit").addEventListener("click", () => resetForm({ preserveLength: true }));
  $("saveGroupName").addEventListener("click", saveGroupName);
  $("downloadJson").addEventListener("click", downloadJson);
  $("instructorToggle").addEventListener("click", () => $("instructorPanel").classList.toggle("hidden"));
  $("importJson").addEventListener("click", importJson);
  $("clearAll").addEventListener("click", clearAllClicked);
  $("lInput").addEventListener("input", () => {
    if (selectedLength === "all" && measurements.length === 0) renderChart();
  });
}

setupControls();
bindEvents();

if (demoMode) {
  loadLocalMeasurements();
  $("connectionBadge").textContent = "local preview";
  renderAll();
} else {
  startFirebase();
}
