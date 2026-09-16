# -*- coding: utf-8 -*-
"""خطّاف MkDocs لتوثيق «نون».

يفعل ثلاثة أشياء، وكلها حتى لا ينحرف التوثيق عن اللغة:

1. يلوّن كتل ```noon بقواعد `editors/vscode/syntaxes/noon.tmLanguage.json`
   نفسها، فما تراه في الموقع هو ما تراه في المحرّر. الرموز تُعطى أصناف
   Pygments القياسية (k، s2، nf…) فتتبع ألوان السِّمة في الوضعين الفاتح والداكن.
2. يعرض كتل ```output «ناتجًا» تحت المثال.
3. يستبدل `<!-- مثال: hello.noon -->` بشيفرة المثال من `examples/` وبناتجه
   الفعلي بعد تشغيله وقت البناء.

وتتحقّق `tests/test_docs.py` أن كل كتلة ```noon تُحلَّل، وأن كل ناتج مكتوب
يطابق ناتج التشغيل الحقيقي.
"""

import html
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for path in (ROOT, os.path.join(ROOT, "tools")):
    if path not in sys.path:
        sys.path.insert(0, path)

# الاستيراد هنا لا داخل الدوال: MkDocs يُعيد sys.path كما كان بعد تحميل
# الخطّاف، فالاستيراد المؤجَّل يفشل حين يُشغَّل `mkdocs serve` من مجلّد آخر.
from noon import values                              # noqa: E402
from noon.errors import NoonError, NoonThrow         # noqa: E402
from noon.vm import VM                               # noqa: E402
from preview_highlight import load_rules, tokenize_line  # noqa: E402

# نطاق TextMate ← صنف Pygments؛ الأخصّ أوّلًا
_SCOPE_CLASSES = [
    ("comment", "c1"),
    ("constant.character.escape", "se"),
    ("string", "s2"),
    ("constant.numeric", "m"),
    ("constant.language", "kc"),
    ("variable.language", "bp"),
    ("keyword.operator.logical", "ow"),
    ("keyword.operator", "o"),
    ("keyword.control", "k"),
    ("storage", "kd"),
    ("entity.name.type", "nc"),
    ("entity.other.inherited-class", "nc"),
    ("entity.name.function", "nf"),
    ("support.function", "nb"),
    ("variable.other.property", "na"),
    ("variable.other", "nv"),
    ("punctuation", "p"),
]

_EXAMPLE = re.compile(r"^<!--\s*مثال:\s*(?P<name>[\w.\-]+)\s*-->[ \t]*$", re.M)

# كتلة ```noon يتبعها (بعد أسطر فارغة اختيارية) كتلة ```output
FENCE = re.compile(
    r"^(?P<indent>[ \t]*)```noon[^\n]*\n(?P<code>.*?)^(?P=indent)```[ \t]*\n"
    r"(?:(?:[ \t]*\n)*(?P=indent)```output[^\n]*\n(?P<output>.*?)^(?P=indent)```[ \t]*$)?",
    re.M | re.S)

_rules = None


def _rules_once():
    global _rules
    if _rules is None:
        _rules = load_rules()
    return _rules


def _css_class(scope):
    for prefix, css in _SCOPE_CLASSES:
        if scope.startswith(prefix):
            return css
    return None


def highlight(source):
    """شيفرة «نون» ← HTML ملوَّن بأصناف Pygments."""

    rules = _rules_once()
    lines = []
    for line in source.rstrip("\n").split("\n"):
        merged = []                              # "مواء" قطعة واحدة لا ثلاث
        for text, scope in tokenize_line(line, rules):
            css = _css_class(scope) if scope else None
            if merged and merged[-1][1] == css:
                merged[-1][0] += text
            else:
                merged.append([text, css])
        lines.append("".join(
            '<span class="%s">%s</span>' % (css, html.escape(text, quote=False))
            if css else html.escape(text, quote=False)
            for text, css in merged))
    return "\n".join(lines)


def run_program(source):
    """ينفّذ برنامجًا ويُرجع ما طبعه، أو رسالة الخطأ كما يعرضها سطر الأوامر.

    يُنفَّذ بالآلة الافتراضية لأنها المحرّك الافتراضي؛ وتطابقها مع المُفسِّر في كل
    مثال هنا يختبره tests/test_vm.py.
    """
    buffer = io.StringIO()
    engine = VM(out=buffer)
    try:
        engine.run(source)
    except NoonError as error:
        buffer.write("%s\n" % error)
    except NoonThrow as thrown:
        buffer.write("قيمة مرميّة لم تُلتقط: %s\n" % engine.stringify(thrown.value))
    finally:
        values.set_arabic_digits(False)
    return buffer.getvalue()


# ——— منسِّقات superfences ———

def format_noon(src, language, class_name, options, md, **kwargs):
    return ('<div class="language-noon highlight noon-code"><pre><span></span>'
            '<code>%s</code></pre></div>' % highlight(src))


def format_output(src, language, class_name, options, md, **kwargs):
    return ('<div class="noon-output" role="figure" aria-label="الناتج">'
            '<span class="noon-output__label">الناتج</span>'
            '<pre><code>%s</code></pre></div>' % html.escape(src.rstrip("\n"), quote=False))


# ——— خطّافات MkDocs ———

def on_config(config, **kwargs):
    fences = config["mdx_configs"].setdefault("pymdownx.superfences", {})
    custom = [f for f in fences.get("custom_fences", [])
              if f.get("name") not in ("noon", "output")]
    custom += [
        {"name": "noon", "class": "noon", "format": format_noon},
        {"name": "output", "class": "output", "format": format_output},
    ]
    fences["custom_fences"] = custom
    return config


_FENCE_LINE = re.compile(r"^[ \t]*(`{3,}|~{3,})")


def expand_examples(markdown):
    """<!-- مثال: x.noon --> ← الشيفرة وناتجها الفعلي.

    التوجيه داخل كتلة شيفرة يبقى كما هو، فصفحة المساهمة تستطيع أن تعرضه.
    """
    def replace(match):
        path = os.path.join(ROOT, "examples", match.group("name"))
        with io.open(path, encoding="utf-8") as handle:
            source = handle.read().rstrip("\n")
        output = run_program(source).rstrip("\n")
        return "```noon\n%s\n```\n\n```output\n%s\n```" % (source, output)

    out, fence = [], None
    for line in markdown.split("\n"):
        marker = _FENCE_LINE.match(line)
        if fence is None and marker:
            fence = marker.group(1)
        elif fence is not None and marker and marker.group(1)[0] == fence[0] \
                and len(marker.group(1)) >= len(fence) and not line.strip()[len(marker.group(1)):]:
            fence = None
        elif fence is None:
            line = _EXAMPLE.sub(replace, line)
        out.append(line)
    return "\n".join(out)


def iter_snippets(markdown):
    """يُرجع (رقم السطر، الشيفرة، الناتج المكتوب أو None) لكل كتلة ```noon."""
    for match in FENCE.finditer(expand_examples(markdown)):
        indent = match.group("indent")

        def dedent(text):
            return "\n".join(line[len(indent):] if line.startswith(indent) else line
                             for line in text.split("\n"))

        output = match.group("output")
        line = markdown.count("\n", 0, match.start()) + 1
        yield line, dedent(match.group("code")), (
            None if output is None else dedent(output))


def on_page_markdown(markdown, page, config, files, **kwargs):
    return expand_examples(markdown)
