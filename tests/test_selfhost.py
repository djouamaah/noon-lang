# -*- coding: utf-8 -*-
"""اختبارات «نون بنون»: مُفسِّر «نون» ومترجِمها المكتوبان بـ«نون» (selfhost/noon.noon).

- المُفسِّر الذاتي يطبع ما تطبعه الآلة حرفًا بحرف على المدوّنة كلها: الأمثلة،
  وبرامج `differential_cases.py`، وكل مثال في التوثيق.
- المترجِم الذاتي يُخرج لكل برنامج في المدوّنة ما يُخرجه noon/compiler.py
  تعليمةً تعليمة، وثابتًا ثابتًا بنوعه (٣ غير ٣٫٠)، وجدولًا جدولًا.
- وهو يترجم نفسه: المترجَم به يترجم مصدره ثانيةً فيُخرج الملف نفسه بايتًا بايتًا.

تعمل مع pytest، وتعمل وحدها أيضًا:  python tests/test_selfhost.py
"""

import glob
import io
import marshal
import os
import re
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for path in (ROOT, os.path.join(ROOT, "tests"), os.path.join(ROOT, "hooks")):
    if path not in sys.path:
        sys.path.insert(0, path)

from noon import builtins as B  # noqa: E402
from noon import bytecode, values  # noqa: E402
from noon.compiler import compile_source  # noqa: E402
from noon.errors import NoonError, NoonThrow  # noqa: E402
from noon.vm import VM  # noqa: E402

import differential_cases  # noqa: E402
import noon_docs  # noqa: E402

SELFHOST = os.path.join(ROOT, "selfhost", "noon.noon")
BATCH_SEPARATOR = chr(0) + "═══ نهاية البرنامج ═══"
FIELDS = ("name param_names required is_method is_script code lines consts names "
          "n_slots slot_names cell_params freevars handlers scope_cells entries").split()


def _read(path):
    with io.open(path, encoding="utf-8") as handle:
        return handle.read()


def _corpus():
    programs = [(os.path.basename(p), _read(p))
                for p in sorted(glob.glob(os.path.join(ROOT, "examples", "*.noon")))]
    programs += list(differential_cases.CASES.items())
    for page in sorted(glob.glob(os.path.join(ROOT, "docs", "**", "*.md"), recursive=True)):
        for line, code, _ in noon_docs.iter_snippets(_read(page)):
            programs.append(("%s:%d" % (os.path.relpath(page, ROOT), line), code))
    return programs


def _transcript(run):
    """ما يطبعه البرنامج، ثم الخطأ الذي أنهاه إن وُجد، كما يراه المستخدم."""
    buffer = io.StringIO()
    vm = VM(out=buffer)
    try:
        run(vm)
    except NoonError as error:
        buffer.write("%s\n" % error)
    except NoonThrow as thrown:
        buffer.write("قيمة مرميّة لم تُلتقط: %s\n" % vm.stringify(thrown.value))
    finally:
        values.set_arabic_digits(False)
    return buffer.getvalue()


def _run_selfhost(args, source=None):
    """يشغّل selfhost/noon.noon (أو مصدرًا بديلًا) بالآلة ويُرجع ما طبعه."""
    saved = list(B.PROGRAM_ARGS)
    B.PROGRAM_ARGS[:] = args
    buffer = io.StringIO()
    try:
        VM(out=buffer).run(_read(SELFHOST) if source is None else source)
    finally:
        B.PROGRAM_ARGS[:] = saved
        values.set_arabic_digits(False)
    return buffer.getvalue()


class _Workspace:
    def __init__(self, programs):
        self.dir = tempfile.mkdtemp(prefix="noon-selfhost-")
        self.paths = []
        for index, (_, source) in enumerate(programs):
            path = os.path.join(self.dir, "p%03d.noon" % index)
            with io.open(path, "w", encoding="utf-8") as handle:
                handle.write(source)
            self.paths.append(path)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        shutil.rmtree(self.dir, ignore_errors=True)


def _typed(value):
    """للمقارنة: القوائم والصفوف سواء، أمّا ٣ و٣٫٠ وصحيح فمختلفة."""
    if isinstance(value, (list, tuple)):
        return [_typed(v) for v in value]
    return (type(value).__name__, value)


def _difference(want, got, where="البرنامج"):
    """أوّل اختلاف بين بنيتَي دالتين مُترجَمتين (ترتيب _to_data)، أو None."""
    for index, field in enumerate(FIELDS):
        a, b = want[index], got[index]
        if field != "consts":
            if _typed(a) != _typed(b):
                return "%s.%s: %r ≠ %r" % (where, field, a, b)
            continue
        if len(a) != len(b):
            return "%s.consts: %d ثابتًا ≠ %d" % (where, len(a), len(b))
        for j, ((kind_a, va), (kind_b, vb)) in enumerate(zip(a, b)):
            if kind_a != kind_b:
                return "%s.consts[%d]: %s ≠ %s" % (where, j, kind_a, kind_b)
            if kind_a == "fn":
                found = _difference(va, vb, "%s/%s" % (where, va[0]))
                if found:
                    return found
            elif _typed(va) != _typed(vb):
                return "%s.consts[%d]: %r ≠ %r" % (where, j, va, vb)
    return None


def _compile_with_selfhost(programs, source=None):
    """يترجم البرامج بالمترجِم الذاتي؛ يُرجع لكل برنامج (رسالته، بايتات ملفه أو None)."""
    with _Workspace(programs) as work:
        output = _run_selfhost(["--ترجم-دفعة", work.dir] + work.paths, source)
        messages = output.splitlines()
        assert len(messages) == len(programs), output[-500:]
        results = []
        for index, message in enumerate(messages):
            path = os.path.join(work.dir, "%d.noonc" % index)
            blob = None
            if os.path.exists(path):
                with open(path, "rb") as handle:
                    blob = handle.read()
            results.append((message, blob))
        return results


def _mismatches(programs, results):
    bad = []
    for (name, source), (message, blob) in zip(programs, results):
        try:
            want = compile_source(source)
        except NoonError as error:
            if message != str(error):
                bad.append("%s: خطأ الأصل «%s» وبنون «%s»" % (name, error, message))
            continue
        if blob is None:
            bad.append("%s: %s" % (name, message))
            continue
        found = _difference(marshal.loads(marshal.dumps(bytecode._to_data(want))),
                            marshal.loads(blob[len(bytecode.MAGIC) + 1:]))
        if found:
            bad.append("%s: %s" % (name, found))
    return bad


# ——————————————— المُفسِّر الذاتي ———————————————

def test_selfhost_interpreter_matches_the_vm_on_the_corpus():
    programs = _corpus()
    with _Workspace(programs) as work:
        outputs = _run_selfhost(["--دفعة"] + work.paths).split(BATCH_SEPARATOR + "\n")
    assert len(outputs) == len(programs) + 1
    bad = [name for (name, source), got in zip(programs, outputs)
           if got != _transcript(lambda vm: vm.run(source))]
    assert not bad, "المُفسِّر الذاتي يختلف في: %s" % "، ".join(bad)


def test_selfhost_knows_every_host_builtin():
    source = _read(SELFHOST)
    table = source[source.index("ثابت الدوال_المدمجة = {"):]
    table = table[:table.index("\n}")]
    names = set(re.findall(r'"([^"]+)":', table))
    assert names == set(B.GLOBALS), "ناقص: %s، زائد: %s" % (
        sorted(set(B.GLOBALS) - names), sorted(names - set(B.GLOBALS)))


# ——————————————— المترجِم الذاتي ———————————————

def test_selfhost_compiler_matches_the_compiler_on_the_corpus():
    programs = _corpus() + [("selfhost/noon.noon", _read(SELFHOST))]
    results = _compile_with_selfhost(programs)
    bad = _mismatches(programs, results)
    assert not bad, "\n".join(bad[:10])
    # والملفات تعمل: تطبع ما يطبعه البرنامج مُترجَمًا بالمترجِم الأصلي
    for (name, source), (_, blob) in zip(programs[:-1], results):
        if blob is not None:
            assert _transcript(lambda vm: vm.execute(bytecode.loads(blob))) == \
                _transcript(lambda vm: vm.run(source)), name


def test_selfhost_compiler_reaches_a_fixpoint():
    work = tempfile.mkdtemp(prefix="noon-bootstrap-")
    try:
        stage1 = os.path.join(work, "stage1.noonc")
        stage2 = os.path.join(work, "stage2.noonc")
        # المرحلة ١: المترجِم الذاتي (مُفسَّرًا من مصدره) يترجم نفسه
        _run_selfhost(["--ترجم", SELFHOST, stage1])
        with open(stage1, "rb") as handle:
            compiled_compiler = bytecode.loads(handle.read())
        # المرحلة ٢: المترجِم المُترجَم يترجم المصدر نفسه
        saved = list(B.PROGRAM_ARGS)
        B.PROGRAM_ARGS[:] = ["--ترجم", SELFHOST, stage2]
        try:
            VM(out=io.StringIO()).execute(compiled_compiler)
        finally:
            B.PROGRAM_ARGS[:] = saved
        with open(stage1, "rb") as a, open(stage2, "rb") as b:
            assert a.read() == b.read(), "المرحلتان ١ و٢ مختلفتان"
    finally:
        shutil.rmtree(work, ignore_errors=True)


def test_the_comparison_catches_a_planted_bug():
    """اختبار الاختبار: مترجِم ينسى الفرق بين ٣ و٣٫٠ يجب أن يُكشف."""
    source = _read(SELFHOST)
    line = '    إذا (صنف_ == "عدد" و عشري) { صنف_ = "عشري" }\n'
    assert source.count(line) == 1
    programs = [("أعداد", "اطبع(٣، ٣٫٠)")]
    assert not _mismatches(programs, _compile_with_selfhost(programs))
    assert _mismatches(programs, _compile_with_selfhost(programs, source.replace(line, "")))


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    tests = [(n, f) for n, f in sorted(globals().items())
             if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print("✓ %s" % name)
        except Exception as error:               # noqa: BLE001
            failed += 1
            print("✗ %s\n    %s" % (name, error))
    print("\n%d/%d اختبارًا ناجحًا" % (len(tests) - failed, len(tests)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
