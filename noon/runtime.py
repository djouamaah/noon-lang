# -*- coding: utf-8 -*-
"""دلالات القيم المشتركة بين محرّكَي التنفيذ.

المُفسِّر (`interpreter.py`) والآلة الافتراضية (`vm.py`) يختلفان في *كيف*
يُنفِّذان البرنامج، ولكن معنى «الجمع» و«الفهرسة» و«المقارنة» وطريقة عرض القيم
واحدة في الاثنين. هي هنا مرّة واحدة حتى لا يفترق المحرّكان في السلوك.

كل دالة مدمجة في `builtins.py` تستقبل هذا الكائن باسم `interp`، فيكفي أن
يَرِث المحرّك `Runtime` وينفّذ `call` لتعمل الدوال المدمجة كلها معه.
"""

import os

from . import builtins as B
from .errors import NoonError, NoonRuntimeError
from .values import (BoundBuiltin, Module, NoonClass, NoonInstance, SuperProxy,
                     equals, is_number, stringify, type_name)

INIT_METHOD = "تهيئة"      # الباني
STR_METHOD = "نص"          # تمثيل الكائن نصًّا

# مكتبة «نون» القياسية: وحدات مكتوبة بـ«نون» تأتي مع اللغة
LIBRARY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib")
MODULE_EXTENSIONS = (".noon", ".نون")


class Runtime:
    """العمليات على القيم. المحرّك يُكمِلها بـ `call` و`write`."""

    out = None

    def write(self, text):
        self.out.write(text)

    def call(self, callee, args, line):
        raise NotImplementedError("على المحرّك أن يُنفّذ الاستدعاء")

    def load_module(self, program, module):
        """ينفّذ الشجرة النحوية لوحدة بعوامّ خاصّة بها، ويضعها في module.namespace
        ويسجّلها بـ register_module ليُعرف في أيّ وحدة يقع الخطأ."""
        raise NotImplementedError("على المحرّك أن يُنفّذ الوحدات")

    def register_module(self, key, module):
        """key: هويّة عوامّ الوحدة في المحرّك (قاموس الآلة أو بيئة المُفسِّر)."""
        self.__dict__.setdefault("_module_keys", {})[id(key)] = module

    def module_of(self, key):
        """الوحدة التي عوامّها key، أو None للبرنامج نفسه."""
        return self.__dict__.get("_module_keys", {}).get(id(key))

    # ——————————— الوحدات ———————————

    base_dir = None        # مجلّد البرنامج الرئيسي؛ يضبطه سطر الأوامر

    def import_module(self, name, line):
        """«استورد»: تُحمَّل الوحدة مرّة واحدة لكل محرّك، ثم تُعاد نفسها."""
        from .parser import parse       # parser ← … ← runtime: استيراد متأخّر

        if not isinstance(name, str) or not name.strip():
            raise NoonRuntimeError("اسم الوحدة يجب أن يكون نصًّا غير فارغ", line)
        modules = self.__dict__.setdefault("_modules", {})
        loading = self.__dict__.setdefault("_loading", [])
        path = self._find_module(name, loading, line)
        if path in modules:
            return modules[path]
        label = os.path.splitext(os.path.basename(path))[0]
        if path in loading:
            chain = [os.path.splitext(os.path.basename(p))[0]
                     for p in loading[loading.index(path):]]
            error = NoonRuntimeError(
                "استيراد دائري: %s" % " ← ".join(chain + [label]), line)
            error.circular = True
            raise error
        with open(path, encoding="utf-8-sig") as handle:
            source = handle.read()

        module = Module(label, path, None, B.GLOBALS)
        loading.append(path)
        try:
            self.load_module(parse(source), module)
        except NoonError as error:
            if getattr(error, "circular", False):   # السلسلة في الرسالة تكفي
                circular = NoonRuntimeError(error.message, line)
                circular.circular = True
                raise circular
            # سطر الخطأ في ملف الوحدة لا في البرنامج، فيُذكر في الرسالة
            where = " [سطر %d]" % error.line if error.line else ""
            raise NoonRuntimeError("%s في الوحدة «%s»%s: %s"
                                   % (error.kind, label, where, error.message), line)
        finally:
            loading.pop()
        modules[path] = module
        return module

    def _find_module(self, name, loading, line):
        """ملف في مجلّد المستورِد أوّلًا (أو مسار صريح)، ثم المكتبة القياسية."""
        here = (os.path.dirname(loading[-1]) if loading
                else self.base_dir or os.getcwd())
        if name.endswith(MODULE_EXTENSIONS):
            candidates = [name]
        else:
            candidates = [name + ext for ext in MODULE_EXTENSIONS]
        places = [here]
        explicit = (os.path.isabs(name) or "/" in name or "\\" in name
                    or name.endswith(MODULE_EXTENSIONS))
        if not explicit:
            places.append(LIBRARY_DIR)
        for place in places:
            for candidate in candidates:
                path = os.path.join(place, candidate)
                if os.path.isfile(path):
                    return os.path.normcase(os.path.realpath(path))
        raise NoonRuntimeError("لا توجد وحدة باسم «%s»" % name, line)

    def binary(self, op, left, right, line):
        if op == "==":
            return equals(left, right)
        if op == "!=":
            return not equals(left, right)
        if op == "في":
            return self.contains(right, left, line)

        if op in ("<", ">", "<=", ">="):
            order = self.compare(left, right, line)
            return {"<": order < 0, ">": order > 0,
                    "<=": order <= 0, ">=": order >= 0}[op]

        if op == "+":
            if is_number(left) and is_number(right):
                return left + right
            if isinstance(left, str) or isinstance(right, str):
                return self.stringify(left) + self.stringify(right)
            if isinstance(left, list) and isinstance(right, list):
                return left + right
            if isinstance(left, dict) and isinstance(right, dict):
                merged = dict(left)
                merged.update(right)
                return merged
            raise NoonRuntimeError(
                "لا يمكن جمع «%s» مع «%s»" % (type_name(left), type_name(right)),
                line)

        if op == "*":
            if is_number(left) and is_number(right):
                return left * right
            for a, b in ((left, right), (right, left)):
                if isinstance(a, (str, list)) and is_number(b) and not isinstance(b, bool):
                    if isinstance(b, float) and not b.is_integer():
                        raise NoonRuntimeError("عدد التكرار يجب أن يكون صحيحًا", line)
                    return a * int(b)
            raise NoonRuntimeError(
                "لا يمكن ضرب «%s» في «%s»" % (type_name(left), type_name(right)),
                line)

        if not (is_number(left) and is_number(right)):
            raise NoonRuntimeError(
                "العملية «%s» تحتاج عددين، لا «%s» و«%s»"
                % (op, type_name(left), type_name(right)), line)

        if op == "-":
            return left - right
        if op == "/":
            if right == 0:
                raise NoonRuntimeError("القسمة على صفر", line)
            result = left / right
            if isinstance(left, int) and isinstance(right, int) and result.is_integer():
                return int(result)
            return result
        if op == "//":
            if right == 0:
                raise NoonRuntimeError("القسمة على صفر", line)
            return left // right
        if op == "%":
            if right == 0:
                raise NoonRuntimeError("باقي القسمة على صفر", line)
            return left % right
        if op == "**":
            try:
                result = left ** right
            except (OverflowError, ZeroDivisionError):
                raise NoonRuntimeError("نتيجة الأُسّ خارج النطاق", line)
            if isinstance(result, complex):
                raise NoonRuntimeError("نتيجة الأُسّ ليست عددًا حقيقيًّا", line)
            return result

        raise NoonRuntimeError("عملية غير معروفة: «%s»" % op, line)

    def compare(self, left, right, line):
        """يُرجع سالبًا أو صفرًا أو موجبًا، ويرفض مقارنة الأنواع المختلطة."""
        if is_number(left) and is_number(right):
            return (left > right) - (left < right)
        if isinstance(left, str) and isinstance(right, str):
            return (left > right) - (left < right)
        raise NoonRuntimeError(
            "لا يمكن المقارنة بين «%s» و«%s»" % (type_name(left), type_name(right)),
            line)

    def contains(self, container, item, line):
        if isinstance(container, str):
            if not isinstance(item, str):
                raise NoonRuntimeError("البحث داخل نصّ يحتاج نصًّا", line)
            return item in container
        if isinstance(container, list):
            return any(equals(x, item) for x in container)
        if isinstance(container, dict):
            return item in container
        raise NoonRuntimeError(
            "لا يمكن البحث داخل قيمة من نوع «%s»" % type_name(container), line)

    def get_index(self, obj, key, line):
        if isinstance(obj, (str, list)):
            if not is_number(key) or (isinstance(key, float) and not key.is_integer()):
                raise NoonRuntimeError(
                    "فهرس %s يجب أن يكون عددًا صحيحًا" % type_name(obj), line)
            index = int(key)
            if not -len(obj) <= index < len(obj):
                raise NoonRuntimeError(
                    "الفهرس %d خارج الحدود (الطول %d)" % (index, len(obj)), line)
            return obj[index]
        if isinstance(obj, dict):
            if key not in obj:
                raise NoonRuntimeError(
                    "المفتاح «%s» غير موجود في القاموس" % stringify(key), line)
            return obj[key]
        if isinstance(obj, NoonInstance):
            return obj.get(self.stringify(key), line)
        raise NoonRuntimeError(
            "لا يمكن فهرسة قيمة من نوع «%s»" % type_name(obj), line)

    def set_index(self, obj, key, value, line):
        if isinstance(obj, list):
            if not is_number(key) or (isinstance(key, float) and not key.is_integer()):
                raise NoonRuntimeError("فهرس القائمة يجب أن يكون عددًا صحيحًا", line)
            index = int(key)
            if not -len(obj) <= index < len(obj):
                raise NoonRuntimeError(
                    "الفهرس %d خارج الحدود (الطول %d)" % (index, len(obj)), line)
            obj[index] = value
            return
        if isinstance(obj, dict):
            if not isinstance(key, (str, int, float)) or isinstance(key, bool):
                raise NoonRuntimeError("مفتاح القاموس يجب أن يكون نصًّا أو عددًا", line)
            obj[key] = value
            return
        if isinstance(obj, NoonInstance):
            obj.set(self.stringify(key), value)
            return
        raise NoonRuntimeError(
            "لا يمكن الإسناد داخل قيمة من نوع «%s»" % type_name(obj), line)

    def get_member(self, obj, name, line):
        if isinstance(obj, NoonInstance):
            return obj.get(name, line)
        if isinstance(obj, Module):
            return obj.get(name, line)
        if isinstance(obj, SuperProxy):
            return obj.get(name, line)
        if isinstance(obj, NoonClass):
            owner, method = obj.find_method(name)
            if method is None:
                raise NoonRuntimeError(
                    "الصنف «%s» لا يملك «%s»" % (obj.name, name), line)
            return method
        table = B.methods_for(obj)
        if table is not None:
            if name in table:
                return BoundBuiltin(obj, table[name])
            if isinstance(obj, dict) and name in obj:
                return obj[name]
            raise NoonRuntimeError(
                "لا يوجد تابع «%s» للنوع «%s»" % (name, type_name(obj)), line)
        raise NoonRuntimeError(
            "لا يمكن قراءة «%s» من قيمة من نوع «%s»" % (name, type_name(obj)), line)

    def iterate(self, value, line=None):
        """يحوّل القيمة إلى قائمة عناصر للتكرار عليها."""
        if isinstance(value, list):
            return list(value)
        if isinstance(value, str):
            return list(value)
        if isinstance(value, dict):
            return list(value.keys())
        raise NoonRuntimeError(
            "لا يمكن التكرار على قيمة من نوع «%s»" % type_name(value), line)

    # ——————————— الاستدعاء ———————————

    def stringify(self, value):
        """مثل values.stringify لكنه يحترم تابع «نص» المُعرَّف في الأصناف."""
        if isinstance(value, NoonInstance):
            owner, method = value.klass.find_method(STR_METHOD)
            if method is not None:
                return stringify(self.call(method.bind(value, owner), [], None))
        if isinstance(value, list):
            return "[" + "، ".join(self._quoted(v) for v in value) + "]"
        if isinstance(value, dict):
            return "{" + "، ".join("%s: %s" % (self._quoted(k), self._quoted(v))
                                   for k, v in value.items()) + "}"
        return stringify(value)

    def _quoted(self, value):
        if isinstance(value, str):
            return '"%s"' % value
        return self.stringify(value)

