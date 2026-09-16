# -*- coding: utf-8 -*-
"""اختبارات المترجم والآلة الافتراضية.

الأساس اختبار تفاضلي: المُفسِّر هو المرجع، والآلة يجب أن تطابقه حرفًا بحرف
على اختبارات اللغة كلها، وعلى كل مثال في التوثيق، وعلى برامج
`differential_cases.py` الصعبة. ثم اختبارات لما لا يملكه المُفسِّر: ملفات
‎.noonc، ومُفكِّك التجميع، والتعاود العميق.

تعمل مع pytest، وتعمل وحدها أيضًا:  python tests/test_vm.py
"""

import glob
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for path in (ROOT, os.path.join(ROOT, "tests"), os.path.join(ROOT, "hooks")):
    if path not in sys.path:
        sys.path.insert(0, path)

from noon import bytecode, values  # noqa: E402
from noon.compiler import compile_source  # noqa: E402
from noon.errors import NoonError, NoonRuntimeError, NoonThrow  # noqa: E402
from noon.interpreter import Interpreter  # noqa: E402
from noon.vm import VM  # noqa: E402

import differential_cases  # noqa: E402


def _transcript(engine, source):
    """ما يطبعه البرنامج، ثم الخطأ الذي أنهاه إن وُجد، كما يراه المستخدم."""
    buffer = io.StringIO()
    runner = engine(out=buffer)
    try:
        runner.run(source)
    except NoonError as error:
        buffer.write("%s\n" % error)
    except NoonThrow as thrown:
        buffer.write("قيمة مرميّة لم تُلتقط: %s\n" % runner.stringify(thrown.value))
    finally:
        values.set_arabic_digits(False)
    return buffer.getvalue()


def _assert_same(name, source):
    expected = _transcript(Interpreter, source)
    actual = _transcript(VM, source)
    assert actual == expected, "المحرّكان مختلفان في «%s»\n  المُفسِّر: %r\n  الآلة:    %r" % (
        name, expected, actual)


# ——————————————— التطابق مع المُفسِّر ———————————————

def test_language_suite_passes_on_the_vm():
    import test_noon
    tests = [(n, f) for n, f in sorted(vars(test_noon).items())
             if n.startswith("test_") and callable(f)]
    previous, test_noon.ENGINE = test_noon.ENGINE, VM
    try:
        for name, fn in tests:
            try:
                fn()
            except Exception as error:
                raise AssertionError("%s فشل على الآلة: %s" % (name, error))
    finally:
        test_noon.ENGINE = previous
    assert len(tests) > 40


def test_hard_programs_behave_identically():
    assert len(differential_cases.CASES) > 40
    for name, source in differential_cases.CASES.items():
        _assert_same(name, source)


def test_every_docs_snippet_behaves_identically():
    try:
        import noon_docs
    except ImportError:                          # الخطّاف يحتاج حزمة regex
        return
    count = 0
    for page in sorted(glob.glob(os.path.join(ROOT, "docs", "**", "*.md"), recursive=True)):
        with io.open(page, encoding="utf-8") as handle:
            markdown = handle.read()
        for line, code, _ in noon_docs.iter_snippets(markdown):
            _assert_same("%s:%d" % (os.path.relpath(page, ROOT), line), code)
            count += 1
    assert count > 80


def test_repl_keeps_definitions_between_runs():
    vm = VM(out=io.StringIO())
    vm.run("متغير س = ٤")
    vm.run("دالة ضعف(ع) { أرجع ع * ٢ }")
    assert vm.run("ضعف(س)", repl=True) == 8
    try:
        vm.run("اطبع(غير_موجود)")
    except NoonRuntimeError:
        pass
    assert vm.run("س + ١", repl=True) == 5       # الخطأ لم يُفسد حالة الآلة
    assert vm.frames == [] and vm.stack == []


# ——————————————— ما تنفرد به الآلة ———————————————

def test_deep_recursion_beyond_the_tree_walker():
    source = """
    دالة عدّ(ن) { إذا (ن == ٠) { أرجع ٠ } أرجع ١ + عدّ(ن - ١) }
    اطبع(عدّ(٤٠٠٠))
    """
    buffer = io.StringIO()
    VM(out=buffer).run(source)
    assert buffer.getvalue() == "4000\n"


def test_compiled_file_round_trip():
    source = """
    صنف نقطة {
        تهيئة(س، ص) { هذا.س = س
                      هذا.ص = ص }
        نص() { أرجع "(" + نص(هذا.س) + "، " + نص(هذا.ص) + ")" }
    }
    دالة عدّاد() { متغير ع = ٠
                   أرجع دالة() { ع += ١
                                 أرجع ع } }
    متغير ع = عدّاد()
    ع()
    حاول { ارمِ نقطة(ع()، ٣٫٥) } امسك (خ) { اطبع("أُمسك", خ) } أخيرًا { اطبع("انتهى") }
    """
    data = bytecode.dumps(compile_source(source))
    assert bytecode.is_compiled(data)
    loaded = bytecode.loads(data)
    buffer = io.StringIO()
    VM(out=buffer).execute(loaded)
    assert buffer.getvalue() == _transcript(Interpreter, source)


def test_compiled_file_rejects_garbage_and_other_versions():
    for data in (b"not noon", bytecode.MAGIC + bytes([bytecode.FORMAT_VERSION + 1]) + b"x",
                 bytecode.MAGIC + bytes([bytecode.FORMAT_VERSION]) + b"\x00broken"):
        try:
            bytecode.loads(data)
        except NoonError:
            continue
        raise AssertionError("قُبل ملف غير صالح: %r" % data[:12])


def test_disassembly_names_every_instruction():
    source = """
    دالة ف(أ، ب = ٢) {
        لكل ن في [أ، ب] { حاول { اطبع(ن) } أخيرًا { } }
        أرجع دالة() { أرجع أ }
    }
    """
    out = io.StringIO()
    bytecode.disassemble(compile_source(source), out)
    text = out.getvalue()
    for expected in ("══ البرنامج ══", "══ دالة ف(أ، ب) ══", "هيّئ_المحاولة",
                     "التالي_أو_اقفز", "اصنع_دالة", "متغيّرات حرّة: أ"):
        assert expected in text, "لم يظهر «%s» في التفكيك:\n%s" % (expected, text)


def test_captured_variables_are_cells_and_others_are_slots():
    script = compile_source("""
    دالة خارج() {
        متغير مُلتقَط = ١
        متغير عادي = ٢
        أرجع دالة() { أرجع مُلتقَط }
    }
    """)
    outer = [c for c in script.consts if isinstance(c, bytecode.CompiledFunction)][0]
    inner = [c for c in outer.consts if isinstance(c, bytecode.CompiledFunction)][0]
    from noon import opcodes as O
    ops = set(outer.code[0::2])
    assert O.INIT_CELL in ops and O.STORE_LOCAL in ops
    assert inner.freevars == [(0, outer.slot_names.index("مُلتقَط"), "مُلتقَط")]


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
