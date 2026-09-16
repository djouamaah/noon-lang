# -*- coding: utf-8 -*-
"""أخطاء لغة «نون» وإشارات التحكّم في التدفّق."""


class NoonError(Exception):
    """الأصل لكل أخطاء اللغة التي تُعرض للمستخدم."""

    kind = "خطأ"

    def __init__(self, message, line=None, col=None):
        super().__init__(message)
        self.message = message
        self.line = line
        self.col = col

    def __str__(self):
        if self.line:
            return "%s [سطر %d]: %s" % (self.kind, self.line, self.message)
        return "%s: %s" % (self.kind, self.message)


class NoonSyntaxError(NoonError):
    """خطأ في صياغة الشيفرة، يُكتشف قبل التشغيل."""

    kind = "خطأ نحوي"


class NoonRuntimeError(NoonError):
    """خطأ أثناء التنفيذ."""

    kind = "خطأ تشغيل"


class NoonThrow(Exception):
    """قيمة مرميّة بالأمر «ارمِ»، تلتقطها «امسك»."""

    def __init__(self, value, line=None):
        super().__init__("قيمة مرميّة")
        self.value = value
        self.line = line


# ——— إشارات التحكّم في التدفّق (ليست أخطاء) ———

class BreakSignal(Exception):
    def __init__(self, line=None):
        super().__init__("توقف")
        self.line = line


class ContinueSignal(Exception):
    def __init__(self, line=None):
        super().__init__("استمر")
        self.line = line


class ReturnSignal(Exception):
    def __init__(self, value, line=None):
        super().__init__("أرجع")
        self.value = value
        self.line = line


# رسائل استعمال هذه الكلمات في غير موضعها؛ يتقاسمها المحرّكان
MISPLACED = {
    "break": "«توقف» لا تُستعمل إلا داخل حلقة",
    "continue": "«استمر» لا تُستعمل إلا داخل حلقة",
    "return": "«أرجع» لا تُستعمل إلا داخل دالة",
}
