# -*- coding: utf-8 -*-
"""اختبارات ساحة التجربة: جسر التشغيل، وحزمة المتصفّح، وروابط المشاركة.

ما يعمل في المتصفّح هو noon.zip داخل Pyodide؛ فيُفكّ هنا ويُشغَّل في عملية
Python منفصلة لا ترى المستودع، للتأكّد أن الحزمة مكتفية بنفسها. واختبارات
JavaScript (توحيد الهمزات، وفكّ روابط المشاركة) تعمل إن وُجد Node وتُتخطّى بدونه.

تعمل مع pytest، وتعمل وحدها أيضًا:  python tests/test_playground.py
"""

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLAYGROUND = os.path.join(ROOT, "docs", "playground")
for path in (ROOT, PLAYGROUND, os.path.join(ROOT, "hooks")):
    if path not in sys.path:
        sys.path.insert(0, path)

import runner  # noqa: E402


def _run(source, **options):
    chunks = []
    result = runner.run(source, emit=chunks.append, **options)
    return "".join(chunks), result, chunks


# ——————————————— جسر التشغيل ———————————————

def test_output_and_success():
    text, result, _ = _run('اطبع("مرحبًا")\nاطبع(١ + ٢)')
    assert text == "مرحبًا\n3\n"
    assert result["ok"] is True and result["truncated"] is False
    assert result["engine"] == "vm" and result["ms"] >= 0


def test_both_engines_give_the_same_output():
    source = "دالة ف(ن) { إذا (ن < ٢) { أرجع ن } أرجع ف(ن - ١) + ف(ن - ٢) }\nاطبع(ف(١٥))"
    assert _run(source)[0] == _run(source, engine="tree")[0] == "610\n"


def test_errors_carry_kind_message_and_line():
    text, result, _ = _run('اطبع("قبل")\nاطبع(١ / ٠)')
    assert text == "قبل\n"
    assert result["ok"] is False
    assert result["kind"] == "خطأ تشغيل"
    assert result["message"] == "القسمة على صفر"
    assert result["line"] == 2
    assert result["text"] == "خطأ تشغيل [سطر 2]: القسمة على صفر"

    _, syntax, _ = _run("اطبع(١ +)")
    assert syntax["kind"] == "خطأ نحوي" and syntax["line"] == 1 and syntax["col"]

    _, thrown, _ = _run('ارمِ {"سبب": "مقصود"}')
    assert thrown["text"] == 'قيمة مرميّة لم تُلتقط: {"سبب": "مقصود"}'
    assert thrown["line"] == 1


def test_read_takes_lines_from_the_input_panel():
    source = 'متغير اسم = اقرأ("الاسم؟ ")\nمتغير عمر = عدد(اقرأ())\nاطبع(اسم، عمر + ١)\nاطبع("[" + اقرأ() + "]")'
    text, result, _ = _run(source, stdin="زيد\n٤١")
    assert result["ok"]
    # ما يُقرأ يظهر في الناتج كما في الطرفية، وبعد نفاد الدخل تُرجع «اقرأ» نصًّا فارغًا
    assert text == "الاسم؟ زيد\n٤١\nزيد 42\n[]\n"


def test_arabic_digits_apply_to_one_run_only():
    assert _run("اطبع(١٢٣)", arabic_digits=True)[0] == "١٢٣\n"
    assert _run("اطبع(١٢٣)")[0] == "123\n"


def test_stdin_is_restored_after_a_run():
    before = sys.stdin
    _run("اطبع(اقرأ())", stdin="س\n")
    assert sys.stdin is before


def test_output_is_streamed_in_batches_not_per_print():
    ticks = iter(range(10 ** 6))
    chunks = []
    stream = runner.StreamingOutput(chunks.append, clock=lambda: next(ticks) * 0.001)
    for i in range(3000):
        stream.write("سطر %d\n" % i)
    stream.flush()
    assert "".join(chunks).count("\n") == 3000
    assert 10 < len(chunks) < 200, "عدد الدفعات %d" % len(chunks)


def test_huge_output_is_truncated():
    text, result, _ = _run("لكل ن في مدى(٥٠٠٠٠) { اطبع(\"سطر طويل نسبيًّا للتجربة\", ن) }")
    assert result["truncated"] is True and result["ok"] is True
    assert len(text) == runner.OUTPUT_LIMIT


def test_disassemble_returns_text_or_the_syntax_error():
    good = runner.disassemble("دالة ف(س) { أرجع س }")
    assert good["ok"] and "══ دالة ف(س) ══" in good["text"]
    bad = runner.disassemble("دالة (")
    assert bad["ok"] is False and bad["kind"] == "خطأ نحوي"


def test_json_entry_points_are_valid_json():
    chunks = []
    data = json.loads(runner.run_json("اطبع(١)", "tree", False, "", chunks.append))
    assert data["ok"] and data["engine"] == "tree" and chunks == ["1\n"]
    assert json.loads(runner.disassemble_json("اطبع(١)"))["ok"]


# ——————————————— ملفات الموقع ———————————————

def _files():
    import noon_docs
    return noon_docs.playground_files()


def test_bundle_runs_on_its_own_outside_the_repository():
    """noon.zip وحده، في عملية Python لا ترى المستودع، كما في Pyodide."""
    archive = zipfile.ZipFile(io.BytesIO(_files()["noon.zip"]))
    names = set(archive.namelist())
    for path in os.listdir(os.path.join(ROOT, "noon")):
        if path.endswith(".py"):
            assert "noon/" + path in names, "ينقص الحزمة: %s" % path
    assert "runner.py" in names
    for path in os.listdir(os.path.join(ROOT, "noon", "lib")):
        assert "noon/lib/" + path in names, "ينقص المكتبة: %s" % path

    workdir = tempfile.mkdtemp()
    try:
        archive.extractall(workdir)
        script = (
            "import sys, json\n"
            "sys.path = [p for p in sys.path if 'noon-lang' not in p.replace('\\\\', '/')]\n"
            "sys.path.insert(0, %r)\n"
            "import runner, noon\n"
            "assert noon.__file__.startswith(%r), noon.__file__\n"
            "out = []\n"
            "r = runner.run('صنف أ { نص() { أرجع \"من الحزمة\" } }\\nاطبع(أ())\\n"
            "اطبع(استورد(\"رياضيات\").عاملي(٥))', emit=out.append)\n"
            "sys.stdout.buffer.write(json.dumps([''.join(out), r['ok']], ensure_ascii=False).encode('utf-8'))\n"
        ) % (workdir, workdir)
        completed = subprocess.run([sys.executable, "-c", script], cwd=workdir,
                                   capture_output=True, timeout=120)
        assert completed.returncode == 0, completed.stderr.decode("utf-8", "replace")
        assert json.loads(completed.stdout.decode("utf-8")) == ["من الحزمة\n120\n", True]
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def test_language_data_matches_the_interpreter():
    from noon import builtins as B
    from noon.lexer import KEYWORDS
    text = _files()["language.js"].decode("utf-8")
    data = json.loads(text[text.index("{"):text.rindex("}") + 1])
    assert data["keywords"] == KEYWORDS
    assert set(data["builtins"]) | set(data["constants"]) == set(B.GLOBALS)
    assert "أضف" in data["methods"] and "مفاتيح" in data["methods"]


def test_examples_are_bundled_with_titles():
    text = _files()["examples.js"].decode("utf-8")
    examples = json.loads(text[text.index("["):text.rindex("]") + 1])
    names = sorted(e["name"] for e in examples)
    on_disk = sorted(os.path.splitext(n)[0] for n in os.listdir(os.path.join(ROOT, "examples"))
                     if n.endswith(".noon"))
    assert names == on_disk
    assert all(e["title"] and not e["title"].startswith("#") for e in examples)


def test_every_docs_code_block_links_to_the_playground():
    import noon_docs
    html = noon_docs.format_noon('اطبع("من التوثيق")\n', "noon", "", {}, None)
    assert 'class="noon-try"' in html
    token = html.split("#code=")[1].split('"')[0]
    assert noon_docs.decode_share(token) == 'اطبع("من التوثيق")'


# ——————————————— JavaScript (يحتاج Node) ———————————————

def _node(script):
    node = shutil.which("node")
    if node is None:
        return None
    completed = subprocess.run([node, "--input-type=module", "-e", script],
                               capture_output=True, timeout=60)
    assert completed.returncode == 0, completed.stderr.decode("utf-8", "replace")
    return completed.stdout.decode("utf-8")


def _file_url(path):
    return "file:///" + path.replace("\\", "/").lstrip("/")


def test_javascript_normalize_matches_the_lexer():
    from noon.lexer import _RAW_KEYWORDS, normalize
    words = list(_RAW_KEYWORDS) + ["دالـة", "فى", "داله", "صنّف", "رشّح", "آخر", "ٱسم", "مدرسة"]
    script = (
        "import { normalize } from %r;\n"
        "const words = JSON.parse(%r);\n"
        "process.stdout.write(JSON.stringify(words.map(normalize)));\n"
    ) % (_file_url(os.path.join(PLAYGROUND, "normalize.js")), json.dumps(words, ensure_ascii=False))
    output = _node(script)
    if output is None:
        return
    assert json.loads(output) == [normalize(w) for w in words]


def test_share_links_from_python_open_in_the_browser_format():
    """ما يُنشئه الخطّاف يفكّه DecompressionStream كما تفعل الصفحة."""
    import noon_docs
    code = 'دالة تحية(اسم) {\n    أرجع "سلام يا " + اسم\n}\nاطبع(تحية("هند"))\n' * 20
    script = (
        "const token = %r;\n"
        "const b64 = token.replace(/-/g, '+').replace(/_/g, '/');\n"
        "const bytes = Uint8Array.from(atob(b64 + '==='.slice((b64.length + 3) %% 4)), c => c.charCodeAt(0));\n"
        "const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream('deflate-raw'));\n"
        "const text = new TextDecoder().decode(await new Response(stream).arrayBuffer());\n"
        "process.stdout.write(JSON.stringify(text));\n"
    ) % noon_docs.encode_share(code)
    output = _node(script)
    if output is None:
        return
    assert json.loads(output) == code


# ——————————————— محرّر الكتل ———————————————

def test_blocks_page_is_wired_to_real_files():
    import re
    html = io.open(os.path.join(PLAYGROUND, "blocks.html"), encoding="utf-8").read()
    script = io.open(os.path.join(PLAYGROUND, "blocks.js"), encoding="utf-8").read()
    for name in re.findall(r'(?:src|href)="([\w.-]+\.(?:js|css))"', html):
        assert os.path.exists(os.path.join(PLAYGROUND, name)), "ملف مفقود: %s" % name
    for name in re.findall(r'from "\./([\w.-]+\.js)"', script) + ["worker.js"]:
        generated = name in ("language.js", "examples.js")
        assert generated or os.path.exists(os.path.join(PLAYGROUND, name)), "ملف مفقود: %s" % name
    # نسخة Blockly واحدة للنواة والكتل والرسائل والوسائط
    versions = set(re.findall(r"blockly@([\d.]+)/", html + script))
    assert len(versions) == 1, versions
    ignore = io.open(os.path.join(ROOT, ".gitignore"), encoding="utf-8").read()
    assert "!docs/playground/blocks.html" in ignore


def test_block_modules_parse():
    node = shutil.which("node")
    if node is None:
        return
    for name in ("blocks.js", "noon-blocks.js", "blocks-examples.js", "share.js"):
        completed = subprocess.run([node, "--check", os.path.join(PLAYGROUND, name)],
                                   capture_output=True, timeout=60)
        assert completed.returncode == 0, completed.stderr.decode("utf-8", "replace")


def test_block_names_become_valid_noon_identifiers():
    """noonName في noon-blocks.js: ما يكتبه المستخدم اسمًا يصير معرّفًا يقبله المُحلِّل."""
    import noon_docs
    from noon.lexer import tokenize
    folder = tempfile.mkdtemp()
    try:
        for name in ("noon-blocks.js", "normalize.js"):
            shutil.copy(os.path.join(PLAYGROUND, name), folder)
        with open(os.path.join(folder, "language.js"), "wb") as handle:
            handle.write(noon_docs.playground_files()["language.js"])
        names = ["عدد الطلاب", "إذا", "اذا", "طول", "3 أشياء", "س-ص", "", "رياضيات",
                 "مجموع_الدرجات", "صنّف"]
        texts = ['قال "مرحبًا"', "سطر\nثانٍ", "مائل \\ هنا"]
        script = (
            "import { noonName, quote } from %r;\n"
            "process.stdout.write(JSON.stringify([JSON.parse(%r).map(noonName),"
            " JSON.parse(%r).map(quote)]));\n"
        ) % (_file_url(os.path.join(folder, "noon-blocks.js")),
             json.dumps(names, ensure_ascii=False), json.dumps(texts, ensure_ascii=False))
        output = _node(script)
        if output is None:
            return
        identifiers, literals = json.loads(output)
    finally:
        shutil.rmtree(folder, ignore_errors=True)
    assert identifiers[:3] == ["عدد_الطلاب", "إذا_", "اذا_"]
    assert identifiers[9] == "صنّف"                      # التشكيل يجعله اسمًا لا كلمة
    for identifier in identifiers:
        tokens = [t for t in tokenize(identifier) if t.type not in ("NEWLINE", "EOF")]
        assert [t.type for t in tokens] == ["IDENT"], (identifier, tokens)
    # والنصوص تُقرأ كما كُتبت
    for text, literal in zip(texts, literals):
        tokens = [t for t in tokenize(literal) if t.type == "STRING"]
        assert tokens and tokens[0].value == text, (literal, tokens)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    try:
        import regex  # noqa: F401            # الخطّاف يحتاجها
    except ImportError:
        print("تُخطِّيت: حزمة regex غير مثبّتة")
        return 0
    tests = [(n, f) for n, f in sorted(globals().items())
             if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print("✓ %s" % name)
        except Exception as error:               # noqa: BLE001
            failed += 1
            print("✗ %s\n    %s: %s" % (name, type(error).__name__, error))
    print("\n%d/%d اختبارًا ناجحًا" % (len(tests) - failed, len(tests)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
