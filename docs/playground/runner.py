# -*- coding: utf-8 -*-
"""جسر ساحة التجربة: ينفّذ شيفرة «نون» داخل Pyodide ويبثّ ناتجها إلى الصفحة.

يُحزَم مع حزمة `noon` في noon.zip عند بناء الموقع (hooks/noon_docs.py)، فما
يعمل في المتصفّح هو المُفسِّر والمترجِم نفساهما لا نسخة منهما.
يُختبر في CPython العادي بـ tests/test_playground.py.
"""

import io
import json
import sys
import time

from noon import values
from noon.bytecode import disassemble as _disassemble
from noon.compiler import compile_source
from noon.errors import NoonError, NoonThrow
from noon.interpreter import Interpreter
from noon.vm import VM

OUTPUT_LIMIT = 200000        # حرف؛ ما بعده يُحذف حتى لا تتجمّد الصفحة
CHUNK = 4096
FLUSH_SECONDS = 0.05


class StreamingOutput:
    """يجمع ما يُطبع ويُرسله دفعات: كل ٤ ك.ب. أو كل ٥٠ م.ث.

    رسالة لكل `اطبع` تُغرق الصفحة حين يطبع البرنامج آلاف الأسطر؛ والانتظار
    حتى النهاية يُخفي تقدّم برنامج طويل. الدفعات تجمع الحسنيين.
    """

    def __init__(self, emit, limit=OUTPUT_LIMIT, clock=time.monotonic):
        self.emit = emit
        self.limit = limit
        self.clock = clock
        self.pending = []
        self.pending_size = 0
        self.sent = 0
        self.truncated = False
        self.last_flush = clock()

    def write(self, text):
        if self.truncated or not text:
            return
        room = self.limit - self.sent - self.pending_size
        if len(text) > room:
            text = text[:max(0, room)]
            self.truncated = True
        self.pending.append(text)
        self.pending_size += len(text)
        if (self.truncated or self.pending_size >= CHUNK
                or self.clock() - self.last_flush >= FLUSH_SECONDS):
            self.flush()

    def flush(self):
        if self.pending:
            chunk = "".join(self.pending)
            self.sent += self.pending_size
            self.pending = []
            self.pending_size = 0
            self.emit(chunk)
        self.last_flush = self.clock()


class EchoingInput(io.StringIO):
    """دخل من لوحة «الدخل» يُكتب ما يُقرأ منه في الناتج، كما يظهر في الطرفية.

    بدونه يلتصق نصّ السؤال بالسطر التالي: «الاسم: أهلًا يا هند».
    """

    def __init__(self, text, out):
        super().__init__(text)
        self.out = out

    def readline(self, *args):
        line = super().readline(*args)
        if line:
            self.out.write(line if line.endswith("\n") else line + "\n")
        return line


def _error(kind, message, line=None, col=None, text=None):
    return {"ok": False, "kind": kind, "message": message, "line": line, "col": col,
            "text": text or message}


def run(source, engine="vm", arabic_digits=False, stdin="", emit=None):
    """ينفّذ البرنامج ويُرجع قاموس النتيجة؛ الناتج يصل عبر `emit` أثناء التنفيذ."""
    out = StreamingOutput(emit or sys.stdout.write)
    runner = Interpreter(out=out) if engine == "tree" else VM(out=out)
    values.set_arabic_digits(bool(arabic_digits))
    previous_stdin = sys.stdin
    sys.stdin = EchoingInput(stdin or "", out)     # ما تقرؤه «اقرأ()»
    result = {"ok": True}
    start = time.perf_counter()
    try:
        runner.run(source)
    except NoonError as error:
        result = _error(error.kind, error.message, error.line, error.col, str(error))
    except NoonThrow as thrown:
        text = "قيمة مرميّة لم تُلتقط: %s" % runner.stringify(thrown.value)
        result = _error("قيمة مرميّة", text, thrown.line, None, text)
    except RecursionError:
        result = _error("خطأ تشغيل", "تجاوز عمق الاستدعاء")
    finally:
        out.flush()
        values.set_arabic_digits(False)
        sys.stdin = previous_stdin
    result["ms"] = round((time.perf_counter() - start) * 1000, 1)
    result["truncated"] = out.truncated
    result["engine"] = engine
    return result


def disassemble(source):
    """البايت-كود مقروءًا، أو الخطأ النحوي الذي منع الترجمة."""
    try:
        buffer = io.StringIO()
        _disassemble(compile_source(source), buffer)
        return {"ok": True, "text": buffer.getvalue()}
    except NoonError as error:
        return _error(error.kind, error.message, error.line, error.col, str(error))


# JSON لا كائنات Python، حتى لا يحتاج العامل إلى تحويل الوكلاء وتحريرهم

def run_json(source, engine, arabic_digits, stdin, emit):
    return json.dumps(run(source, engine, arabic_digits, stdin, emit), ensure_ascii=False)


def disassemble_json(source):
    return json.dumps(disassemble(source), ensure_ascii=False)
