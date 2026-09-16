# -*- coding: utf-8 -*-
"""اختبارات لغة «نون».

تعمل مع pytest، وتعمل وحدها أيضًا:  python tests/test_noon.py
"""

import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from noon.errors import NoonError, NoonRuntimeError, NoonSyntaxError  # noqa: E402
from noon.interpreter import Interpreter  # noqa: E402
from noon import values  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def out(source):
    """ينفّذ الشيفرة ويُرجع ما طُبع."""
    buffer = io.StringIO()
    Interpreter(out=buffer).run(source)
    return buffer.getvalue()


def val(expression):
    """يُرجع قيمة تعبير واحد."""
    buffer = io.StringIO()
    return Interpreter(out=buffer).run(expression, repl=True)


def fails(source, kind=NoonError):
    try:
        out(source)
    except kind as error:
        return error
    raise AssertionError("كان يُفترض أن تفشل هذه الشيفرة: %r" % source)


# ——————————————— التحليل اللفظي ———————————————

def test_arabic_and_latin_digits_are_the_same():
    assert val("١٢٣") == 123
    assert val("١٢٣ == 123") is True
    assert val("٣٫٥ + ٠٫٥") == 4
    assert val("١٬٠٠٠ + ١") == 1001


def test_keyword_spelling_variants():
    assert out("اذا (صحيح) { اطبع(١) }") == "1\n"
    assert out("إذا (صحيح) { اطبع(١) }") == "1\n"
    assert out("دالة ض(س) { ارجع س * ٢ }\nاطبع(ض(٤))") == "8\n"


def test_comments_and_separators():
    assert out("# تعليق\nاطبع(١)؛ اطبع(٢)") == "1\n2\n"
    assert val('"نصّ # ليس تعليقًا"') == "نصّ # ليس تعليقًا"


def test_string_escapes():
    assert val(r'"سطر\nثانٍ"') == "سطر\nثانٍ"
    assert val(r'"\u0646\u0648\u0646"') == "نون"
    assert val('"اقتباس \\"داخلي\\""') == 'اقتباس "داخلي"'
    # التهريب المجهول يبقى حرفيًّا حتى لا يضيع مسار مثل "C:\\Users"
    assert val(r'"C:\Users\GEEK"') == r"C:\Users\GEEK"


def test_unterminated_string_is_a_syntax_error():
    fails('اطبع("بلا إغلاق)', NoonSyntaxError)


# ——————————————— التعابير ———————————————

def test_arithmetic_precedence():
    assert val("٢ + ٣ * ٤") == 14
    assert val("(٢ + ٣) * ٤") == 20
    assert val("٢ ** ٣ ** ٢") == 512          # يمين-تجميعي
    assert val("-٢ ** ٢") == -4
    assert val("٧ // ٢") == 3
    assert val("٧ % ٢") == 1
    assert val("٦ / ٣") == 2                  # قسمة صحيحة تبقى صحيحة
    assert val("٧ / ٢") == 3.5


def test_string_and_list_operations():
    assert val('"أ" + "ب"') == "أب"
    assert val('"ـ" * ٣') == "ـــ"
    assert val('"عدد: " + ٥') == "عدد: 5"
    assert val("[١، ٢] + [٣]") == [1, 2, 3]
    assert val('"مرحبا"[٠]') == "م"
    assert val('"مرحبا"[-١]') == "ا"
    assert val("[١، ٢، ٣، ٤][١:٣]") == [2, 3]
    assert val('"البخاري"[:٢]') == "ال"


def test_comparison_and_equality_are_strict():
    assert val("١ == صحيح") is False
    assert val("٠ == خطأ") is False
    assert val("عدم == عدم") is True
    assert val('"ا" < "ب"') is True
    assert val("[١، ٢] == [١، ٢]") is True
    fails("١ < \"ا\"", NoonRuntimeError)


def test_logical_operators_short_circuit():
    assert out("خطأ و اطبع(١)\nاطبع(٢)") == "2\n"
    assert val("عدم أو ٥") == 5
    assert val("ليس ٠") is True
    assert val("صحيح && خطأ") is False
    assert val("خطأ || ٣") == 3


def test_membership():
    assert val("٢ في [١، ٢]") is True
    assert val('"خ" في "بخاري"') is True
    assert val('"أ" في {"أ": ١}') is True


# ——————————————— المتغيّرات والنطاقات ———————————————

def test_undefined_variable():
    error = fails("اطبع(س)", NoonRuntimeError)
    assert "غير مُعرَّف" in error.message


def test_assignment_requires_declaration():
    fails("س = ١", NoonRuntimeError)
    assert out("متغير س = ١\nس = ٢\nاطبع(س)") == "2\n"


def test_constants_cannot_change():
    error = fails('ثابت ق = ١\nق = ٢', NoonRuntimeError)
    assert "ثابت" in error.message


def test_block_scope():
    assert out("متغير س = ١\n{ متغير س = ٢\nاطبع(س) }\nاطبع(س)") == "2\n1\n"


def test_compound_assignment():
    assert out("متغير س = ١٠\nس += ٥\nس -= ٣\nس *= ٢\nس /= ٤\nاطبع(س)") == "6\n"


# ——————————————— التحكّم في التدفّق ———————————————

def test_if_else_chain():
    source = """
    دالة صنّف(ع) {
        إذا (ع < ٠) { أرجع "سالب" }
        وإلا إذا (ع == ٠) { أرجع "صفر" }
        وإلا { أرجع "موجب" }
    }
    اطبع(صنّف(-١)، صنّف(٠)، صنّف(١))
    """
    assert out(source) == "سالب صفر موجب\n"


def test_while_break_continue():
    source = """
    متغير ع = ٠
    متغير مجموع_ = ٠
    طالما (صحيح) {
        ع += ١
        إذا (ع > ١٠) { توقف }
        إذا (ع % ٢ == ١) { استمر }
        مجموع_ += ع
    }
    اطبع(مجموع_)
    """
    assert out(source) == "30\n"


def test_for_in_over_every_type():
    assert out("لكل ع في [١، ٢] { اطبع(ع) }") == "1\n2\n"
    assert out('لكل ح في "ابج" { اطبع(ح) }') == "ا\nب\nج\n"
    assert out('لكل م في {"أ": ١، "ب": ٢} { اطبع(م) }') == "أ\nب\n"
    assert out("لكل ع في مدى(٢، ٨، ٣) { اطبع(ع) }") == "2\n5\n"


# ——————————————— الدوال ———————————————

def test_functions_defaults_and_recursion():
    assert out("دالة ت(اسم، لقب = \"—\") { أرجع اسم + \" \" + لقب }\n"
               "اطبع(ت(\"زيد\"))\nاطبع(ت(\"زيد\"، \"العابد\"))") == "زيد —\nزيد العابد\n"
    assert val("""(دالة ف(ن) { إذا (ن <= ١) { أرجع ١ } أرجع ن * ف(ن - ١) })""") is not None


def test_closures_keep_state():
    source = """
    دالة عدّاد(بداية) {
        متغير ع = بداية
        أرجع دالة() {
            ع += ١
            أرجع ع
        }
    }
    متغير أ = عدّاد(١٠)
    متغير ب = عدّاد(٠)
    اطبع(أ()، أ()، ب())
    """
    assert out(source) == "11 12 1\n"


def test_arity_errors():
    error = fails("دالة د(أ، ب) { أرجع أ }\nد(١)", NoonRuntimeError)
    assert "تتوقّع" in error.message
    fails("طول()", NoonRuntimeError)


def test_higher_order_builtins():
    assert val("طبّق(دالة(س) { أرجع س * س }، [١، ٢، ٣])") == [1, 4, 9]
    assert val("رشّح(دالة(س) { أرجع س % ٢ == ٠ }، مدى(٧))") == [0, 2, 4, 6]
    assert val("اختزل(دالة(أ، ب) { أرجع أ + ب }، [١، ٢، ٣]، ١٠)") == 16
    assert val("فرز([٣، ١، ٢])") == [1, 2, 3]
    assert val("فرز([\"بب\"، \"أ\"]، دالة(س) { أرجع طول(س) })") == ["أ", "بب"]


def test_recursion_depth_is_reported():
    error = fails("دالة لانهاية(ن) { أرجع لانهاية(ن + ١) }\nلانهاية(٠)",
                  NoonRuntimeError)
    assert "عمق الاستدعاء" in error.message


# ——————————————— الأصناف ———————————————

def test_class_inheritance_and_super():
    source = """
    صنف أب {
        تهيئة(اسم) { هذا.اسم = اسم }
        تحية() { أرجع "أنا " + هذا.اسم }
    }
    صنف ابن يرث أب {
        تهيئة(اسم) { الأصل.تهيئة(اسم + " الصغير") }
        تحية() { أرجع الأصل.تحية() + "!" }
    }
    اطبع(ابن("زيد").تحية())
    """
    assert out(source) == "أنا زيد الصغير!\n"


def test_to_string_method_is_used_by_print():
    source = """
    صنف نقطة {
        تهيئة(س، ص) { هذا.س = س
                      هذا.ص = ص }
        نص() { أرجع "(" + نص(هذا.س) + "، " + نص(هذا.ص) + ")" }
    }
    اطبع(نقطة(١، ٢))
    """
    assert out(source) == "(1، 2)\n"


def test_instance_of_and_missing_member():
    source = """
    صنف أ {}
    صنف ب يرث أ {}
    اطبع(من_صنف(ب()، أ)، من_صنف(أ()، ب))
    """
    assert out(source) == "صحيح خطأ\n"
    fails("صنف ج {}\nاطبع(ج().لا_يوجد)", NoonRuntimeError)


# ——————————————— القوائم والقواميس ———————————————

def test_list_methods():
    assert val("متغير ق = [١]؛ ق.أضف(٢، ٣)؛ ق") == [1, 2, 3]
    assert val("متغير ق = [١، ٢، ٣]؛ ق.احذف(٠)؛ ق") == [2, 3]
    assert val("[١، ٢، ٣].يحتوي(٢)") is True
    assert val("[١، ٢].موضع(٢)") == 1
    assert val('["أ"، "ب"].وصل("-")') == "أ-ب"
    assert val("[٣، ١].فرز()") == [1, 3]
    assert val("[١، ٢].عكس()") == [2, 1]


def test_dict_methods_and_indexing():
    assert val('{"أ": ١}.مفاتيح()') == ["أ"]
    assert val('{"أ": ١}.قيم()') == [1]
    assert val('{"أ": ١}.اجلب("ب"، ٩)') == 9
    assert val('متغير م = {}؛ م["س"] = ١؛ م') == {"س": 1}
    assert val('متغير م = {}؛ م.ص = ٢؛ م["ص"]') == 2
    fails('{"أ": ١}["ب"]', NoonRuntimeError)


def test_index_errors():
    error = fails("[١، ٢][٩]", NoonRuntimeError)
    assert "خارج الحدود" in error.message
    fails('[١][""]', NoonRuntimeError)


# ——————————————— الأخطاء ———————————————

def test_throw_and_catch():
    source = """
    دالة اقسم(أ، ب) {
        إذا (ب == ٠) { ارمِ "لا قسمة على صفر" }
        أرجع أ / ب
    }
    حاول {
        اطبع(اقسم(١، ٠))
    } امسك (خ) {
        اطبع("مسكت:", خ)
    } أخيرًا {
        اطبع("انتهى")
    }
    """
    assert out(source) == "مسكت: لا قسمة على صفر\nانتهى\n"


def test_runtime_errors_are_catchable():
    source = """
    حاول {
        اطبع(١ / ٠)
    } امسك (خ) {
        اطبع(خ["نوع"]، خ["رسالة"])
    }
    """
    assert out(source) == "خطأ تشغيل القسمة على صفر\n"


def test_division_by_zero_and_type_errors():
    assert "القسمة على صفر" in fails("١ / ٠", NoonRuntimeError).message
    assert "لا يمكن جمع" in fails("[١] + ١", NoonRuntimeError).message
    assert "لا يمكن استدعاء" in fails("متغير س = ١\nس()", NoonRuntimeError).message


def test_syntax_errors_carry_line_numbers():
    error = fails("اطبع(١)\nاطبع(٢\n", NoonSyntaxError)
    assert error.line >= 2


# ——————————————— الدوال المدمجة والعرض ———————————————

def test_type_and_conversions():
    assert val("نوع(١)") == "عدد"
    assert val('نوع("ا")') == "نص"
    assert val("نوع([])") == "قائمة"
    assert val("نوع({})") == "قاموس"
    assert val("نوع(عدم)") == "عدم"
    assert val("نوع(صحيح)") == "منطقي"
    assert val("نوع(اطبع)") == "دالة"
    assert val('عدد("١٢٣")') == 123
    assert val('عدد("٣٫٥")') == 3.5
    assert val("نص(١٢)") == "12"
    fails('عدد("ليس عددًا")', NoonRuntimeError)


def test_printing_format():
    assert out("اطبع([١، \"ا\"، عدم، صحيح])") == '[1، "ا"، عدم، صحيح]\n'
    assert out('اطبع({"أ": [١]})') == '{"أ": [1]}\n'
    assert out("اطبع(١٫٠، ٢٫٥)") == "1 2.5\n"
    assert out("اطبع()") == "\n"


def test_arabic_digit_output_mode():
    try:
        values.set_arabic_digits(True)
        assert out("اطبع(١٢٣٤، ٢٫٥)") == "١٢٣٤ ٢٫٥\n"
    finally:
        values.set_arabic_digits(False)
    assert out("اطبع(١٢٣٤)") == "1234\n"


def test_math_builtins():
    assert val("مجموع([١، ٢، ٣])") == 6
    assert val("أقصى([١، ٩، ٣])") == 9
    assert val("أدنى(٤، ٢)") == 2
    assert val("مطلق(-٣)") == 3
    assert val("جذر(٩)") == 3
    assert val("تقريب(٣٫١٤١٥٩، ٢)") == 3.14
    assert val("أرضية(٢٫٩)") == 2
    assert val("سقف(٢٫١)") == 3
    assert val("طول(مدى(٥))") == 5


# ——————————————— الأمثلة ———————————————

def test_all_examples_run():
    folder = os.path.join(ROOT, "examples")
    names = sorted(name for name in os.listdir(folder) if name.endswith(".noon"))
    assert names, "لا توجد أمثلة"
    for name in names:
        with io.open(os.path.join(folder, name), encoding="utf-8") as handle:
            source = handle.read()
        buffer = io.StringIO()
        Interpreter(out=buffer).run(source)
        assert buffer.getvalue().strip(), "المثال %s لم يطبع شيئًا" % name


# ——————————————— إضافة VS Code ———————————————

VSCODE = os.path.join(ROOT, "editors", "vscode")
GRAMMAR = os.path.join(VSCODE, "syntaxes", "noon.tmLanguage.json")


def _json(path):
    import json
    with io.open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _patterns(node, found=None):
    """يجمع كل تعابير المطابقة في ملف القواعد."""
    found = [] if found is None else found
    if isinstance(node, dict):
        for key, value in node.items():
            if key in ("match", "begin", "end") and isinstance(value, str):
                found.append(value)
            else:
                _patterns(value, found)
    elif isinstance(node, list):
        for item in node:
            _patterns(item, found)
    return found


def _oniguruma_to_python(pattern):
    r"""\x{0640} في Oniguruma تُكتب \u0640 في بايثون."""
    import re as _re
    return _re.sub(r"\\x\{([0-9A-Fa-f]+)\}",
                   lambda m: "\\u%04x" % int(m.group(1), 16), pattern)


def _rule(name, index=0):
    """تعبير قاعدة من مستودع القواعد، مترجَمًا وجاهزًا للتجربة."""
    import regex
    grammar = _json(GRAMMAR)
    rule = grammar["repository"][name]["patterns"][index]
    return regex.compile(_oniguruma_to_python(rule["match"]))


def _has_regex_engine():
    """المحرّك `regex` اختياري: يفهم \\p{L} والنظر الخلفي مثل Oniguruma."""
    try:
        import regex  # noqa: F401
        return True
    except ImportError:
        return False


def test_vscode_grammar_is_in_sync_with_the_language():
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import build_grammar
    current = io.open(GRAMMAR, encoding="utf-8").read()
    assert current == build_grammar.dumps(build_grammar.build()), (
        "قواعد التلوين ليست محدَّثة — شغّل python tools/build_grammar.py")


def test_vscode_grammar_patterns_compile():
    if not _has_regex_engine():
        return
    import regex
    patterns = _patterns(_json(GRAMMAR))
    assert len(patterns) > 20
    for pattern in patterns:
        regex.compile(_oniguruma_to_python(pattern))


def test_vscode_grammar_agrees_with_the_lexer_on_keywords():
    if not _has_regex_engine():
        return
    from noon.lexer import _RAW_KEYWORDS, tokenize

    rules = [_rule("keywords", i) for i in range(6)]
    rules += [_rule("constants", i) for i in range(2)]

    def coloured(word):
        return any(rule.fullmatch(word) for rule in rules)

    for keyword in _RAW_KEYWORDS:
        assert coloured(keyword), "الكلمة المفتاحية «%s» بلا تلوين" % keyword

    # أسماء تشبه الكلمات المفتاحية ولكنها أسماء عادية عند المُفسِّر
    for name in ("صنّف", "أرجعه", "احمد", "فيصل", "وقت", "هذان", "خطأي"):
        assert tokenize(name)[0].type == "IDENT", "«%s» ليست اسمًا؟" % name
        assert not coloured(name), "«%s» لُوِّنت كأنها كلمة مفتاحية" % name


def test_vscode_grammar_numbers_and_builtins():
    if not _has_regex_engine():
        return
    numbers = _rule("numbers")
    for text in ("١٢٣", "3.5", "٣٫٥", "١٬٠٠٠", "٠"):
        assert numbers.fullmatch(text), "لم يُلوَّن العدد %s" % text
    assert not numbers.search("س١")            # رقم داخل اسم ليس عددًا

    builtins_rule = _rule("calls")
    for name in ("اطبع", "مدى", "فرز", "طبّق"):
        assert builtins_rule.fullmatch(name), "الدالة المدمجة «%s» بلا تلوين" % name
    assert not builtins_rule.fullmatch("اطبعوا")


def test_vscode_grammar_colours_whole_tokens():
    if not _has_regex_engine():
        return
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    from preview_highlight import load_rules, tokenize_line

    rules = load_rules()

    def scopes(line):
        return [(text, scope) for text, scope in tokenize_line(line, rules) if text.strip()]

    # «==» مقارنة واحدة، لا علامتا إسناد
    assert ("==", "keyword.operator.comparison.noon") in scopes("إذا (س == ٠) {")

    # تابع داخل صنف بلا «دالة» تعريفٌ لا نداء، حتى لو حمل اسم دالة مدمجة
    for line, name in (("تهيئة(اسم) {", "تهيئة"), ("نص() {", "نص")):
        assert scopes(line)[0] == (name, "entity.name.function.method.noon"), line
    assert scopes("إذا (س) {")[0][1] == "keyword.control.conditional.noon"
    assert scopes("اطبع(س)")[0][1] == "support.function.builtin.noon"


def test_vscode_manifest_points_at_real_files():
    manifest = _json(os.path.join(VSCODE, "package.json"))
    contributes = manifest["contributes"]
    language = contributes["languages"][0]
    assert language["id"] == "noon"
    assert ".noon" in language["extensions"]
    paths = [language["configuration"],
             contributes["grammars"][0]["path"],
             contributes["snippets"][0]["path"]]
    for path in paths:
        full = os.path.join(VSCODE, path.lstrip("./"))
        assert os.path.exists(full), "مسار مفقود في package.json: %s" % path
        _json(full)                            # لا بدّ أن يكون JSON سليمًا
    assert contributes["grammars"][0]["scopeName"] == _json(GRAMMAR)["scopeName"]


def test_vscode_snippets_parse_as_noon():
    """كل مقطع جاهز لا بدّ أن يكون شيفرة «نون» صحيحة بعد إزالة علاماته."""
    import re as _re
    from noon.parser import parse

    snippets = _json(os.path.join(VSCODE, "snippets", "noon.code-snippets"))
    assert snippets
    for name, snippet in snippets.items():
        body = "\n".join(snippet["body"])
        body = _re.sub(r"\$\{\d+:([^}]*)\}", r"\1", body)     # ${1:اسم} ← اسم
        body = _re.sub(r"\$\{\d+\}", "س", body)               # ${2}    ← س
        body = _re.sub(r"\$\d+", "", body)                    # $0      ← فراغ
        try:
            parse(body)
        except NoonError as error:
            raise AssertionError("المقطع «%s» لا يُحلَّل: %s" % (name, error))


# ——————————————— مُشغِّل مستقلّ ———————————————

def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    tests = [(name, fn) for name, fn in sorted(globals().items())
             if name.startswith("test_") and callable(fn)]
    failed = []
    for name, fn in tests:
        try:
            fn()
            print("✓ %s" % name)
        except Exception as error:                   # noqa: BLE001
            failed.append((name, error))
            print("✗ %s\n    %s: %s" % (name, type(error).__name__, error))
    print("\n%d/%d اختبارًا ناجحًا" % (len(tests) - len(failed), len(tests)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
