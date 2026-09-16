# -*- coding: utf-8 -*-
"""يتحقّق أن رقم الإصدار واحد في كل مكان، ويستخرج ملاحظات الإصدار.

    python tools/check_version.py              # الأرقام متّفقة؟
    python tools/check_version.py v1.1.0       # ومتّفقة مع هذا الوسم؟
    python tools/check_version.py v1.1.0 --notes   # ملاحظات الإصدار من CHANGELOG.md

يُشغّله سير عمل الإصدار قبل البناء، فلا يُنشر إصدار وسمُه يخالف ما في الحزمة.
"""

import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

ARABIC_DIGITS = {chr(0x0660 + i): str(i) for i in range(10)}
ARABIC_DIGITS["٫"] = "."


def _read(*parts):
    with io.open(os.path.join(ROOT, *parts), encoding="utf-8") as handle:
        return handle.read()


def versions():
    import noon
    from noon import cli

    pyproject = re.search(r'(?m)^version\s*=\s*"([^"]+)"', _read("pyproject.toml")).group(1)
    extension = json.loads(_read("editors", "vscode", "package.json"))["version"]
    shown = "".join(ARABIC_DIGITS.get(ch, ch) for ch in cli.VERSION)
    return {
        "pyproject.toml": pyproject,
        "noon.__version__": noon.__version__,
        "editors/vscode/package.json": extension,
        "noon -v (major.minor)": shown,
    }


def release_notes(version):
    """قسم الإصدار من CHANGELOG.md، بلا عنوانه وبلا روابط المراجع في آخره."""
    text = _read("CHANGELOG.md")
    match = re.search(r"(?ms)^## \[%s\][^\n]*\n(.*?)(?=^## \[|^\[[^\]]+\]:)" % re.escape(version), text)
    if not match:
        return None
    return match.group(1).strip() + "\n"


def main(argv):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    tag = next((a for a in argv if not a.startswith("--")), None)
    found = versions()
    version = found["pyproject.toml"]
    problems = []

    for where, value in found.items():
        expected = ".".join(version.split(".")[:2]) if "major.minor" in where else version
        if value != expected:
            problems.append("%s يقول %s والمتوقَّع %s" % (where, value, expected))
    if tag is not None and tag != "v" + version:
        problems.append("الوسم %s لا يطابق الإصدار v%s" % (tag, version))
    notes = release_notes(version)
    if notes is None:
        problems.append("CHANGELOG.md بلا قسم «## [%s]»" % version)

    if problems:
        print("الإصدار غير متّسق:\n  " + "\n  ".join(problems), file=sys.stderr)
        return 1
    if "--notes" in argv:
        sys.stdout.write(notes)
    else:
        print("الإصدار %s متّسق في: %s" % (version, "، ".join(found)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
