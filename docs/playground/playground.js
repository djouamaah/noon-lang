// ساحة «نون»: محرّر CodeMirror، وتشغيل في عامل منفصل، ومشاركة الشيفرة برابط.

import { EditorState, StateEffect, StateField, Prec } from "@codemirror/state";
import {
  EditorView, keymap, lineNumbers, highlightActiveLine, highlightActiveLineGutter,
  drawSelection, Decoration,
} from "@codemirror/view";
import { history, historyKeymap, defaultKeymap, indentWithTab } from "@codemirror/commands";
import { syntaxHighlighting, bracketMatching, indentOnInput } from "@codemirror/language";
import { search, searchKeymap, highlightSelectionMatches } from "@codemirror/search";
import { noonLanguage, noonHighlight, noonIndent } from "./noon-mode.js";
import EXAMPLES from "./examples.js";

const $ = (id) => document.getElementById(id);
const STORAGE_KEY = "noon-playground:code";
const SETTINGS_KEY = "noon-playground:settings";

// ——— التخزين المحلّي: راحة لكل زائر، والصفحة تعمل بدونه ———

function load(key) {
  try { return window.localStorage.getItem(key); } catch { return null; }
}
function save(key, value) {
  try { window.localStorage.setItem(key, value); } catch { /* خاصّ أو ممنوع */ }
}

// ——— المشاركة: deflate خام + base64 للروابط، مثل encode_share في الخطّاف ———

function toBase64Url(bytes) {
  let binary = "";
  for (let i = 0; i < bytes.length; i += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  }
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}
function fromBase64Url(text) {
  const binary = atob(text.replace(/-/g, "+").replace(/_/g, "/") + "===".slice((text.length + 3) % 4));
  return Uint8Array.from(binary, (c) => c.charCodeAt(0));
}
async function pipe(bytes, transform) {
  const stream = new Blob([bytes]).stream().pipeThrough(transform);
  return new Uint8Array(await new Response(stream).arrayBuffer());
}
export async function encodeShare(code) {
  return toBase64Url(await pipe(new TextEncoder().encode(code), new CompressionStream("deflate-raw")));
}
export async function decodeShare(token) {
  return new TextDecoder().decode(await pipe(fromBase64Url(token), new DecompressionStream("deflate-raw")));
}

async function codeFromHash() {
  const match = /^#code=([A-Za-z0-9_-]+)$/.exec(window.location.hash);
  if (!match) return null;
  try { return await decodeShare(match[1]); } catch { return null; }
}

// ——— تمييز سطر الخطأ ———

const setErrorLine = StateEffect.define();
const errorLine = StateField.define({
  create: () => Decoration.none,
  update(value, tr) {
    value = value.map(tr.changes);
    for (const effect of tr.effects) {
      if (!effect.is(setErrorLine)) continue;
      if (effect.value == null) return Decoration.none;
      const line = tr.state.doc.line(Math.min(Math.max(1, effect.value), tr.state.doc.lines));
      return Decoration.set([Decoration.line({ class: "cm-noon-error" }).range(line.from)]);
    }
    return tr.docChanged ? Decoration.none : value;
  },
  provide: (field) => EditorView.decorations.from(field),
});

const arabicPhrases = EditorState.phrases.of({
  "Find": "ابحث", "Replace": "استبدل", "next": "التالي", "previous": "السابق",
  "all": "الكل", "match case": "طابِق الحالة", "regexp": "تعبير نمطي",
  "by word": "كلمة كاملة", "replace": "استبدل", "replace all": "استبدل الكل",
  "close": "أغلق", "Go to line": "اذهب إلى السطر", "go": "اذهب",
});

// ——— الحالة ———

const settings = Object.assign({ engine: "vm", digits: false },
  (() => { try { return JSON.parse(load(SETTINGS_KEY)) || {}; } catch { return {}; } })());

let worker = null;
let workerReady = false;
let running = null;           // { id, started }
let nextId = 1;
let pythonVersion = "";

const output = $("output");
const statusText = $("status");
const timing = $("timing");

function setStatus(text, kind = "") {
  statusText.textContent = text;
  statusText.dataset.kind = kind;
}

// ——— المحرّر ———

const view = new EditorView({
  parent: $("editor"),
  state: EditorState.create({
    doc: "",
    extensions: [
      lineNumbers(),
      highlightActiveLineGutter(),
      highlightActiveLine(),
      drawSelection(),
      history(),
      indentOnInput(),
      bracketMatching(),
      search({ top: true }),
      highlightSelectionMatches(),
      noonLanguage,
      noonIndent,
      syntaxHighlighting(noonHighlight),
      errorLine,
      arabicPhrases,
      EditorView.perLineTextDirection.of(true),
      EditorView.lineWrapping,
      EditorView.contentAttributes.of({ "aria-label": "شيفرة «نون»", spellcheck: "false" }),
      Prec.high(keymap.of([
        { key: "Mod-Enter", run: () => { run(); return true; } },
        { key: "Mod-s", run: () => { share(); return true; } },
        { key: "Escape", run: () => { if (running) { stop(); return true; } return false; } },
      ])),
      keymap.of([...defaultKeymap, ...historyKeymap, ...searchKeymap, indentWithTab]),
      EditorView.updateListener.of((update) => {
        if (update.docChanged) save(STORAGE_KEY, update.state.doc.toString());
      }),
    ],
  }),
});

function setCode(code) {
  view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: code },
                  selection: { anchor: 0 }, effects: setErrorLine.of(null) });
}

function jumpToLine(number) {
  const line = view.state.doc.line(Math.min(Math.max(1, number), view.state.doc.lines));
  view.dispatch({ selection: { anchor: line.from }, effects: [setErrorLine.of(number),
                  EditorView.scrollIntoView(line.from, { y: "center" })] });
  view.focus();
}

// ——— العامل ———

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
      case "disassembly":
        showDisassembly(data.result);
        break;
    }
  };
  worker.onerror = (event) => setStatus("خطأ في العامل: " + (event.message || "غير معروف"), "error");
}

// ——— التشغيل ———

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
  showTab("output");
  output.textContent = "";
  timing.textContent = "";
  view.dispatch({ effects: setErrorLine.of(null) });
  running = { id: nextId++, started: performance.now() };
  $("run").hidden = true;
  $("stop").hidden = false;
  setStatus("يعمل…", "running");
  worker.postMessage({
    type: "run", id: running.id, code: view.state.doc.toString(),
    engine: settings.engine, arabicDigits: settings.digits, stdin: $("stdin").value,
  });
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
      go.textContent = "اذهب إلى السطر " + result.line;
      go.onclick = () => jumpToLine(result.line);
      error.append(go);
      jumpToLine(result.line);
    }
    output.append(error);
  } else if (!output.textContent) {
    const note = document.createElement("span");
    note.className = "note";
    note.textContent = "انتهى البرنامج دون أن يطبع شيئًا.";
    output.append(note);
  }
  const engine = settings.engine === "tree" ? "المُفسِّر الشجري" : "الآلة الافتراضية";
  timing.textContent = (result.ok ? "اكتمل" : "توقّف بخطأ") + " في " +
    Math.round(result.ms ?? elapsed) + " م.ث · " + engine;
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
  startWorker();                     // Python يُعاد تحميله من ذاكرة المتصفّح
}

// ——— البايت-كود ———

function showDisassembly(result) {
  const box = $("bytecode");
  box.textContent = result.ok ? result.text : result.text;
  box.classList.toggle("has-error", !result.ok);
}

function requestDisassembly() {
  if (!workerReady) {
    $("bytecode").textContent = "لم يجهز Python بعد.";
    return;
  }
  $("bytecode").textContent = "…";
  worker.postMessage({ type: "disassemble", id: nextId++, code: view.state.doc.toString() });
}

// ——— الألسنة ———

function showTab(name) {
  for (const tab of document.querySelectorAll("[role=tab]")) {
    const selected = tab.dataset.tab === name;
    tab.setAttribute("aria-selected", String(selected));
    $(tab.getAttribute("aria-controls")).hidden = !selected;
  }
  if (name === "bytecode") requestDisassembly();
}

// ——— المشاركة ———

let toastTimer = null;
function toast(text) {
  const box = $("toast");
  box.textContent = text;
  box.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { box.hidden = true; }, 2600);
}

async function share() {
  const token = await encodeShare(view.state.doc.toString());
  const url = window.location.href.split("#")[0] + "#code=" + token;
  window.history.replaceState(null, "", "#code=" + token);
  try {
    await navigator.clipboard.writeText(url);
    toast("نُسخ رابط الشيفرة");
  } catch {
    window.prompt("انسخ هذا الرابط:", url);
  }
}

// ——— الأمثلة والإعدادات ———

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
      setCode(example.code);
      window.history.replaceState(null, "", window.location.pathname);
      view.focus();
    }
    select.value = "";
  };
}

function bindSettings() {
  $("engine").value = settings.engine;
  $("digits").checked = settings.digits;
  $("engine").onchange = () => { settings.engine = $("engine").value; save(SETTINGS_KEY, JSON.stringify(settings)); };
  $("digits").onchange = () => { settings.digits = $("digits").checked; save(SETTINGS_KEY, JSON.stringify(settings)); };
}

// ——— البدء ———

async function init() {
  fillExamples();
  bindSettings();
  $("run").onclick = run;
  $("stop").onclick = stop;
  $("share").onclick = share;
  for (const tab of document.querySelectorAll("[role=tab]")) {
    tab.onclick = () => showTab(tab.dataset.tab);
  }
  window.addEventListener("hashchange", async () => {
    const shared = await codeFromHash();
    if (shared != null) setCode(shared);
  });

  const shared = await codeFromHash();
  setCode(shared ?? load(STORAGE_KEY) ?? EXAMPLES.find((e) => e.name === "hello")?.code ?? "");
  view.focus();
  startWorker();
}

init();
