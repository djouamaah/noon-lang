# -*- coding: utf-8 -*-
"""التوثيق لا يكذب: كل مثال فيه يُحلَّل، وكل ناتج مكتوب يطابق التشغيل.

تعمل مع pytest، وتعمل وحدها أيضًا:  python tests/test_docs.py
تحتاج حزمة `regex` (لتلوين الشيفرة)؛ تُتخطّى الاختبارات بدونها.
"""

import glob
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "hooks"))

from noon.errors import NoonError  # noqa: E402
from noon.parser import parse  # noqa: E402


def _pages():
    return sorted(glob.glob(os.path.join(DOCS, "**", "*.md"), recursive=True))


def _read(path):
    with io.open(path, encoding="utf-8") as handle:
        return handle.read()


def _hook():
    import noon_docs
    return noon_docs


def _where(path, line):
    return "%s:%d" % (os.path.relpath(path, ROOT), line)


def test_every_snippet_parses_or_shows_its_error():
    hook = _hook()
    count = 0
    for page in _pages():
        for line, code, output in hook.iter_snippets(_read(page)):
            count += 1
            if output is not None:
                continue                 # يتحقّق منه الاختبار التالي، ولو كان خطأً مقصودًا
            try:
                parse(code)
            except NoonError as error:
                raise AssertionError("%s لا يُحلَّل: %s" % (_where(page, line), error))
    assert count > 50, "عدد أمثلة التوثيق أقلّ من المتوقّع: %d" % count


def test_every_written_output_is_the_real_output():
    hook = _hook()
    checked = 0
    failures = []
    for page in _pages():
        for line, code, output in hook.iter_snippets(_read(page)):
            if output is None:
                continue
            checked += 1
            actual = hook.run_program(code).rstrip("\n")
            if actual != output.rstrip("\n"):
                failures.append("%s\n  المكتوب:\n%s\n  الفعلي:\n%s" % (
                    _where(page, line),
                    _indent(output.rstrip("\n")), _indent(actual)))
    assert not failures, "نواتج لا تطابق التشغيل:\n\n" + "\n\n".join(failures)
    assert checked > 30, "عدد النواتج المتحقَّق منها قليل: %d" % checked


def _indent(text):
    return "\n".join("    | " + line for line in text.split("\n"))


def test_reference_lists_every_builtin_keyword_and_method():
    from noon import builtins as B
    from noon.lexer import _RAW_KEYWORDS

    builtins_page = _read(os.path.join(DOCS, "reference", "builtins.md"))
    keywords_page = _read(os.path.join(DOCS, "reference", "keywords.md"))
    methods_page = _read(os.path.join(DOCS, "reference", "methods.md"))

    # الأسماء الأصلية فقط، لا البدائل المطويّة (أقصى لا اقصي)
    from noon.lexer import fold
    canonical = [name for name in B.GLOBALS
                 if not any(other != name and fold(other) == name for other in B.GLOBALS)]
    missing = [n for n in canonical if "`%s" % n not in builtins_page]
    assert not missing, "دوال مدمجة غير موثَّقة: %s" % "، ".join(missing)

    missing = [k for k in _RAW_KEYWORDS if "`%s`" % k not in keywords_page]
    assert not missing, "كلمات مفتاحية غير موثَّقة: %s" % "، ".join(missing)

    for title, table in (("النصوص", B.STRING_METHODS), ("القوائم", B.LIST_METHODS),
                         ("القواميس", B.DICT_METHODS)):
        names = [n for n in table if not any(o != n and fold(o) == n for o in table)]
        missing = [n for n in names if ".%s(" % n not in methods_page]
        assert not missing, "توابع %s غير موثَّقة: %s" % (title, "، ".join(missing))


def test_every_page_is_in_the_navigation_and_every_link_resolves():
    config = _read(os.path.join(ROOT, "mkdocs.yml"))
    in_nav = set(re.findall(r":\s*([\w\-/]+\.md)\s*$", config, re.M))
    on_disk = {os.path.relpath(p, DOCS).replace(os.sep, "/") for p in _pages()}
    assert on_disk == in_nav, "صفحات خارج القائمة: %s / روابط لصفحات مفقودة: %s" % (
        sorted(on_disk - in_nav), sorted(in_nav - on_disk))

    for page in _pages():
        text = _read(page)
        for target in re.findall(r"\]\(([^)#\s]+\.md)(?:#[^)]*)?\)", text):
            resolved = os.path.normpath(os.path.join(os.path.dirname(page), target))
            assert os.path.exists(resolved), "%s: رابط مكسور إلى %s" % (
                os.path.relpath(page, ROOT), target)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    try:
        import regex  # noqa: F401
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
            print("✗ %s\n%s" % (name, error))
    print("\n%d/%d اختبارًا ناجحًا" % (len(tests) - failed, len(tests)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
