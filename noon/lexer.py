# -*- coding: utf-8 -*-
"""المُحلِّل اللفظي: يحوّل نصّ البرنامج إلى سلسلة رموز (tokens)."""

from .errors import NoonSyntaxError

# ——— الأرقام العربية والهندية ———
_DIGIT_MAP = {}
for _i in range(10):
    _DIGIT_MAP[str(_i)] = str(_i)                       # 0-9
    _DIGIT_MAP[chr(0x0660 + _i)] = str(_i)              # ٠-٩ عربية-هندية
    _DIGIT_MAP[chr(0x06F0 + _i)] = str(_i)              # ۰-۹ فارسية

_DECIMAL_SEPS = ".٫"
_THOUSANDS_SEPS = "٬_"           # الفاصلة العشرية العربية تُكتب ٫ والآلاف ٬

TATWEEL = "ـ"
_DIACRITICS = set(range(0x064B, 0x0656)) | {0x0670, 0x06D6, 0x0640}


def normalize(word):
    """توحيد الهمزات لمطابقة الكلمات المفتاحية: «إذا» و«اذا» سواء.

    التشكيل *لا* يُحذف هنا عمدًا: لو حُذف لصارت «صنّف» هي الكلمة
    المفتاحية «صنف»، ولامتنع على المبرمج تسمية دالته «صنّف» أو «رشّح».
    """
    out = []
    for ch in word:
        if ch == TATWEEL:
            continue
        if ch in "أإآٱ":
            ch = "ا"
        elif ch == "ى":
            ch = "ي"
        elif ch == "ة":
            ch = "ه"
        out.append(ch)
    return "".join(out)


def fold(word):
    """توحيد أوسع (يحذف التشكيل أيضًا) لأسماء الدوال والتوابع المدمجة.

    يُستعمل لتسجيل أسماء بديلة فقط، فلا يسلب المبرمج أسماءه: «رشّح»
    تُكتب «رشح»، و«أضف» تُكتب «اضف».
    """
    return normalize("".join(ch for ch in word if ord(ch) not in _DIACRITICS))


_RAW_KEYWORDS = {
    "متغير": "VAR",
    "ثابت": "CONST",
    "دالة": "FUNC",
    "أرجع": "RETURN",
    "إذا": "IF",
    "وإلا": "ELSE",
    "طالما": "WHILE",
    "لكل": "FOR",
    "في": "IN",
    "توقف": "BREAK",
    "استمر": "CONTINUE",
    "صحيح": "TRUE",
    "خطأ": "FALSE",
    "عدم": "NULL",
    "و": "AND",
    "أو": "OR",
    "ليس": "NOT",
    "صنف": "CLASS",
    "يرث": "EXTENDS",
    "هذا": "THIS",
    "الأصل": "SUPER",
    "حاول": "TRY",
    "امسك": "CATCH",
    "أخيرًا": "FINALLY",
    "أخيرا": "FINALLY",
    "ارمِ": "THROW",
    "ارم": "THROW",
}
KEYWORDS = {normalize(k): v for k, v in _RAW_KEYWORDS.items()}

_TWO_CHAR = {
    "**": "POW", "==": "EQ", "!=": "NE", "<=": "LE", ">=": "GE",
    "+=": "PLUS_EQ", "-=": "MINUS_EQ", "*=": "STAR_EQ", "/=": "SLASH_EQ",
    "//": "DSLASH", "&&": "AND", "||": "OR",
}

_ONE_CHAR = {
    "+": "PLUS", "-": "MINUS", "*": "STAR", "/": "SLASH", "%": "PERCENT",
    "=": "ASSIGN", "<": "LT", ">": "GT", "!": "NOT",
    "(": "LPAREN", ")": "RPAREN", "[": "LBRACKET", "]": "RBRACKET",
    "{": "LBRACE", "}": "RBRACE", ":": "COLON", ".": "DOT",
    ",": "COMMA", "،": "COMMA",
    ";": "NEWLINE", "؛": "NEWLINE",
}

_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", '"': '"', "'": "'",
            "0": "\0"}


class Token:
    __slots__ = ("type", "value", "line", "col")

    def __init__(self, type_, value, line, col):
        self.type = type_
        self.value = value
        self.line = line
        self.col = col

    def __repr__(self):
        return "Token(%s, %r, سطر %d)" % (self.type, self.value, self.line)


class Lexer:
    def __init__(self, source):
        self.src = source
        self.i = 0
        self.line = 1
        self.col = 1
        self.depth = 0           # عمق الأقواس () و[] لتجاهل نهايات الأسطر داخلها
        self.tokens = []

    # ——— أدوات صغيرة ———
    def _peek(self, offset=0):
        j = self.i + offset
        return self.src[j] if j < len(self.src) else ""

    def _advance(self):
        ch = self.src[self.i]
        self.i += 1
        if ch == "\n":
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return ch

    def _add(self, type_, value, line=None, col=None):
        self.tokens.append(Token(type_, value,
                                 self.line if line is None else line,
                                 self.col if col is None else col))

    def _error(self, message):
        raise NoonSyntaxError(message, self.line, self.col)

    # ——— الحلقة الرئيسة ———
    def tokenize(self):
        while self.i < len(self.src):
            ch = self._peek()

            if ch == "\n":
                line, col = self.line, self.col
                self._advance()
                if self.depth == 0 and self._last_type() not in (None, "NEWLINE"):
                    self._add("NEWLINE", "\\n", line, col)
                continue

            if ch in " \t\r﻿‏‎":
                self._advance()
                continue

            if ch == "#":
                while self.i < len(self.src) and self._peek() != "\n":
                    self._advance()
                continue

            if ch in _DIGIT_MAP:
                self._number()
                continue

            if ch in "\"'":
                self._string(ch)
                continue

            if ch.isalpha() or ch == "_":
                self._identifier()
                continue

            two = self.src[self.i:self.i + 2]
            if two in _TWO_CHAR:
                line, col = self.line, self.col
                self._advance(); self._advance()
                self._add(_TWO_CHAR[two], two, line, col)
                continue

            if ch in _ONE_CHAR:
                line, col = self.line, self.col
                type_ = _ONE_CHAR[ch]
                self._advance()
                if ch in "([":
                    self.depth += 1
                elif ch in ")]":
                    self.depth = max(0, self.depth - 1)
                if type_ == "NEWLINE" and self._last_type() in (None, "NEWLINE"):
                    continue
                self._add(type_, ch, line, col)
                continue

            self._error("رمز غير معروف: «%s»" % ch)

        if self._last_type() not in (None, "NEWLINE"):
            self._add("NEWLINE", "\\n")
        self._add("EOF", None)
        return self.tokens

    def _last_type(self):
        return self.tokens[-1].type if self.tokens else None

    # ——— الأعداد ———
    def _number(self):
        line, col = self.line, self.col
        digits = []
        seen_dot = False
        while self.i < len(self.src):
            ch = self._peek()
            if ch in _DIGIT_MAP:
                digits.append(_DIGIT_MAP[ch])
                self._advance()
            elif ch in _THOUSANDS_SEPS:
                self._advance()                     # فاصل آلاف تجميلي
            elif ch in _DECIMAL_SEPS and not seen_dot and self._peek(1) in _DIGIT_MAP:
                seen_dot = True
                digits.append(".")
                self._advance()
            else:
                break
        text = "".join(digits)
        value = float(text) if seen_dot else int(text)
        self._add("NUMBER", value, line, col)

    # ——— النصوص ———
    def _string(self, quote):
        line, col = self.line, self.col
        self._advance()
        out = []
        while True:
            if self.i >= len(self.src):
                raise NoonSyntaxError("نصّ لم يُغلق", line, col)
            ch = self._advance()
            if ch == quote:
                break
            if ch == "\n":
                raise NoonSyntaxError("نصّ لم يُغلق قبل نهاية السطر", line, col)
            if ch == "\\":
                nxt = self._advance() if self.i < len(self.src) else ""
                if nxt == "u":
                    hexits = ""
                    for _ in range(4):
                        if self.i < len(self.src):
                            hexits += self._advance()
                    try:
                        out.append(chr(int(hexits, 16)))
                    except ValueError:
                        self._error("تهريب \\u غير صالح")
                else:
                    # المعروف يُترجم، وما لا يُعرف يبقى كما كُتب:
                    # "C:\Users" تبقى C:\Users لا C:Users
                    out.append(_ESCAPES.get(nxt, "\\" + nxt) if nxt else "\\")
                continue
            out.append(ch)
        self._add("STRING", "".join(out), line, col)

    # ——— المعرِّفات والكلمات المفتاحية ———
    def _identifier(self):
        line, col = self.line, self.col
        start = self.i
        while self.i < len(self.src):
            ch = self._peek()
            if ch.isalpha() or ch == "_" or ch in _DIGIT_MAP or ord(ch) in _DIACRITICS:
                self._advance()
            else:
                break
        raw = self.src[start:self.i]
        key = normalize(raw)
        if key in KEYWORDS:
            self._add(KEYWORDS[key], raw, line, col)
        else:
            self._add("IDENT", raw, line, col)


def tokenize(source):
    return Lexer(source).tokenize()
