# التثبيت والتشغيل

«نون» لا تحتاج إلا إلى **Python 3.8** أو أحدث، ولا تعتمد على أي حزمة خارجية.

!!! tip "أو جرّبها دون تثبيت شيء"
    [ساحة التجربة](../playground/index.html) محرّر في المتصفّح يشغّل «نون» نفسها
    عبر Python المُترجَم إلى WebAssembly: اكتب، وشغّل بـ ++ctrl+enter++، وشارك
    شيفرتك برابط. وتحت كل مثال في هذا التوثيق رابط «جرّبها» يفتحه فيها.

## الحصول على اللغة

```bash
git clone https://github.com/djouamaah/noon-lang.git
cd noon-lang
```

تحقّق أن كل شيء يعمل:

```bash
python noon.py --version
```

## تشغيل ملف

ملفات «نون» امتدادها `.noon` (أو `.نون`). أنشئ ملفًا اسمه `مرحبا.noon`:

```noon
اطبع("مرحبًا يا عالم")
```

ثم شغّله:

```bash
python noon.py مرحبا.noon
```

```output
مرحبًا يا عالم
```

!!! tip "الترميز"
    احفظ ملفاتك بترميز **UTF-8**. المُفسِّر يقرأ UTF-8 ويتجاهل علامة BOM إن وُجدت،
    ويضبط الإخراج على UTF-8 حتى في طرفية ويندوز.

## طرق أخرى للتشغيل

=== "شيفرة مباشرة"

    ```bash
    python noon.py -c 'اطبع(٢ ** ١٠)'
    ```

    في **Windows PowerShell 5.1** تُحذف علامات الاقتباس المزدوجة من داخل الوسيط
    قبل أن تصل إلى البرنامج، فاستعمل المفردة داخل الشيفرة:

    ```powershell
    python noon.py -c "اطبع('مرحبًا')"
    ```

=== "من الدخل القياسي"

    ```bash
    echo 'اطبع("من الأنبوب")' | python noon.py
    ```

=== "صدفة تفاعلية"

    ```bash
    python noon.py
    ```

    انظر [الصدفة التفاعلية](repl.md).

## التثبيت أمرًا في النظام

إن أردت كتابة `noon` بدل `python noon.py`، ثبّت الحزمة من
[آخر إصدار](https://github.com/djouamaah/noon-lang/releases/latest):

```bash
pip install https://github.com/djouamaah/noon-lang/releases/download/v1.2.0/noon_lang-1.2.0-py3-none-any.whl
```

أو من نسختك من المستودع، فتظهر تعديلاتك فورًا:

```bash
pip install -e .
```

```bash
noon مرحبا.noon
```

!!! warning "ويندوز: «noon is not recognized»"
    إن لم يكن لديك صلاحية المدير، يثبّت pip الأمر في مجلّد مستخدمك
    (`%APPDATA%\Python\Python3XX\Scripts`) لا في مجلّد Python العام، وهذا المجلّد
    ليس في `PATH` غالبًا، فيقول PowerShell:

    ```text
    noon : The term 'noon' is not recognized as the name of a cmdlet...
    ```

    **حلّ فوري** بلا تغيير شيء:

    ```powershell
    python -m noon .\مرحبا.noon
    ```

    **حلّ دائم**: أضِف مجلّد الأوامر إلى `PATH` مستخدمك (لا يحتاج صلاحية المدير):

    ```powershell
    $scripts = python -c "import sysconfig; print(sysconfig.get_path('scripts', 'nt_user'))"
    [Environment]::SetEnvironmentVariable("Path", [Environment]::GetEnvironmentVariable("Path", "User") + ";$scripts", "User")
    ```

    ثم **أغلق الطرفية وافتح غيرها**: الطرفية المفتوحة لا تقرأ `PATH` الجديد.

## الخطوة التالية

- [أوّل برنامج](first-program.md): جولة قصيرة في برنامج كامل.
- [إضافة VS Code](../tools/vscode.md): تلوين الصيغة والمقاطع الجاهزة.
- [سطر الأوامر](../reference/cli.md): كل الخيارات.
