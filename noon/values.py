# -*- coding: utf-8 -*-
"""قيم اللغة: الدوال والأصناف والكائنات، وأدوات التحويل والمقارنة.

هذه الوحدة لا تعتمد على المُفسِّر حتى لا تنشأ دورة استيراد؛ كل ما يحتاج
إلى استدعاء دالة من داخل اللغة يستقبل المُفسِّر كوسيط.
"""

from .errors import NoonRuntimeError


class NoonFunction:
    """دالة مُعرَّفة داخل اللغة، تحمل بيئتها (closure)."""

    def __init__(self, name, params, body, closure, is_method=False):
        self.name = name or "دالة مجهولة"
        self.params = params          # قائمة من (الاسم، القيمة الافتراضية أو None)
        self.body = body
        self.closure = closure
        self.is_method = is_method

    def bind(self, instance, klass):
        """يُرجع نسخة من الدالة مربوطة بكائن، لتعمل فيها «هذا» و«الأصل»."""
        from .interpreter import Environment  # استيراد مؤجَّل لتفادي الدورة

        env = Environment(self.closure)
        env.declare("هذا", instance)
        if klass is not None and klass.parent is not None:
            env.declare("الأصل", SuperProxy(instance, klass.parent))
        bound = NoonFunction(self.name, self.params, self.body, env, True)
        return bound

    def __repr__(self):
        return "<دالة %s>" % self.name


class Cell:
    """صندوق لمتغيّر التقطته دالة داخلية، فيراه الاثنان ويتغيّر للاثنين."""

    __slots__ = ("value",)

    def __init__(self, value=None):
        self.value = value

    def __repr__(self):
        return "<خليّة %r>" % (self.value,)


class Closure:
    """دالة مُترجَمة مع خلاياها الملتقَطة — نظير NoonFunction في الآلة الافتراضية."""

    __slots__ = ("function", "cells", "owner")

    def __init__(self, function, cells=(), owner=None):
        self.function = function
        self.cells = cells
        self.owner = owner            # الصنف الذي عُرِّف فيه التابع، لأجل «الأصل»

    @property
    def name(self):
        return self.function.name

    def bind(self, instance, klass):
        """يربط التابع بكائن: `هذا` هو الوسيط الأول عند الاستدعاء."""
        return BoundMethod(self, instance, klass)

    def __repr__(self):
        return "<دالة %s>" % self.function.name


class BoundMethod:
    """تابع مربوط بكائن؛ يمرّر الكائن وسيطًا أوّل عند النداء."""

    __slots__ = ("closure", "instance", "owner")

    def __init__(self, closure, instance, owner):
        self.closure = closure
        self.instance = instance
        self.owner = owner

    @property
    def name(self):
        return self.closure.function.name

    def __repr__(self):
        return "<تابع %s>" % self.name


class BuiltinFunction:
    """دالة مدمجة مكتوبة بـ Python. توقيعها: fn(interp, args, line)."""

    def __init__(self, name, fn, min_args=0, max_args=None):
        self.name = name
        self.fn = fn
        self.min_args = min_args
        self.max_args = min_args if max_args is None else max_args

    def check(self, count, line):
        if count < self.min_args or (self.max_args >= 0 and count > self.max_args):
            expected = (str(self.min_args) if self.min_args == self.max_args
                        else "%d..%s" % (self.min_args,
                                         "∞" if self.max_args < 0 else self.max_args))
            raise NoonRuntimeError(
                "الدالة «%s» تتوقّع %s وسيطًا، ووصلها %d" % (self.name, expected, count),
                line)

    def __repr__(self):
        return "<دالة مدمجة %s>" % self.name


class BoundBuiltin:
    """تابع مدمج مربوط بقيمة، مثل قائمة.أضف أو نص.تقسيم."""

    def __init__(self, receiver, builtin):
        self.receiver = receiver
        self.builtin = builtin

    @property
    def name(self):
        return self.builtin.name

    def __repr__(self):
        return "<تابع %s>" % self.builtin.name


class NoonClass:
    """صنف: اسم، أب اختياري، وجدول توابع."""

    def __init__(self, name, parent, methods):
        self.name = name
        self.parent = parent
        self.methods = methods

    def find_method(self, name):
        klass = self
        while klass is not None:
            if name in klass.methods:
                return klass, klass.methods[name]
            klass = klass.parent
        return None, None

    def __repr__(self):
        return "<صنف %s>" % self.name


class NoonInstance:
    """كائن مُنشأ من صنف."""

    def __init__(self, klass):
        self.klass = klass
        self.fields = {}

    def get(self, name, line=None):
        if name in self.fields:
            return self.fields[name]
        owner, method = self.klass.find_method(name)
        if method is not None:
            return method.bind(self, owner)
        raise NoonRuntimeError(
            "الكائن من الصنف «%s» لا يملك «%s»" % (self.klass.name, name), line)

    def set(self, name, value):
        self.fields[name] = value

    def __repr__(self):
        return "<كائن %s>" % self.klass.name


class SuperProxy:
    """«الأصل» داخل التوابع: يبحث عن التابع في الصنف الأب ويربطه بالكائن نفسه."""

    def __init__(self, instance, parent):
        self.instance = instance
        self.parent = parent

    def get(self, name, line=None):
        owner, method = self.parent.find_method(name)
        if method is None:
            raise NoonRuntimeError(
                "الصنف الأب «%s» لا يملك التابع «%s»" % (self.parent.name, name), line)
        return method.bind(self.instance, owner)


CALLABLES = (NoonFunction, BuiltinFunction, BoundBuiltin, NoonClass,
             Closure, BoundMethod)


# ——————————————————— أدوات على القيم ———————————————————

_ARABIC_INDIC = "٠١٢٣٤٥٦٧٨٩"
_TO_ARABIC = {ord(str(i)): _ARABIC_INDIC[i] for i in range(10)}
_TO_ARABIC[ord(".")] = "٫"
_STATE = {"arabic_digits": False}


def set_arabic_digits(enabled):
    """هل تُعرَض الأعداد بالأرقام العربية-الهندية (٠٩) أم باللاتينية؟"""
    _STATE["arabic_digits"] = bool(enabled)


def arabic_digits_enabled():
    return _STATE["arabic_digits"]


def localize_digits(text):
    return text.translate(_TO_ARABIC) if _STATE["arabic_digits"] else text


def type_name(value):
    """اسم نوع القيمة كما يراه مبرمج «نون»."""
    if value is None:
        return "عدم"
    if isinstance(value, bool):
        return "منطقي"
    if isinstance(value, (int, float)):
        return "عدد"
    if isinstance(value, str):
        return "نص"
    if isinstance(value, list):
        return "قائمة"
    if isinstance(value, dict):
        return "قاموس"
    if isinstance(value, NoonClass):
        return "صنف"
    if isinstance(value, NoonInstance):
        return value.klass.name
    if isinstance(value, (NoonFunction, BuiltinFunction, BoundBuiltin,
                          Closure, BoundMethod)):
        return "دالة"
    return "غير معروف"


def is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def format_number(value):
    """٣ بدل ٣٫٠، ومنع الصيغة العلمية القبيحة في الأعداد الصغيرة."""
    if isinstance(value, int):
        return localize_digits(str(value))
    if value != value:            # not a number
        return "ليس_عددًا"
    if value in (float("inf"), float("-inf")):
        return "لانهاية" if value > 0 else "-لانهاية"
    if float(value).is_integer() and abs(value) < 1e16:
        return localize_digits(str(int(value)))
    return localize_digits(repr(float(value)))


def stringify(value, quote=False):
    """تحويل أي قيمة إلى نص للعرض. quote يضع النصوص بين علامتي اقتباس."""
    if value is None:
        return "عدم"
    if isinstance(value, bool):
        return "صحيح" if value else "خطأ"
    if isinstance(value, (int, float)):
        return format_number(value)
    if isinstance(value, str):
        return '"%s"' % value if quote else value
    if isinstance(value, list):
        return "[" + "، ".join(stringify(v, True) for v in value) + "]"
    if isinstance(value, dict):
        return "{" + "، ".join(
            "%s: %s" % (stringify(k, True), stringify(v, True))
            for k, v in value.items()) + "}"
    if isinstance(value, NoonInstance):
        # الصنف الذي يُعرِّف تابع «نص» يُعرض به؛ الاستدعاء يتم في المُفسِّر
        # (انظر Interpreter.stringify) لأن هذه الوحدة لا تستدعي دوال اللغة.
        return "<كائن %s>" % value.klass.name
    return repr(value)


def truthy(value):
    """ما يُعدّ «صحيحًا» في شرط: كل شيء عدا عدم، خطأ، صفر، والفراغ."""
    if value is None or value is False:
        return False
    if value is True:
        return True
    if is_number(value):
        return value != 0
    if isinstance(value, (str, list, dict)):
        return len(value) > 0
    return True


def equals(a, b):
    """مساواة صارمة: المنطقي لا يساوي العدد."""
    if isinstance(a, bool) != isinstance(b, bool):
        return False
    if a is None or b is None:
        return a is None and b is None
    if is_number(a) and is_number(b):
        return a == b              # مقارنة بايثون بين int وfloat دقيقة؛ float() كانت تُضيّع الأعداد الكبيرة
    if type(a) is not type(b):
        return False
    if isinstance(a, list):
        return len(a) == len(b) and all(equals(x, y) for x, y in zip(a, b))
    if isinstance(a, dict):
        if len(a) != len(b):
            return False
        return all(k in b and equals(v, b[k]) for k, v in a.items())
    return a is b if isinstance(a, (NoonInstance, NoonClass)) else a == b
