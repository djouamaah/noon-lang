# -*- coding: utf-8 -*-
"""الدوال المدمجة وتوابع الأنواع الأساسية في «نون»."""

import math
import random
import time

from .errors import NoonRuntimeError
from .lexer import _DIGIT_MAP, fold
from .values import (BuiltinFunction, NoonClass, NoonInstance, is_number,
                     set_arabic_digits, stringify, truthy, type_name, equals)


def _need_number(value, line, what="وسيط"):
    if not is_number(value):
        raise NoonRuntimeError("%s يجب أن يكون عددًا، لا «%s»"
                               % (what, type_name(value)), line)
    return value


def _need_int(value, line, what="وسيط"):
    _need_number(value, line, what)
    if isinstance(value, float) and not value.is_integer():
        raise NoonRuntimeError("%s يجب أن يكون عددًا صحيحًا" % what, line)
    return int(value)


def _to_number(value, line):
    if is_number(value):
        return value
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, str):
        text = "".join(_DIGIT_MAP.get(c, c) for c in value.strip())
        text = text.replace("٫", ".").replace("٬", "").replace("−", "-")
        try:
            return int(text)
        except ValueError:
            try:
                return float(text)
            except ValueError:
                raise NoonRuntimeError("لا يمكن تحويل «%s» إلى عدد" % value, line)
    raise NoonRuntimeError("لا يمكن تحويل قيمة من نوع «%s» إلى عدد"
                           % type_name(value), line)


# ———————————————— الدوال العامة ————————————————

def _print(interp, args, line):
    interp.write(" ".join(interp.stringify(a) for a in args) + "\n")
    return None


def _read(interp, args, line):
    prompt = interp.stringify(args[0]) if args else ""
    if prompt:
        interp.write(prompt)
    try:
        return input()
    except EOFError:
        return ""


def _len(interp, args, line):
    value = args[0]
    if isinstance(value, (str, list, dict)):
        return len(value)
    raise NoonRuntimeError("لا طول لقيمة من نوع «%s»" % type_name(value), line)


def _range(interp, args, line):
    if len(args) == 1:
        start, stop, step = 0, _need_int(args[0], line, "نهاية المدى"), 1
    elif len(args) == 2:
        start = _need_int(args[0], line, "بداية المدى")
        stop = _need_int(args[1], line, "نهاية المدى")
        step = 1
    else:
        start = _need_int(args[0], line, "بداية المدى")
        stop = _need_int(args[1], line, "نهاية المدى")
        step = _need_int(args[2], line, "خطوة المدى")
    if step == 0:
        raise NoonRuntimeError("خطوة المدى لا يمكن أن تكون صفرًا", line)
    return list(range(start, stop, step))


def _sum(interp, args, line):
    total = 0
    for item in interp.iterate(args[0], line):
        total += _need_number(item, line, "عنصر في «مجموع»")
    return total


def _minmax(pick):
    def fn(interp, args, line):
        items = args[0] if len(args) == 1 and isinstance(args[0], list) else list(args)
        if not items:
            raise NoonRuntimeError("لا يمكن إيجاد القيمة من قائمة فارغة", line)
        best = items[0]
        for item in items[1:]:
            order = interp.compare(item, best, line)
            if (order > 0) if pick == "max" else (order < 0):
                best = item
        return best
    return fn


def _sorted(interp, args, line):
    import functools
    items = list(interp.iterate(args[0], line))
    if len(args) > 1 and args[1] is not None:
        key_fn = args[1]
        decorated = [(interp.call(key_fn, [item], line), item) for item in items]
        decorated.sort(key=functools.cmp_to_key(
            lambda a, b: interp.compare(a[0], b[0], line)))
        items = [item for _, item in decorated]
    else:
        items.sort(key=functools.cmp_to_key(
            lambda a, b: interp.compare(a, b, line)))
    if len(args) > 2 and truthy(args[2]):
        items.reverse()
    return items


def _reversed(interp, args, line):
    value = args[0]
    if isinstance(value, str):
        return value[::-1]
    return list(interp.iterate(value, line))[::-1]


def _map(interp, args, line):
    return [interp.call(args[0], [item], line)
            for item in interp.iterate(args[1], line)]


def _filter(interp, args, line):
    return [item for item in interp.iterate(args[1], line)
            if truthy(interp.call(args[0], [item], line))]


def _reduce(interp, args, line):
    items = list(interp.iterate(args[1], line))
    if len(args) > 2:
        acc, rest = args[2], items
    elif items:
        acc, rest = items[0], items[1:]
    else:
        raise NoonRuntimeError("«اختزل» على قائمة فارغة بلا قيمة ابتدائية", line)
    for item in rest:
        acc = interp.call(args[0], [acc, item], line)
    return acc


def _to_list(interp, args, line):
    return list(interp.iterate(args[0], line))


def _is_instance(interp, args, line):
    obj, klass = args[0], args[1]
    if not isinstance(klass, NoonClass):
        raise NoonRuntimeError("الوسيط الثاني لـ«من_صنف» يجب أن يكون صنفًا", line)
    if not isinstance(obj, NoonInstance):
        return False
    current = obj.klass
    while current is not None:
        if current is klass:
            return True
        current = current.parent
    return False


def _assert(interp, args, line):
    if not truthy(args[0]):
        message = interp.stringify(args[1]) if len(args) > 1 else "فشل التحقّق"
        raise NoonRuntimeError(message, line)
    return None


# ——— ما يلزم لكتابة برامج أدوات بـ«نون» نفسها، ومنها مُفسِّرها (selfhost/) ———

# وسائط البرنامج بعد اسم ملفه في سطر الأوامر؛ يملؤها cli.main
PROGRAM_ARGS = []


def _code_point(interp, args, line):
    value = args[0]
    if not isinstance(value, str) or len(value) != 1:
        raise NoonRuntimeError("«رمز» تحتاج نصًّا من حرف واحد، لا «%s»"
                               % interp.stringify(value), line)
    return ord(value)


def _character(interp, args, line):
    code = _need_int(args[0], line, "وسيط «محرف»")
    if not 0 <= code <= 0x10FFFF:
        raise NoonRuntimeError("«محرف» تحتاج رقمًا بين 0 و1114111، لا %d" % code, line)
    return chr(code)


def _read_file(interp, args, line):
    path = args[0]
    if not isinstance(path, str):
        raise NoonRuntimeError("مسار الملف يجب أن يكون نصًّا", line)
    try:
        with open(path, encoding="utf-8-sig") as handle:
            return handle.read()
    except FileNotFoundError:
        raise NoonRuntimeError("لا يوجد ملف بالمسار: %s" % path, line)
    except UnicodeDecodeError:
        raise NoonRuntimeError("الملف «%s» ليس نصًّا بترميز UTF-8" % path, line)
    except OSError as error:
        raise NoonRuntimeError("تعذّرت قراءة الملف «%s»: %s" % (path, error.strerror or error), line)


def _save_compiled(interp, args, line):
    """يكتب ملف ‎.noonc من بنية دالة مُترجَمة مصنوعة بـ«نون» (selfhost/noon.noon).

    «نون» لا تعرف البايتات، فترميز البنية ملفًّا هو الخطوة الوحيدة في مترجِمها
    الذاتي المكتوبة بـ Python. البنية هي ترتيب bytecode._to_data نفسه.
    """
    from .bytecode import _from_data, dumps

    path, data = args
    if not isinstance(path, str):
        raise NoonRuntimeError("مسار الملف يجب أن يكون نصًّا", line)
    try:
        compiled = _from_data(data)
    except (ValueError, TypeError, IndexError, KeyError) as error:
        raise NoonRuntimeError("بنية مُترجَمة غير صالحة: %s" % error, line)
    blob = dumps(compiled)
    try:
        with open(path, "wb") as handle:
            handle.write(blob)
    except OSError as error:
        raise NoonRuntimeError("تعذّرت كتابة الملف «%s»: %s" % (path, error.strerror or error), line)
    return len(blob)


def _import(interp, args, line):
    return interp.import_module(args[0], line)


def _member(interp, args, line):
    obj, name = args
    if not isinstance(name, str):
        raise NoonRuntimeError("اسم العضو يجب أن يكون نصًّا", line)
    return interp.get_member(obj, name, line)


GLOBALS = {
    "اطبع": BuiltinFunction("اطبع", _print, 0, -1),
    "اقرأ": BuiltinFunction("اقرأ", _read, 0, 1),
    "طول": BuiltinFunction("طول", _len, 1),
    "نوع": BuiltinFunction("نوع", lambda i, a, l: type_name(a[0]), 1),
    "نص": BuiltinFunction("نص", lambda i, a, l: i.stringify(a[0]), 1),
    "عدد": BuiltinFunction("عدد", lambda i, a, l: _to_number(a[0], l), 1),
    "منطقي": BuiltinFunction("منطقي", lambda i, a, l: truthy(a[0]), 1),
    "قائمة": BuiltinFunction("قائمة", _to_list, 1),
    "مدى": BuiltinFunction("مدى", _range, 1, 3),
    "مجموع": BuiltinFunction("مجموع", _sum, 1),
    "أقصى": BuiltinFunction("أقصى", _minmax("max"), 1, -1),
    "أدنى": BuiltinFunction("أدنى", _minmax("min"), 1, -1),
    "مطلق": BuiltinFunction("مطلق", lambda i, a, l: abs(_need_number(a[0], l)), 1),
    "جذر": BuiltinFunction("جذر", lambda i, a, l: math.sqrt(_need_number(a[0], l)), 1),
    "تقريب": BuiltinFunction(
        "تقريب",
        lambda i, a, l: round(_need_number(a[0], l),
                              _need_int(a[1], l) if len(a) > 1 else 0), 1, 2),
    "أرضية": BuiltinFunction("أرضية", lambda i, a, l: math.floor(_need_number(a[0], l)), 1),
    "سقف": BuiltinFunction("سقف", lambda i, a, l: math.ceil(_need_number(a[0], l)), 1),
    "فرز": BuiltinFunction("فرز", _sorted, 1, 3),
    "عكس": BuiltinFunction("عكس", _reversed, 1),
    "طبّق": BuiltinFunction("طبّق", _map, 2),
    "رشّح": BuiltinFunction("رشّح", _filter, 2),
    "اختزل": BuiltinFunction("اختزل", _reduce, 2, 3),
    "عشوائي": BuiltinFunction(
        "عشوائي",
        lambda i, a, l: (random.random() if not a else
                         random.randint(_need_int(a[0], l), _need_int(a[1], l))
                         if len(a) > 1 else random.randrange(_need_int(a[0], l))),
        0, 2),
    "وقت": BuiltinFunction("وقت", lambda i, a, l: time.time(), 0),
    "من_صنف": BuiltinFunction("من_صنف", _is_instance, 2),
    "تحقّق": BuiltinFunction("تحقّق", _assert, 1, 2),
    "متساويان": BuiltinFunction("متساويان", lambda i, a, l: equals(a[0], a[1]), 2),
    "أرقام_عربية": BuiltinFunction(
        "أرقام_عربية",
        lambda i, a, l: set_arabic_digits(truthy(a[0]) if a else True), 0, 1),
    "رمز": BuiltinFunction("رمز", _code_point, 1),
    "محرف": BuiltinFunction("محرف", _character, 1),
    "اقرأ_ملف": BuiltinFunction("اقرأ_ملف", _read_file, 1),
    "وسائط": BuiltinFunction("وسائط", lambda i, a, l: list(PROGRAM_ARGS), 0),
    "عضو": BuiltinFunction("عضو", _member, 2),
    "احفظ_مترجما": BuiltinFunction("احفظ_مترجما", _save_compiled, 2),
    "استورد": BuiltinFunction("استورد", _import, 1),
    "باي": math.pi,
}


# ———————————————— توابع الأنواع ————————————————

def _str_split(interp, args, line):
    text = args[0]
    if not args[1:]:
        return text.split()
    sep = args[1]
    return text.split(sep) if sep else list(text)


def _index_of(interp, args, line):
    haystack, needle = args[0], args[1]
    try:
        return haystack.index(needle)
    except ValueError:
        return -1


def _list_remove(interp, args, line):
    items, index = args[0], _need_int(args[1], line, "الفهرس")
    if not -len(items) <= index < len(items):
        raise NoonRuntimeError("الفهرس %d خارج حدود القائمة" % index, line)
    return items.pop(index)


def _dict_remove(interp, args, line):
    mapping, key = args[0], args[1]
    if key not in mapping:
        raise NoonRuntimeError("المفتاح «%s» غير موجود" % stringify(key), line)
    return mapping.pop(key)


def _join(interp, args, line):
    sep = interp.stringify(args[1]) if len(args) > 1 else ""
    return sep.join(interp.stringify(item) for item in args[0])


def _slice(interp, args, line):
    value = args[0]
    start = _need_int(args[1], line, "البداية")
    end = _need_int(args[2], line, "النهاية") if len(args) > 2 else None
    return value[start:end]


def _m(name, fn, min_args=0, max_args=None):
    """يبني تابعًا؛ الوسيط الأول دائمًا القيمة المستقبِلة."""
    return BuiltinFunction(name, fn, min_args + 1,
                           -1 if max_args == -1 else (max_args or min_args) + 1)


STRING_METHODS = {
    "طول": _m("طول", lambda i, a, l: len(a[0])),
    "قص": _m("قص", lambda i, a, l: a[0].strip(a[1]) if len(a) > 1 else a[0].strip(), 0, 1),
    "تقسيم": _m("تقسيم", _str_split, 0, 1),
    "استبدل": _m("استبدل", lambda i, a, l: a[0].replace(a[1], a[2]), 2),
    "يحتوي": _m("يحتوي", lambda i, a, l: a[1] in a[0], 1),
    "يبدأ": _m("يبدأ", lambda i, a, l: a[0].startswith(a[1]), 1),
    "ينتهي": _m("ينتهي", lambda i, a, l: a[0].endswith(a[1]), 1),
    "موضع": _m("موضع", _index_of, 1),
    "مقطع": _m("مقطع", _slice, 1, 2),
    "تكرار": _m("تكرار", lambda i, a, l: a[0] * _need_int(a[1], l, "عدد التكرار"), 1),
    "عكس": _m("عكس", lambda i, a, l: a[0][::-1]),
    "كبير": _m("كبير", lambda i, a, l: a[0].upper()),
    "صغير": _m("صغير", lambda i, a, l: a[0].lower()),
    "أحرف": _m("أحرف", lambda i, a, l: list(a[0])),
}

LIST_METHODS = {
    "طول": _m("طول", lambda i, a, l: len(a[0])),
    "أضف": _m("أضف", lambda i, a, l: (a[0].extend(a[1:]), a[0])[1], 1, -1),
    "احذف": _m("احذف", _list_remove, 1),
    "إدراج": _m("إدراج", lambda i, a, l: (a[0].insert(_need_int(a[1], l), a[2]), a[0])[1], 2),
    "يحتوي": _m("يحتوي", lambda i, a, l: any(equals(x, a[1]) for x in a[0]), 1),
    "موضع": _m("موضع", lambda i, a, l: next(
        (n for n, x in enumerate(a[0]) if equals(x, a[1])), -1), 1),
    "فرز": _m("فرز", lambda i, a, l: _sorted(i, a, l), 0, 2),
    "عكس": _m("عكس", lambda i, a, l: a[0][::-1]),
    "وصل": _m("وصل", _join, 0, 1),
    "مقطع": _m("مقطع", _slice, 1, 2),
    "نسخة": _m("نسخة", lambda i, a, l: list(a[0])),
    "مسح": _m("مسح", lambda i, a, l: (a[0].clear(), a[0])[1]),
    "ادمج": _m("ادمج", lambda i, a, l: a[0] + list(a[1]), 1),
}

DICT_METHODS = {
    "طول": _m("طول", lambda i, a, l: len(a[0])),
    "مفاتيح": _m("مفاتيح", lambda i, a, l: list(a[0].keys())),
    "قيم": _m("قيم", lambda i, a, l: list(a[0].values())),
    "عناصر": _m("عناصر", lambda i, a, l: [[k, v] for k, v in a[0].items()]),
    "يحتوي": _m("يحتوي", lambda i, a, l: a[1] in a[0], 1),
    "احذف": _m("احذف", _dict_remove, 1),
    "اجلب": _m("اجلب", lambda i, a, l: a[0].get(a[1], a[2] if len(a) > 2 else None), 1, 2),
    "ضع": _m("ضع", lambda i, a, l: (a[0].__setitem__(a[1], a[2]), a[0])[1], 2),
    "نسخة": _m("نسخة", lambda i, a, l: dict(a[0])),
    "مسح": _m("مسح", lambda i, a, l: (a[0].clear(), a[0])[1]),
}


def _with_normalized(table):
    """يقبل الكتابة بالهمزة أو بدونها وبالشدّة أو بدونها: «أضف» و«اضف» سواء."""
    out = dict(table)
    for key, value in table.items():
        out.setdefault(fold(key), value)
    return out


STRING_METHODS = _with_normalized(STRING_METHODS)
LIST_METHODS = _with_normalized(LIST_METHODS)
DICT_METHODS = _with_normalized(DICT_METHODS)
GLOBALS = _with_normalized(GLOBALS)


def methods_for(value):
    if isinstance(value, str):
        return STRING_METHODS
    if isinstance(value, list):
        return LIST_METHODS
    if isinstance(value, dict):
        return DICT_METHODS
    return None
