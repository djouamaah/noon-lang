# -*- coding: utf-8 -*-
"""سطر أوامر «نون»: تشغيل ملف، أو تنفيذ نصّ، أو صدفة تفاعلية، أو ترجمة.

يُنفَّذ البرنامج افتراضًا بالمترجِم والآلة الافتراضية؛ و`--شجرة` تختار المُفسِّر
الذي يمشي على الشجرة. المحرّكان يُعطيان الناتج نفسه (انظر tests/test_vm.py).
"""

import argparse
import os
import sys

from . import bytecode
from .builtins import PROGRAM_ARGS
from .compiler import compile_source
from .errors import NoonError, NoonThrow
from .interpreter import Interpreter
from .lexer import tokenize
from .parser import parse
from .runtime import Runtime
from .values import set_arabic_digits, stringify
from .vm import VM

VERSION = "١٫١"
EXTENSIONS = (".noon", ".نون")
COMPILED_EXTENSION = ".noonc"

BANNER = """
  ن و ن — لغة برمجة عربية · الإصدار {version} · {engine}
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


def _engine(tree):
    return Interpreter() if tree else VM()


def load_program(path):
    """يُرجع (نصّ، None) لملف مصدر، أو (None، دالة مُترجَمة) لملف ‎.noonc."""
    if not os.path.exists(path):
        print("لا يوجد ملف بالمسار: %s" % path, file=sys.stderr)
        raise SystemExit(2)
    with open(path, "rb") as handle:
        data = handle.read()
    if bytecode.is_compiled(data):
        return None, bytecode.loads(data)
    try:
        return data.decode("utf-8-sig"), None
    except UnicodeDecodeError:
        raise NoonError("الملف ليس نصًّا بترميز UTF-8 ولا ملفًّا مُترجَمًا")


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


def execute(engine, action, source=None, path=None):
    """ينفّذ ويُترجم الأخطاء إلى رسائل ورموز خروج."""
    try:
        action()
    except NoonError as error:
        report(error, source, path)
        return 1
    except NoonThrow as thrown:
        print("قيمة مرميّة لم تُلتقط: %s" % engine.stringify(thrown.value),
              file=sys.stderr)
        return 1
    except RecursionError:
        print("تجاوز عمق الاستدعاء", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nأُوقف التنفيذ", file=sys.stderr)
        return 130
    return 0


def run_source(source, path=None, dump=None, tree=False):
    if dump == "tokens":
        for token in tokenize(source):
            print(token)
        return 0
    if dump == "ast":
        print(parse(source))
        return 0
    engine = _engine(tree)
    return execute(engine, lambda: engine.run(source), source, path)


def compile_file(source, path, output):
    """يترجم المصدر ويكتب ملف ‎.noonc دون تشغيله."""
    if output is None:
        if path is None or path.startswith("<"):
            print("حدّد مسار الملف المُترجَم بـ -o", file=sys.stderr)
            return 2
        output = os.path.splitext(path)[0] + COMPILED_EXTENSION
    try:
        data = bytecode.dumps(compile_source(source))
    except NoonError as error:
        report(error, source, path)
        return 1
    with open(output, "wb") as handle:
        handle.write(data)
    print("تُرجم إلى %s (%d بايت)" % (output, len(data)))
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


def repl(tree=False):
    engine = _engine(tree)
    print(BANNER.format(version=VERSION,
                        engine="المُفسِّر الشجري" if tree else "الآلة الافتراضية"))
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
        result = {}

        def evaluate():
            result["value"] = engine.run(source, repl=True)

        if execute(engine, evaluate, source) == 0 and result.get("value") is not None:
            value = result["value"]
            print(stringify(value, True) if isinstance(value, str)
                  else engine.stringify(value))


def main(argv=None):
    _setup_streams()
    sys.setrecursionlimit(8000)

    parser = argparse.ArgumentParser(
        prog="noon", description="مترجِم لغة «نون» العربية ومُفسِّرها")
    parser.add_argument("file", nargs="?",
                        help="ملف %s، أو ملف مُترجَم %s" % (" أو ".join(EXTENSIONS),
                                                       COMPILED_EXTENSION))
    parser.add_argument("-c", "--code", help="تنفيذ شيفرة مباشرة")
    parser.add_argument("--compile", "--ترجم", dest="compile", action="store_true",
                        help="ترجمة البرنامج إلى ملف %s دون تشغيله" % COMPILED_EXTENSION)
    parser.add_argument("-o", "--output", help="مسار الملف المُترجَم (مع --ترجم)")
    parser.add_argument("--dis", "--فكّك", dest="dis", action="store_true",
                        help="عرض البايت-كود بصيغة مقروءة دون تشغيل")
    parser.add_argument("--tree", "--شجرة", dest="tree", action="store_true",
                        help="التنفيذ بالمُفسِّر الذي يمشي على الشجرة بدل المترجِم")
    parser.add_argument("--tokens", action="store_true", help="عرض الرموز فقط")
    parser.add_argument("--ast", action="store_true", help="عرض الشجرة النحوية فقط")
    parser.add_argument("--arabic-digits", "--عربي", dest="arabic_digits",
                        action="store_true",
                        help="عرض الأعداد بالأرقام العربية-الهندية (٠٩)")
    parser.add_argument("-v", "--version", action="version",
                        version="نون %s" % VERSION)
    parser.add_argument("program_args", nargs=argparse.REMAINDER,
                        help="وسائط البرنامج بعد اسم ملفه، تُقرأ بـ«وسائط()»")
    args = parser.parse_args(argv)
    if args.program_args and (args.compile or args.dis or args.tokens or args.ast):
        # البرنامج لا يُشغَّل، فما بعد اسم الملف خيارات «نون» نفسها:
        # «--ترجم برنامج.noon -o آخر.noonc»
        rest = parser.parse_args(args.program_args)
        if rest.file is not None or rest.program_args:
            parser.error("وسائط زائدة: %s" % " ".join(args.program_args))
        for key, value in vars(rest).items():
            if key not in ("file", "program_args") and value not in (None, False):
                setattr(args, key, value)
        args.program_args = []

    dump = "tokens" if args.tokens else ("ast" if args.ast else None)
    set_arabic_digits(args.arabic_digits)
    program_args = list(args.program_args)
    if args.code is not None and args.file:     # مع -c لا ملف: الوسيط الأول للبرنامج
        program_args.insert(0, args.file)
    PROGRAM_ARGS[:] = program_args
    if args.tree and (args.compile or args.dis):
        parser.error("--شجرة لا تُجمع مع --ترجم أو --فكّك: المُفسِّر لا يترجم")

    source, script, label = None, None, None
    try:
        if args.code is not None:
            source, label = args.code, "<شيفرة>"
        elif args.file:
            source, script = load_program(args.file)
            label = args.file
            # «استورد» يبحث عن الوحدات بجوار البرنامج قبل المكتبة القياسية
            Runtime.base_dir = os.path.dirname(os.path.abspath(args.file))
        elif not sys.stdin.isatty():
            source, label = sys.stdin.read(), "<الدخل القياسي>"
        else:
            if args.compile or args.dis or dump:
                parser.error("هذا الخيار يحتاج ملفًّا أو -c")
            return repl(tree=args.tree)

        if script is not None:                    # ملف ‎.noonc
            if dump or args.compile:
                parser.error("الملف مُترجَم أصلًا؛ هذا الخيار يحتاج نصّ البرنامج")
            if args.tree:
                parser.error("الملف المُترجَم لا يُشغَّل إلا بالآلة الافتراضية")
            if args.dis:
                bytecode.disassemble(script, sys.stdout)
                return 0
            engine = VM()
            return execute(engine, lambda: engine.execute(script), None, label)

        if args.compile:
            return compile_file(source, label, args.output)
        if args.dis:
            bytecode.disassemble(compile_source(source), sys.stdout)
            return 0
        return run_source(source, label, dump, tree=args.tree)
    except NoonError as error:
        report(error, source, label)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
