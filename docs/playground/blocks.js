// محرّر كتل «نون»: Blockly لتركيب الكتل، والشيفرة الناتجة تُعرض وتُشغَّل بعامل ساحة
// التجربة نفسه (Python في المتصفّح مع حزمة «نون» الحقيقية).

import { createNoonBlocks, toolboxBlockTypes } from "./noon-blocks.js";
import { encodeShare, decodeShare } from "./share.js";
import EXAMPLES from "./blocks-examples.js";

const Blockly = window.Blockly;
const $ = (id) => document.getElementById(id);
const STORAGE_KEY = "noon-blocks:workspace";
const MEDIA = "https://cdn.jsdelivr.net/npm/blockly@13.3.0/media/";

const { generator, toolbox, themes } = createNoonBlocks(Blockly);
const dark = window.matchMedia("(prefers-color-scheme: dark)");

const workspace = Blockly.inject("workspace", {
  toolbox,
  rtl: true,
  renderer: "zelos",
  theme: dark.matches ? themes.dark : themes.light,
  media: MEDIA,
  sounds: false,
  trashcan: true,
  zoom: { controls: true, wheel: true, startScale: 0.8, maxScale: 2, minScale: 0.4, scaleSpeed: 1.15 },
  grid: { spacing: 28, length: 3, colour: "rgba(128, 128, 128, 0.22)", snap: true },
  move: { scrollbars: true, drag: true, wheel: false },
});
dark.addEventListener("change", () => workspace.setTheme(dark.matches ? themes.dark : themes.light));
new ResizeObserver(() => Blockly.svgResize(workspace)).observe($("workspace"));

const output = $("output");
const codeView = $("code");
const timing = $("timing");
let code = "";
let worker = null;
let workerReady = false;
let pythonVersion = "";
let running = null;
let nextId = 1;

// ——— التخزين: راحة لكل زائر، والصفحة تعمل بدونه ———

function load(key) {
  try { return window.localStorage.getItem(key); } catch { return null; }
}
function save(key, value) {
  try { window.localStorage.setItem(key, value); } catch { /* خاصّ أو ممنوع */ }
}

// ——— الشيفرة ———

function generate() {
  try {
    code = generator.workspaceToCode(workspace);
  } catch (error) {
    code = "";
    console.error(error);
  }
  showCode();
}

function showCode(errorLine = null) {
  codeView.textContent = "";
  if (!code.trim()) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = "اسحب كتلًا من الصندوق إلى المساحة لتظهر شيفرتها هنا.";
    codeView.append(empty);
    return;
  }
  code.split("\n").forEach((text, index) => {
    const line = document.createElement("span");
    line.className = "line" + (index + 1 === errorLine ? " error" : "");
    line.textContent = text || " ";
    codeView.append(line);
  });
}

let saveTimer = null;
workspace.addChangeListener((event) => {
  if (event.isUiEvent) return;
  generate();
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => {
    save(STORAGE_KEY, JSON.stringify(Blockly.serialization.workspaces.save(workspace)));
  }, 300);
});

function loadXml(xml) {
  workspace.clear();
  Blockly.Xml.domToWorkspace(Blockly.utils.xml.textToDom(xml), workspace);
  workspace.scrollCenter();
}

function loadState(state) {
  workspace.clear();
  Blockly.serialization.workspaces.load(state, workspace);
}

// ——— الحالة ———

function setStatus(text, kind = "") {
  const status = $("status");
  status.textContent = text;
  status.dataset.kind = kind;
}

function toast(text) {
  const box = $("toast");
  box.textContent = text;
  box.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { box.hidden = true; }, 2200);
}

function showTab(name) {
  for (const tab of document.querySelectorAll("[role=tab]")) {
    const selected = tab.dataset.tab === name;
    tab.setAttribute("aria-selected", String(selected));
    $(tab.getAttribute("aria-controls")).hidden = !selected;
  }
}

// ——— العامل: worker.js نفسه الذي تستعمله ساحة التجربة ———

function startWorker() {
  workerReady = false;
  $("run").disabled = true;
  worker = new Worker(new URL("./worker.js", import.meta.url), { type: "module" });
  worker.onmessage = ({ data }) => {
    switch (data.type) {
      case "status":
        setStatus(data.text, "loading");
        break;
      case "ready":
        workerReady = true;
        pythonVersion = data.python;
        $("run").disabled = false;
        setStatus("جاهز · Python " + data.python, "ready");
        break;
      case "fatal":
        setStatus("تعذّر تحميل Python: " + data.text, "error");
        break;
      case "output":
        if (running && data.id === running.id) appendOutput(data.text);
        break;
      case "done":
        if (running && data.id === running.id) finishRun(data.result);
        break;
    }
  };
  worker.onerror = (event) => setStatus("خطأ في العامل: " + (event.message || "غير معروف"), "error");
}

function appendOutput(text) {
  const atBottom = output.scrollHeight - output.scrollTop - output.clientHeight < 40;
  output.append(text);
  if (atBottom) output.scrollTop = output.scrollHeight;
}

function run() {
  if (running) return;
  if (!workerReady) {
    setStatus("لم يجهز Python بعد؛ انتظر لحظة", "loading");
    return;
  }
  generate();
  showTab("output");
  output.textContent = "";
  timing.textContent = "";
  if (!code.trim()) {
    const note = document.createElement("span");
    note.className = "note";
    note.textContent = "لا كتل لتشغيلها بعد: اسحب «اطبع» من «الإخراج والإدخال».";
    output.append(note);
    return;
  }
  running = { id: nextId++, started: performance.now() };
  $("run").hidden = true;
  $("stop").hidden = false;
  setStatus("يعمل…", "running");
  worker.postMessage({ type: "run", id: running.id, code, engine: "vm", arabicDigits: false,
    stdin: $("stdin").value });
}

function finishRun(result) {
  const elapsed = performance.now() - running.started;
  running = null;
  $("run").hidden = false;
  $("stop").hidden = true;

  if (result.truncated) {
    const note = document.createElement("span");
    note.className = "note";
    note.textContent = "\n… اقتُطع الناتج بعد ٢٠٠ ألف حرف\n";
    output.append(note);
  }
  if (!result.ok) {
    const error = document.createElement("div");
    error.className = "error";
    error.textContent = result.text;
    if (result.line) {
      const go = document.createElement("button");
      go.className = "go-line";
      go.textContent = "أرِني السطر " + result.line + " في الشيفرة";
      go.onclick = () => { showCode(result.line); showTab("code"); };
      error.append(go);
    }
    output.append(error);
  } else if (!output.textContent) {
    const note = document.createElement("span");
    note.className = "note";
    note.textContent = "انتهى البرنامج دون أن يطبع شيئًا.";
    output.append(note);
  }
  showCode(result.ok ? null : result.line);
  timing.textContent = (result.ok ? "اكتمل" : "توقّف بخطأ") + " في " + Math.round(result.ms ?? elapsed) + " م.ث";
  setStatus(result.ok ? "جاهز · Python " + pythonVersion : "انتهى بخطأ", result.ok ? "ready" : "error");
}

function stop() {
  if (!running) return;
  worker.terminate();
  running = null;
  $("run").hidden = false;
  $("stop").hidden = true;
  const note = document.createElement("div");
  note.className = "error";
  note.textContent = "أُوقف التنفيذ.";
  output.append(note);
  startWorker();
}

// ——— الأزرار ———

function fillExamples() {
  const select = $("examples");
  for (const example of EXAMPLES) {
    const option = document.createElement("option");
    option.value = example.name;
    option.textContent = example.title;
    select.append(option);
  }
  select.onchange = () => {
    const example = EXAMPLES.find((e) => e.name === select.value);
    if (example) {
      loadXml(example.xml);
      if (example.stdin) $("stdin").value = example.stdin;
      window.history.replaceState(null, "", window.location.pathname);
    }
    select.value = "";
  };
}

async function share() {
  const state = JSON.stringify(Blockly.serialization.workspaces.save(workspace));
  const url = new URL(window.location.href);
  url.hash = "blocks=" + await encodeShare(state);
  window.history.replaceState(null, "", url);
  try {
    await navigator.clipboard.writeText(url.href);
    toast("نُسخ رابط الكتل");
  } catch {
    toast("الرابط في شريط العنوان");
  }
}

async function openInPlayground(event) {
  event.preventDefault();
  generate();
  window.location.href = "index.html" + (code.trim() ? "#code=" + await encodeShare(code + "\n") : "");
}

function clearAll() {
  if (workspace.getAllBlocks(false).length === 0) return;
  if (!window.confirm("أتمسح كل الكتل؟ (يمكن التراجع بـ Ctrl + Z)")) return;
  workspace.clear();
}

async function stateFromHash() {
  const match = /^#blocks=([A-Za-z0-9_-]+)$/.exec(window.location.hash);
  if (!match) return null;
  try { return JSON.parse(await decodeShare(match[1])); } catch { return null; }
}

// فحص ذاتي يُنادى من أدوات المطوّر أو الاختبار: كل كتلة في الصندوق لها مترجِم
window.noonBlocks = {
  workspace, generator, examples: EXAMPLES,
  missingGenerators: () => toolboxBlockTypes().filter((type) => !generator.forBlock[type]),
  codeFor(xml) { loadXml(xml); generate(); return code; },
};

// ——— البدء ———

async function init() {
  fillExamples();
  $("run").onclick = run;
  $("stop").onclick = stop;
  $("share").onclick = share;
  $("clear").onclick = clearAll;
  $("to-playground").onclick = openInPlayground;
  for (const tab of document.querySelectorAll("[role=tab]")) tab.onclick = () => showTab(tab.dataset.tab);
  document.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") { event.preventDefault(); run(); }
    if (event.key === "Escape" && running) stop();
  });
  window.addEventListener("hashchange", async () => {
    const shared = await stateFromHash();
    if (shared) loadState(shared);
  });

  const shared = await stateFromHash();
  const saved = load(STORAGE_KEY);
  try {
    if (shared) loadState(shared);
    else if (saved) loadState(JSON.parse(saved));
    else loadXml(EXAMPLES[0].xml);
  } catch {
    loadXml(EXAMPLES[0].xml);
  }
  generate();
  startWorker();
}

init();
