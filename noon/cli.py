# -*- coding: utf-8 -*-
"""سطر أوامر «نون»: تشغيل ملف، أو تنفيذ نصّ، أو صدفة تفاعلية."""

import argparse
import io
import os
import sys

from .errors import NoonError, NoonThrow
from .interpreter import Interpreter
from .lexer import tokenize
from .parser import parse
from .values import set_arabic_digits, stringify

VERSION = "١٫٠"
EXTENSIONS = (".noon", ".نون")

BANNER = """
  ن و ن — لغة برمجة عربية · الإصدار {version}
  اكتب شيفرتك ثم Enter. «مساعدة» للتعليمات، «خروج» للخروج.
""".strip("\n")

HELP = """
الأوامر الخاصة بالصدفة:
  مساعدة        عرض هذه التعليمات
  خروج          إنهاء الصدفة (أو Ctrl-D)
  مسح           مسح الشاشة

أمثلة سريعة:
  متغير س = ١٠
  اطبع("مرحبًا يا عالم")
  دالة ضعف(ع) { أرجع ع * ٢ }
  لكل ع في مدى(٥) { اطبع(ع، ضعف(ع)) }
""".strip("\n")


def _setup_streams():
    """ضمان UTF-8 دخلًا وخرجًا حتى عند إعادة التوجيه على ويندوز."""
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass


def read_source(path):
    if not os.path.exists(path):
        print("لا يوجد ملف بالمسار: %s" % path, file=sys.stderr)
        raise SystemExit(2)
    with io.open(path, encoding="utf-8-sig") as handle:
        return handle.read()


def report(error, source=None, path=None):
    """طباعة خطأ مع السطر المخالف وسهم يشير إلى موضعه."""
    where = " (%s)" % path if path else ""
    print("%s%s" % (error, where), file=sys.stderr)
    if source and getattr(error, "line", None):
        lines = source.splitlines()
        index = error.line - 1
        if 0 <= index < len(lines):
            print("  %s" % lines[index].rstrip(), file=sys.stderr)
            if error.col:
                print("  %s^" % (" " * max(0, error.col - 1)), file=sys.stderr)


def run_source(source, path=None, dump=None):
    if dump == "tokens":
        for token in tokenize(source):
            print(token)
        return 0
    if dump == "ast":
        print(parse(source))
        return 0

    interpreter = Interpreter()
    try:
        interpreter.run(source)
    except NoonError as error:
        report(error, source, path)
        return 1
    except NoonThrow as thrown:
        print("قيمة مرميّة لم تُلتقط: %s" % interpreter.stringify(thrown.value),
              file=sys.stderr)
        return 1
    except RecursionError:
        print("تجاوز عمق الاستدعاء", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nأُوقف التنفيذ", file=sys.stderr)
        return 130
    return 0


def _is_complete(source):
    """هل اكتملت الكتلة؟ يُستعمل في الصدفة لمتابعة السطر التالي."""
    depth = 0
    in_string = None
    escaped = False
    for ch in source:
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == in_string:
                in_string = None
            continue
        if ch in "\"'":
            in_string = ch
        elif ch == "#":
            break
        elif ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
    return depth <= 0 and in_string is None


def repl():
    print(BANNER.format(version=VERSION))
    interpreter = Interpreter()
    buffer = ""
    while True:
        prompt = "نون> " if not buffer else "  ... "
        try:
            line = input(prompt)
        except (EOFError, KeyboardInterrupt):
            print()
            return 0

        stripped = line.strip()
        if not buffer:
            if stripped in ("خروج", "اخرج", "exit", "quit"):
                return 0
            if stripped in ("مساعدة", "help", "؟"):
                print(HELP)
                continue
            if stripped in ("مسح", "clear"):
                os.system("cls" if os.name == "nt" else "clear")
                continue
            if not stripped:
                continue

        buffer += line + "\n"
        if not _is_complete(buffer):
            continue

        source, buffer = buffer, ""
        try:
            value = interpreter.run(source, repl=True)
            if value is not None:
                print(interpreter.stringify(value)
                      if not isinstance(value, str) else stringify(value, True))
        except NoonError as error:
            report(error, source)
        except NoonThrow as thrown:
            print("قيمة مرميّة لم تُلتقط: %s" % interpreter.stringify(thrown.value),
                  file=sys.stderr)
        except RecursionError:
            print("تجاوز عمق الاستدعاء", file=sys.stderr)
        except KeyboardInterrupt:
            print("\nأُوقف التنفيذ", file=sys.stderr)


def main(argv=None):
    _setup_streams()
    sys.setrecursionlimit(8000)

    parser = argparse.ArgumentParser(
        prog="noon", description="مُفسِّر لغة «نون» العربية")
    parser.add_argument("file", nargs="?", help="ملف %s" % " أو ".join(EXTENSIONS))
    parser.add_argument("-c", "--code", help="تنفيذ شيفرة مباشرة")
    parser.add_argument("--tokens", action="store_true", help="عرض الرموز فقط")
    parser.add_argument("--ast", action="store_true", help="عرض الشجرة النحوية فقط")
    parser.add_argument("--arabic-digits", "--عربي", dest="arabic_digits",
                        action="store_true",
                        help="عرض الأعداد بالأرقام العربية-الهندية (٠٩)")
    parser.add_argument("-v", "--version", action="version",
                        version="نون %s" % VERSION)
    args = parser.parse_args(argv)

    dump = "tokens" if args.tokens else ("ast" if args.ast else None)
    set_arabic_digits(args.arabic_digits)

    try:
        if args.code is not None:
            return run_source(args.code, "<شيفرة>", dump)
        if args.file:
            return run_source(read_source(args.file), args.file, dump)
        if not sys.stdin.isatty():
            return run_source(sys.stdin.read(), "<الدخل القياسي>", dump)
        return repl()
    except NoonError as error:
        report(error)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
