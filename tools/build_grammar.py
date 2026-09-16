# -*- coding: utf-8 -*-
"""يولّد قواعد تلوين صيغة «نون» لـ VS Code من تعريف اللغة نفسه.

مصدر الحقيقة الوحيد هو `noon/lexer.py` و`noon/builtins.py`: الكلمات
المفتاحية والدوال المدمجة تُقرأ منهما، فلا ينحرف المُلوِّن عن المُفسِّر.

    python tools/build_grammar.py            # يكتب الملف
    python tools/build_grammar.py --check    # يتحقّق أنه محدَّث فقط
"""

import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from noon import builtins as B          # noqa: E402
from noon.lexer import _RAW_KEYWORDS    # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, "editors", "vscode", "syntaxes", "noon.tmLanguage.json")

# حروف تُعدّ جزءًا من الاسم في `lexer._identifier`: حروف وأرقام وشرطة سفلية
# وتشكيل وتطويل. تُستعمل حدودًا للكلمات بدل \b الذي لا يفهم التشكيل.
WORD_CHAR = r"[\p{L}\p{N}_\x{064B}-\x{0655}\x{0670}\x{0640}]"
BEFORE = r"(?<!%s)" % WORD_CHAR
AFTER = r"(?!%s)" % WORD_CHAR

IDENT = r"[\p{L}_]%s*" % WORD_CHAR
DIGIT = r"[0-9\x{0660}-\x{0669}\x{06F0}-\x{06F9}]"

# الكلمات المفتاحية مجموعةً بحسب دورها في التلوين
GROUPS = {
    "conditional": ["إذا", "وإلا"],
    "loop": ["طالما", "لكل", "في", "توقف", "استمر"],
    "flow": ["أرجع", "حاول", "امسك", "أخيرًا", "أخيرا", "ارمِ", "ارم"],
    "storage": ["متغير", "ثابت", "دالة", "صنف"],
    "modifier": ["يرث"],
    "logical": ["و", "أو", "ليس"],
    "constant": ["صحيح", "خطأ", "عدم"],
    "language_variable": ["هذا", "الأصل"],
}


def variants(word):
    """صيغة تقبل ما يقبله `lexer.normalize`: الهمزات والألف المقصورة والتاء."""
    out = []
    for ch in word:
        if ch in "اأإآٱ":
            out.append("[اأإآٱ]")
        elif ch in "يى":
            out.append("[يى]")
        elif ch in "ةه":
            out.append("[ةه]")
        else:
            out.append(ch)
    return "".join(out)


def alternation(words):
    """أطول أوّلًا حتى لا تبتلع كلمةٌ قصيرة بدايةَ أطول منها."""
    ordered = sorted(set(words), key=lambda w: (-len(w), w))
    return "|".join(variants(word) for word in ordered)


def keyword_rule(words, scope):
    return {"name": scope, "match": "%s(?:%s)%s" % (BEFORE, alternation(words), AFTER)}


def check_keywords_cover_the_lexer():
    """كل كلمة مفتاحية في المُفسِّر لها لون؛ وإلا فالمُلوِّن ناقص."""
    coloured = {w for words in GROUPS.values() for w in words}
    missing = sorted(set(_RAW_KEYWORDS) - coloured)
    if missing:
        raise SystemExit("كلمات مفتاحية بلا تلوين: %s" % "، ".join(missing))


def builtin_names():
    return [name for name, value in B.GLOBALS.items() if name != "باي"]


def method_names():
    names = set()
    for table in (B.STRING_METHODS, B.LIST_METHODS, B.DICT_METHODS):
        names.update(table)
    return sorted(names)


def build():
    check_keywords_cover_the_lexer()

    return {
        "$schema": "https://raw.githubusercontent.com/martinring/tmlanguage/master/tmlanguage.json",
        "name": "نون",
        "scopeName": "source.noon",
        "fileTypes": ["noon", "نون"],
        "_مولَّد": "لا تُحرِّر هذا الملف يدويًّا — أعِد توليده بـ tools/build_grammar.py",
        "patterns": [
            {"include": "#comments"},
            {"include": "#strings"},
            {"include": "#numbers"},
            {"include": "#declarations"},
            {"include": "#keywords"},
            {"include": "#constants"},
            {"include": "#methods"},
            {"include": "#members"},
            {"include": "#calls"},
            {"include": "#operators"},
            {"include": "#punctuation"},
        ],
        "repository": {
            "comments": {
                "patterns": [{
                    "name": "comment.line.number-sign.noon",
                    "begin": "#",
                    "end": "$",
                    "beginCaptures": {
                        "0": {"name": "punctuation.definition.comment.noon"}},
                }],
            },

            "strings": {
                "patterns": [
                    {
                        "name": "string.quoted.double.noon",
                        "begin": '"',
                        "end": '"',
                        "beginCaptures": {
                            "0": {"name": "punctuation.definition.string.begin.noon"}},
                        "endCaptures": {
                            "0": {"name": "punctuation.definition.string.end.noon"}},
                        "patterns": [{"include": "#escapes"}],
                    },
                    {
                        "name": "string.quoted.single.noon",
                        "begin": "'",
                        "end": "'",
                        "beginCaptures": {
                            "0": {"name": "punctuation.definition.string.begin.noon"}},
                        "endCaptures": {
                            "0": {"name": "punctuation.definition.string.end.noon"}},
                        "patterns": [{"include": "#escapes"}],
                    },
                ],
            },

            "escapes": {
                "patterns": [
                    # ما عدا هذه تبقى الشرطة المائلة حرفيةً كما في المُفسِّر
                    {"name": "constant.character.escape.noon",
                     "match": r"\\(?:u[0-9A-Fa-f]{4}|[nrt0\\\"'])"},
                ],
            },

            "numbers": {
                "patterns": [{
                    "name": "constant.numeric.noon",
                    # ١٢٣  ١٬٠٠٠  ٣٫٥  3.5  — الأرقام العربية واللاتينية سواء
                    "match": r"%s(?:%s[%s\x{066C}_]*(?:[.\x{066B}]%s+)?)%s"
                             % (BEFORE, DIGIT, DIGIT[1:-1], DIGIT, AFTER),
                }],
            },

            "declarations": {
                "patterns": [
                    {
                        # صنف مربّع يرث مستطيل
                        "match": r"%s(%s)\s+(%s)(?:\s+(%s)\s+(%s))?"
                                 % (BEFORE, variants("صنف"), IDENT,
                                    variants("يرث"), IDENT),
                        "captures": {
                            "1": {"name": "storage.type.class.noon"},
                            "2": {"name": "entity.name.type.class.noon"},
                            "3": {"name": "storage.modifier.extends.noon"},
                            "4": {"name": "entity.other.inherited-class.noon"},
                        },
                    },
                    {
                        # دالة مضروب(ع)
                        "match": r"%s(%s)\s+(%s)" % (BEFORE, variants("دالة"), IDENT),
                        "captures": {
                            "1": {"name": "storage.type.function.noon"},
                            "2": {"name": "entity.name.function.noon"},
                        },
                    },
                    {
                        # متغير س / ثابت ق
                        "match": r"%s(%s)\s+(%s)"
                                 % (BEFORE, alternation(["متغير", "ثابت"]), IDENT),
                        "captures": {
                            "1": {"name": "storage.type.variable.noon"},
                            "2": {"name": "variable.other.declaration.noon"},
                        },
                    },
                    {
                        # لكل عنصر في ...
                        "match": r"%s(%s)\s+(%s)\s+(%s)%s"
                                 % (BEFORE, variants("لكل"), IDENT,
                                    variants("في"), AFTER),
                        "captures": {
                            "1": {"name": "keyword.control.loop.noon"},
                            "2": {"name": "variable.other.loop.noon"},
                            "3": {"name": "keyword.control.loop.noon"},
                        },
                    },
                ],
            },

            "keywords": {
                "patterns": [
                    keyword_rule(GROUPS["conditional"], "keyword.control.conditional.noon"),
                    keyword_rule(GROUPS["loop"], "keyword.control.loop.noon"),
                    keyword_rule(GROUPS["flow"], "keyword.control.flow.noon"),
                    keyword_rule(GROUPS["storage"], "storage.type.noon"),
                    keyword_rule(GROUPS["modifier"], "storage.modifier.noon"),
                    keyword_rule(GROUPS["logical"], "keyword.operator.logical.noon"),
                ],
            },

            "constants": {
                "patterns": [
                    keyword_rule(GROUPS["constant"], "constant.language.noon"),
                    keyword_rule(GROUPS["language_variable"], "variable.language.noon"),
                    {"name": "constant.language.pi.noon",
                     "match": "%s%s%s" % (BEFORE, variants("باي"), AFTER)},
                ],
            },

            "methods": {
                "patterns": [{
                    # داخل الصنف كلمة «دالة» اختيارية: تهيئة(اسم) {  و  نص() {
                    # بعد الكلمات المفتاحية حتى تبقى «إذا (س) {» شرطًا لا تابعًا
                    "name": "entity.name.function.method.noon",
                    "match": r"%s%s(?=\s*\([^()]*\)\s*\{)" % (BEFORE, IDENT),
                }],
            },

            "members": {
                "patterns": [
                    {
                        # .أضف( — توابع الأنواع المدمجة
                        "match": r"(\.)\s*((?:%s))%s\s*(?=\()"
                                 % (alternation(method_names()), AFTER),
                        "captures": {
                            "1": {"name": "punctuation.accessor.noon"},
                            "2": {"name": "support.function.method.noon"},
                        },
                    },
                    {
                        "match": r"(\.)\s*(%s)\s*(?=\()" % IDENT,
                        "captures": {
                            "1": {"name": "punctuation.accessor.noon"},
                            "2": {"name": "entity.name.function.member.noon"},
                        },
                    },
                    {
                        "match": r"(\.)\s*(%s)" % IDENT,
                        "captures": {
                            "1": {"name": "punctuation.accessor.noon"},
                            "2": {"name": "variable.other.property.noon"},
                        },
                    },
                ],
            },

            "calls": {
                "patterns": [
                    {"name": "support.function.builtin.noon",
                     "match": "%s(?:%s)%s" % (BEFORE, alternation(builtin_names()), AFTER)},
                    {"name": "entity.name.function.call.noon",
                     "match": r"%s%s(?=\s*\()" % (BEFORE, IDENT)},
                ],
            },

            "operators": {
                "patterns": [
                    # المقارنة قبل الإسناد، وإلا صارت «==» علامتَي إسناد
                    {"name": "keyword.operator.comparison.noon",
                     "match": r"==|!=|<=|>=|<|>"},
                    {"name": "keyword.operator.assignment.noon",
                     "match": r"\+=|-=|\*=|/=|="},
                    {"name": "keyword.operator.logical.noon", "match": r"&&|\|\||!"},
                    {"name": "keyword.operator.arithmetic.noon",
                     "match": r"\*\*|//|[+\-*/%]"},
                ],
            },

            "punctuation": {
                "patterns": [
                    {"name": "punctuation.separator.noon", "match": "[,،:]"},
                    {"name": "punctuation.terminator.noon", "match": "[;؛]"},
                    {"name": "punctuation.section.braces.noon", "match": r"[{}]"},
                    {"name": "punctuation.section.brackets.noon", "match": r"[\[\]]"},
                    {"name": "punctuation.section.parens.noon", "match": r"[()]"},
                ],
            },
        },
    }


def dumps(grammar):
    return json.dumps(grammar, ensure_ascii=False, indent=2) + "\n"


def main(argv):
    grammar = dumps(build())
    if "--check" in argv:
        if not os.path.exists(TARGET):
            print("الملف غير موجود:", TARGET)
            return 1
        current = io.open(TARGET, encoding="utf-8").read()
        if current != grammar:
            print("قواعد التلوين ليست محدَّثة — شغّل: python tools/build_grammar.py")
            return 1
        print("قواعد التلوين محدَّثة")
        return 0

    os.makedirs(os.path.dirname(TARGET), exist_ok=True)
    io.open(TARGET, "w", encoding="utf-8", newline="\n").write(grammar)
    print("كُتب %s (%d بايت)" % (os.path.relpath(TARGET, ROOT), len(grammar.encode("utf-8"))))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
