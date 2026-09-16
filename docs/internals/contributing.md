# المساهمة

## التجهيز

```bash
git clone https://github.com/djouamaah/noon-lang.git
cd noon-lang
pip install -r docs/requirements.txt
```

الحزم في `docs/requirements.txt` للتوثيق واختبارات التلوين فقط؛ اللغة نفسها لا
تحتاج شيئًا.

## الاختبارات

```bash
python tests/test_noon.py
```

```bash
python tests/test_docs.py
```

الأولى تختبر اللغة والأمثلة وقواعد التلوين. والثانية تختبر **التوثيق**: كل كتلة
شيفرة فيه تُحلَّل، وكل كتلة ناتج تُقارَن بتشغيل الشيفرة التي فوقها، وكل دالة
مدمجة وكلمة مفتاحية وتابع موثَّق في المرجع. تعمل الاثنتان بـ`pytest` أيضًا.

## مثال: إضافة دالة مدمجة

لنُضف `مضروب(ن)`.

**١. الدالة** في `noon/builtins.py`، وتوقيع كل دالة مدمجة `(interp, args, line)`:

```python
def _factorial(interp, args, line):
    n = _need_int(args[0], line, "وسيط «مضروب»")
    if n < 0:
        raise NoonRuntimeError("لا مضروب لعدد سالب", line)
    return math.factorial(n)
```

**٢. تسجيلها** في جدول `GLOBALS` مع عدد وسائطها الأدنى والأقصى:

```python
"مضروب": BuiltinFunction("مضروب", _factorial, 1),
```

**٣. اختبار** في `tests/test_noon.py`:

```python
def test_factorial():
    assert val("مضروب(٥)") == 120
    fails("مضروب(-١)", NoonRuntimeError)
```

**٤. التلوين**: أعِد توليد قواعد VS Code لتُلوَّن الدالة الجديدة:

```bash
python tools/build_grammar.py
```

**٥. التوثيق**: أضِفها إلى [الدوال المدمجة](../reference/builtins.md). لو نسيت، سيفشل
`test_docs.py` ويسمّيها لك.

## التوثيق

الموقع مبنيّ بـ [MkDocs](https://www.mkdocs.org/) وسِمة
[Material](https://squidfunk.github.io/mkdocs-material/). صفحاته Markdown في
`docs/`، وقائمتها في `mkdocs.yml`.

```bash
mkdocs serve
```

ثم افتح `http://127.0.0.1:8000`؛ كل حفظ يُحدِّث الصفحة.

كتل الشيفرة بلغة `noon`، وكتلة `output` بعدها مباشرةً تعرض الناتج **وتُختبر**:

````markdown
```noon
اطبع(١ + ١)
```

```output
2
```
````

ولإدراج مثال من `examples/` مع ناتجه الفعلي وقت البناء:

```markdown
<!-- مثال: fib.noon -->
```

والتلوين في الموقع يأتي من قواعد إضافة VS Code عبر `hooks/noon_docs.py`، فلا
قواعد تلوين ثانية تُصان.

يُنشر الموقع تلقائيًّا على GitHub Pages مع كل دفعة إلى `main`، بعد أن تنجح
الاختبارات ويُبنى بلا تحذيرات.
