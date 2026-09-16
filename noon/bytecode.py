# -*- coding: utf-8 -*-
"""الدالة المُترجَمة، وصيغة ملفات ‎.noonc، ومُفكِّك التجميع."""

import marshal

from . import opcodes as op
from .errors import NoonError
from .values import stringify

MAGIC = b"NOONC"
FORMAT_VERSION = 1


class CompiledFunction:
    """ناتج ترجمة دالة (أو البرنامج كلّه): تعليمات وثوابت وجداول.

    ليست قيمة يراها المبرمج؛ ما يراه هو `values.Closure` التي تغلّفها مع
    خلاياها الملتقَطة.
    """

    __slots__ = (
        "name", "param_names", "required", "is_method", "is_script",
        "code", "lines", "consts", "names", "n_slots", "slot_names",
        "cell_params", "freevars", "handlers", "scope_cells", "entries",
    )

    def __init__(self, name, is_method=False, is_script=False):
        self.name = name or "دالة مجهولة"
        self.param_names = []        # بلا «هذا»
        self.required = 0            # عدد الوسائط التي لا قيمة افتراضية لها
        self.is_method = is_method
        self.is_script = is_script
        self.code = []               # أزواج (تعليمة، وسيط)
        self.lines = []              # سطر كل تعليمة: lines[ip // 2]
        self.consts = []
        self.names = []              # أسماء العوامّ والأعضاء
        self.n_slots = 0
        self.slot_names = []         # للعرض فقط
        self.cell_params = []        # خانات وسائط التقطتها دوال داخلية
        self.freevars = []           # (نوع، فهرس، اسم): ٠ خانة في الأب، ١ حرّ في الأب
        self.handlers = []           # (موضع امسك، موضع أخيرًا، رقم أخيرًا)
        self.scope_cells = []        # لكل نطاق: خاناته المُلتقَطة
        self.entries = []            # موضع البدء بحسب عدد الوسائط المعطاة

    @property
    def n_params(self):
        return len(self.param_names)

    def __repr__(self):
        return "<دالة مُترجَمة %s>" % self.name


# ——————————————— ملفات ‎.noonc ———————————————

def _to_data(fn):
    consts = []
    for value in fn.consts:
        if isinstance(value, CompiledFunction):
            consts.append(("fn", _to_data(value)))
        else:
            consts.append(("v", value))
    return (
        fn.name, fn.param_names, fn.required, fn.is_method, fn.is_script,
        fn.code, fn.lines, consts, fn.names, fn.n_slots, fn.slot_names,
        fn.cell_params, [list(f) for f in fn.freevars],
        [list(h) for h in fn.handlers], fn.scope_cells, fn.entries,
    )


def _from_data(data):
    (name, param_names, required, is_method, is_script, code, lines, consts,
     names, n_slots, slot_names, cell_params, freevars, handlers, scope_cells,
     entries) = data
    fn = CompiledFunction(name, is_method, is_script)
    fn.param_names = list(param_names)
    fn.required = required
    fn.code = list(code)
    fn.lines = list(lines)
    fn.consts = [_from_data(v) if kind == "fn" else v for kind, v in consts]
    fn.names = list(names)
    fn.n_slots = n_slots
    fn.slot_names = list(slot_names)
    fn.cell_params = list(cell_params)
    fn.freevars = [tuple(f) for f in freevars]
    fn.handlers = [tuple(h) for h in handlers]
    fn.scope_cells = [list(s) for s in scope_cells]
    fn.entries = list(entries)
    return fn


def dumps(script):
    """الدالة المُترجَمة ← بايتات ملف ‎.noonc."""
    return MAGIC + bytes([FORMAT_VERSION]) + marshal.dumps(_to_data(script))


def loads(data):
    """بايتات ملف ‎.noonc ← الدالة المُترجَمة."""
    if not is_compiled(data):
        raise NoonError("ليس ملفًّا مُترجَمًا للغة «نون»")
    version = data[len(MAGIC)]
    if version != FORMAT_VERSION:
        raise NoonError("الملف مُترجَم بإصدار صيغة %d، وهذا المُترجِم يقرأ %d؛ "
                        "أعِد ترجمته" % (version, FORMAT_VERSION))
    try:
        return _from_data(marshal.loads(data[len(MAGIC) + 1:]))
    except (ValueError, EOFError, TypeError) as error:
        raise NoonError("ملف مُترجَم تالف: %s" % error)


def is_compiled(data):
    return data[:len(MAGIC)] == MAGIC


# ——————————————— مُفكِّك التجميع ———————————————

def _function_label(fn):
    return "<دالة مجهولة>" if fn.name == "دالة مجهولة" else "<دالة %s>" % fn.name


def _describe_arg(fn, code_op, arg):
    if code_op == op.LOAD_CONST:
        value = fn.consts[arg]
        if isinstance(value, CompiledFunction):
            return _function_label(value)
        return stringify(value, quote=True)     # عدم وصحيح و"نص" لا None وTrue
    if code_op in (op.LOAD_LOCAL, op.STORE_LOCAL, op.LOAD_CELL, op.STORE_CELL,
                   op.INIT_CELL):
        return "%d (%s)" % (arg, fn.slot_names[arg] if arg < len(fn.slot_names) else "?")
    if code_op in (op.LOAD_FREE, op.STORE_FREE):
        return "%d (%s)" % (arg, fn.freevars[arg][2])
    if code_op in (op.LOAD_GLOBAL, op.STORE_GLOBAL, op.DEFINE_GLOBAL,
                   op.DEFINE_GLOBAL_CONST, op.DEFINE_GLOBAL_FORCE,
                   op.GET_MEMBER, op.SET_MEMBER):
        return "%d (%s)" % (arg, fn.names[arg])
    if code_op == op.BINARY:
        return op.BINARY_OPS[arg]
    if code_op in op.JUMPS:
        return "← %d" % arg
    if code_op == op.MAKE_CLOSURE:
        return _function_label(fn.consts[arg])
    if code_op == op.RAISE_ERROR:
        return stringify(fn.consts[arg], quote=True)
    if code_op == op.SETUP_TRY:
        catch, final, _ = fn.handlers[arg]
        parts = []
        if catch >= 0:
            parts.append("امسك ← %d" % catch)
        if final >= 0:
            parts.append("أخيرًا ← %d" % final)
        return "، ".join(parts)
    if code_op in (op.CALL, op.BUILD_LIST, op.BUILD_DICT):
        return str(arg)
    if code_op == op.BUILD_CLASS:
        return "%d توابع%s" % (arg // 2, "، له أب" if arg & 1 else "")
    if code_op == op.GET_SLICE:
        return {0: "[:]", 1: "[س:]", 2: "[:ص]", 3: "[س:ص]"}[arg]
    return ""


def disassemble(fn, out, _seen=None):
    """يكتب تعليمات الدالة ودوالّها الداخلية بصيغة مقروءة."""
    seen = set() if _seen is None else _seen
    if id(fn) in seen:
        return
    seen.add(id(fn))

    params = "، ".join(fn.param_names)
    if fn.is_script:
        title = "البرنامج"
    elif fn.name == "دالة مجهولة":
        title = "دالة مجهولة(%s)" % params
    else:
        title = "%s %s(%s)" % ("تابع" if fn.is_method else "دالة", fn.name, params)
    details = ["خانات: %d" % fn.n_slots]
    if fn.freevars:
        details.append("متغيّرات حرّة: %s" % "، ".join(f[2] for f in fn.freevars))
    out.write("══ %s ══  %s\n" % (title, " · ".join(details)))

    last_line = None
    for ip in range(0, len(fn.code), 2):
        code_op, arg = fn.code[ip], fn.code[ip + 1]
        line = fn.lines[ip // 2]
        shown = str(line) if line != last_line else ""
        last_line = line
        marker = "▸" if ip in fn.entries[1:] else " "
        out.write("%5s %s%5d  %-22s %s\n" % (
            shown, marker, ip, op.NAMES[code_op], _describe_arg(fn, code_op, arg)))
    out.write("\n")

    for value in fn.consts:
        if isinstance(value, CompiledFunction):
            disassemble(value, out, seen)
