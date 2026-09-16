# -*- coding: utf-8 -*-
"""معاينة تلوين الصيغة في المتصفّح، بالقواعد نفسها التي تستعملها VS Code.

تُطبّق قواعد `noon.tmLanguage.json` تطبيقًا مبسَّطًا (أوّل مطابقة موضعًا،
وعند التساوي أسبق قاعدة — كما يفعل vscode-textmate) وتكتب صفحة HTML.
تحتاج حزمة `regex` لأن القواعد تستعمل \\p{L} والنظر الخلفي.

    python tools/preview_highlight.py examples/shapes.noon -o معاينة.html
"""

import argparse
import html
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GRAMMAR = os.path.join(ROOT, "editors", "vscode", "syntaxes", "noon.tmLanguage.json")

# ألوان قريبة من سِمة Dark+ في VS Code، مرتّبة من الأخصّ إلى الأعمّ
COLOURS = [
    ("comment", "#6a9955", "italic"),
    ("string", "#ce9178", None),
    ("constant.character.escape", "#d7ba7d", None),
    ("constant.numeric", "#b5cea8", None),
    ("constant.language", "#569cd6", None),
    ("variable.language", "#4fc1ff", "italic"),
    ("keyword.control", "#c586c0", None),
    ("keyword.operator", "#d4d4d4", None),
    ("storage.modifier", "#569cd6", None),
    ("storage.type", "#569cd6", None),
    ("entity.name.type", "#4ec9b0", None),
    ("entity.other.inherited-class", "#4ec9b0", None),
    ("entity.name.function", "#dcdcaa", None),
    ("support.function", "#4fc1ff", None),
    ("variable.other", "#9cdcfe", None),
    ("punctuation", "#808080", None),
]


def style_for(scope):
    for prefix, colour, weight in COLOURS:
        if scope.startswith(prefix):
            return colour, weight
    return "#d4d4d4", None


def load_rules():
    """يفرد قواعد المستودع بترتيب الإدراج في «patterns» العليا."""
    import regex

    grammar = json.load(io.open(GRAMMAR, encoding="utf-8"))
    repository = grammar["repository"]

    def to_python(pattern):
        return re.sub(r"\\x\{([0-9A-Fa-f]+)\}",
                      lambda m: "\\u%04x" % int(m.group(1), 16), pattern)

    rules = []

    def add(entry):
        if "include" in entry:
            for sub in repository[entry["include"].lstrip("#")]["patterns"]:
                add(sub)
            return
        if "begin" in entry:                     # التعليقات والنصوص
            inner = []
            for sub in entry.get("patterns", []):
                if "include" in sub:
                    for nested in repository[sub["include"].lstrip("#")]["patterns"]:
                        inner.append({"match": regex.compile(to_python(nested["match"])),
                                      "name": nested.get("name", ""),
                                      "captures": nested.get("captures", {})})
            rules.append({
                "begin": regex.compile(to_python(entry["begin"])),
                "end": regex.compile(to_python(entry["end"])),
                "name": entry.get("name", ""),
                "inner": inner,
            })
            return
        if "match" in entry:
            rules.append({
                "match": regex.compile(to_python(entry["match"])),
                "name": entry.get("name", ""),
                "captures": entry.get("captures", {}),
            })

    for entry in grammar["patterns"]:
        add(entry)
    return rules


def tokenize_line(line, rules):
    """يُرجع قائمة (نصّ، نطاق) تغطّي السطر كلّه."""
    spans = []
    pos = 0
    while pos < len(line):
        best = None
        for rule in rules:
            pattern = rule.get("match") or rule["begin"]
            found = pattern.search(line, pos)
            if found and (best is None or found.start() < best[0].start()):
                best = (found, rule)
            if best and best[0].start() == pos:
                break
        if best is None:
            spans.append((line[pos:], ""))
            break

        found, rule = best
        if found.start() > pos:
            spans.append((line[pos:found.start()], ""))

        if "begin" in rule:                      # حتى نهاية النصّ أو السطر
            end = rule["end"].search(line, found.end())
            stop = end.end() if end else len(line)
            inner = rule.get("inner")
            if inner:                            # تهريبات \\n داخل النصّ مثلًا
                body_start, body_stop = found.end(), (end.start() if end else stop)
                spans.append((line[found.start():body_start], rule["name"]))
                for text, scope in tokenize_line(line[body_start:body_stop], inner):
                    spans.append((text, scope or rule["name"]))
                spans.append((line[body_stop:stop], rule["name"]))
            else:
                spans.append((line[found.start():stop], rule["name"]))
            pos = stop
            continue

        captures = rule.get("captures")
        if captures:
            cursor = found.start()
            for index in sorted(captures, key=int):
                group = int(index)
                if group == 0 or found.group(group) is None:
                    continue
                start, stop = found.span(group)
                if start > cursor:
                    spans.append((line[cursor:start], rule["name"]))
                spans.append((line[start:stop], captures[index]["name"]))
                cursor = stop
            if cursor < found.end():
                spans.append((line[cursor:found.end()], rule["name"]))
        else:
            spans.append((found.group(0), rule["name"]))
        pos = max(found.end(), pos + 1)
    return spans


def render(paths):
    rules = load_rules()
    blocks = []
    for path in paths:
        source = io.open(path, encoding="utf-8-sig").read()
        lines = []
        for number, line in enumerate(source.splitlines(), 1):
            pieces = []
            for text, scope in tokenize_line(line, rules):
                escaped = html.escape(text)
                if not scope:
                    pieces.append(escaped)
                    continue
                colour, weight = style_for(scope)
                style = "color:%s" % colour
                if weight:
                    style += ";font-style:%s" % weight
                pieces.append('<span style="%s" title="%s">%s</span>'
                              % (style, html.escape(scope), escaped))
            lines.append('<tr><td class="ln">%d</td><td dir="auto">%s</td></tr>'
                         % (number, "".join(pieces) or "&nbsp;"))
        blocks.append("<h2>%s</h2>\n<table>%s</table>"
                      % (html.escape(os.path.basename(path)), "\n".join(lines)))

    return """<!doctype html>
<html lang="ar" dir="rtl">
<meta charset="utf-8">
<title>معاينة تلوين «نون»</title>
<style>
  body { background:#1e1e1e; color:#d4d4d4; font-family:"Cascadia Mono","Consolas",monospace;
         margin:0; padding:24px 32px; }
  h1 { font-size:20px; color:#9cdcfe; margin:0 0 4px; }
  p.hint { color:#808080; font-size:13px; margin:0 0 24px; }
  h2 { font-size:14px; color:#dcdcaa; margin:28px 0 8px; font-weight:normal; }
  table { border-collapse:collapse; width:100%%; background:#252526; border-radius:6px;
          overflow:hidden; }
  td { padding:1px 10px; white-space:pre-wrap; unicode-bidi:plaintext; font-size:14px;
       line-height:1.65; vertical-align:top; }
  td.ln { color:#5a5a5a; text-align:left; width:3em; user-select:none;
          border-inline-end:1px solid #333; }
</style>
<h1>معاينة تلوين لغة «نون»</h1>
<p class="hint">مولَّدة من editors/vscode/syntaxes/noon.tmLanguage.json — مرّر المؤشر على أي رمز لترى نطاقه (scope).</p>
%s
</html>
""" % "\n".join(blocks)


def main(argv=None):
    parser = argparse.ArgumentParser(description="معاينة تلوين صيغة «نون»")
    parser.add_argument("files", nargs="*", help="ملفات .noon")
    parser.add_argument("-o", "--out", default="noon-highlight.html")
    args = parser.parse_args(argv)

    paths = args.files or sorted(
        os.path.join(ROOT, "examples", name)
        for name in os.listdir(os.path.join(ROOT, "examples"))
        if name.endswith(".noon"))

    io.open(args.out, "w", encoding="utf-8", newline="\n").write(render(paths))
    print(os.path.abspath(args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
