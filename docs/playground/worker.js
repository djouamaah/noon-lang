// عامل ساحة التجربة: يحمّل Python (Pyodide) وحزمة «نون» الحقيقية، وينفّذ الشيفرة
// بعيدًا عن واجهة الصفحة فلا تتجمّد. الإيقاف يكون بإنهاء العامل كلّه.

import { loadPyodide } from "https://cdn.jsdelivr.net/npm/pyodide@314.0.7/pyodide.mjs";

const PYODIDE_URL = "https://cdn.jsdelivr.net/npm/pyodide@314.0.7/";
const post = (message) => self.postMessage(message);

let runner = null;

const ready = (async () => {
  post({ type: "status", text: "جارٍ تحميل Python…" });
  const pyodide = await loadPyodide({ indexURL: PYODIDE_URL });

  post({ type: "status", text: "جارٍ تحميل «نون»…" });
  const response = await fetch(new URL("noon.zip", import.meta.url));
  if (!response.ok) throw new Error("تعذّر تحميل noon.zip (" + response.status + ")");
  pyodide.unpackArchive(await response.arrayBuffer(), "zip", { extractDir: "/home/pyodide/noon" });
  pyodide.runPython('import sys; sys.path.insert(0, "/home/pyodide/noon")');
  runner = pyodide.pyimport("runner");

  post({ type: "ready", python: pyodide.runPython("import sys; sys.version.split()[0]") });
})().catch((error) => post({ type: "fatal", text: String(error && error.message || error) }));

self.onmessage = async ({ data }) => {
  await ready;
  if (!runner) return;
  try {
    if (data.type === "run") {
      const emit = (text) => post({ type: "output", id: data.id, text });
      const json = runner.run_json(data.code, data.engine, data.arabicDigits, data.stdin, emit);
      post({ type: "done", id: data.id, result: JSON.parse(json) });
    } else if (data.type === "disassemble") {
      post({ type: "disassembly", id: data.id, result: JSON.parse(runner.disassemble_json(data.code)) });
    }
  } catch (error) {
    // خطأ في Python نفسه لا في برنامج المستخدم: يُعرض كما هو ليُبلَّغ عنه
    post({ type: "done", id: data.id, result: {
      ok: false, kind: "خطأ داخلي", text: "خطأ داخلي في الساحة:\n" + String(error && error.message || error),
    } });
  }
};
