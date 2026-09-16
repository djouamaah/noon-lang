# -*- coding: utf-8 -*-
"""المُفسِّر: يمشي على الشجرة النحوية وينفّذها."""

import sys

from . import ast_nodes as A
from . import builtins as B
from .errors import (BreakSignal, ContinueSignal, NoonRuntimeError, NoonThrow,
                     ReturnSignal)
from .parser import parse
from .values import (BoundBuiltin, BuiltinFunction, NoonClass, NoonFunction,
                     NoonInstance, SuperProxy, equals, is_number, stringify,
                     truthy, type_name)

INIT_METHOD = "تهيئة"      # الباني
STR_METHOD = "نص"          # تمثيل الكائن نصًّا


class Environment:
    """نطاق متغيّرات مرتبط بنطاق أب."""

    __slots__ = ("values", "constants", "parent")

    def __init__(self, parent=None):
        self.values = {}
        self.constants = set()
        self.parent = parent

    def declare(self, name, value, constant=False):
        self.values[name] = value
        if constant:
            self.constants.add(name)
        elif name in self.constants:
            self.constants.discard(name)

    def get(self, name, line=None):
        env = self
        while env is not None:
            if name in env.values:
                return env.values[name]
            env = env.parent
        raise NoonRuntimeError("المتغيّر «%s» غير مُعرَّف" % name, line)

    def assign(self, name, value, line=None):
        env = self
        while env is not None:
            if name in env.values:
                if name in env.constants:
                    raise NoonRuntimeError(
                        "«%s» ثابت، لا يمكن تغيير قيمته" % name, line)
                env.values[name] = value
                return
            env = env.parent
        raise NoonRuntimeError(
            "المتغيّر «%s» غير مُعرَّف؛ استعمل «متغير %s = ...» أوّلًا" % (name, name),
            line)

    def has(self, name):
        env = self
        while env is not None:
            if name in env.values:
                return True
            env = env.parent
        return False


class Interpreter:
    def __init__(self, out=None):
        self.globals = Environment()
        self.env = self.globals
        self.out = out if out is not None else sys.stdout
        for name, value in B.GLOBALS.items():
            self.globals.declare(name, value, constant=True)

    # ——————————— واجهة عامة ———————————
    def write(self, text):
        self.out.write(text)

    def run(self, source, repl=False):
        """ينفّذ شيفرة نصّية ويُرجع قيمة آخر تعبير (مفيدة في REPL)."""
        program = parse(source)
        return self.execute_program(program, repl=repl)

    def execute_program(self, program, repl=False):
        last = None
        for statement in program.body:
            if repl and isinstance(statement, A.ExprStmt):
                last = self.evaluate(statement.expr)
            else:
                self.execute(statement)
                last = None
        return last

    # ——————————— الإرسال ———————————
    def execute(self, node):
        method = getattr(self, "exec_" + type(node).__name__, None)
        if method is None:
            raise NoonRuntimeError("جملة غير مدعومة: %s" % type(node).__name__,
                                   node.line)
        return method(node)

    def evaluate(self, node):
        method = getattr(self, "eval_" + type(node).__name__, None)
        if method is None:
            raise NoonRuntimeError("تعبير غير مدعوم: %s" % type(node).__name__,
                                   node.line)
        return method(node)

    # ——————————— الجُمل ———————————
    def exec_Program(self, node):
        self.execute_program(node)

    def exec_Block(self, node):
        self.execute_block(node.body, Environment(self.env))

    def execute_block(self, statements, env):
        previous = self.env
        self.env = env
        try:
            for statement in statements:
                self.execute(statement)
        finally:
            self.env = previous

    def exec_ExprStmt(self, node):
        self.evaluate(node.expr)

    def exec_VarDecl(self, node):
        value = self.evaluate(node.value) if node.value is not None else None
        if node.name in self.env.values:
            raise NoonRuntimeError(
                "«%s» مُعرَّف مسبقًا في هذا النطاق" % node.name, node.line)
        self.env.declare(node.name, value, node.constant)

    def exec_Assign(self, node):
        target = node.target
        value = self.evaluate(node.value)
        if node.op is not None:
            current = self.evaluate(target)
            value = self.binary(node.op, current, value, node.line)

        if isinstance(target, A.Identifier):
            self.env.assign(target.name, value, node.line)
        elif isinstance(target, A.Index):
            obj = self.evaluate(target.obj)
            key = self.evaluate(target.key)
            self.set_index(obj, key, value, node.line)
        elif isinstance(target, A.Member):
            obj = self.evaluate(target.obj)
            if isinstance(obj, NoonInstance):
                obj.set(target.name, value)
            elif isinstance(obj, dict):
                obj[target.name] = value
            else:
                raise NoonRuntimeError(
                    "لا يمكن إسناد عضو إلى قيمة من نوع «%s»" % type_name(obj),
                    node.line)
        return value

    def exec_If(self, node):
        if truthy(self.evaluate(node.cond)):
            self.execute(node.then_branch)
        elif node.else_branch is not None:
            self.execute(node.else_branch)

    def exec_While(self, node):
        while truthy(self.evaluate(node.cond)):
            try:
                self.execute(node.body)
            except BreakSignal:
                break
            except ContinueSignal:
                continue

    def exec_ForIn(self, node):
        items = self.iterate(self.evaluate(node.iterable), node.line)
        for item in items:
            env = Environment(self.env)
            env.declare(node.name, item)
            try:
                self.execute_block(node.body.body, env)
            except BreakSignal:
                break
            except ContinueSignal:
                continue

    def exec_FuncDecl(self, node):
        function = NoonFunction(node.name, node.params, node.body, self.env)
        self.env.declare(node.name, function)

    def exec_Return(self, node):
        value = self.evaluate(node.value) if node.value is not None else None
        raise ReturnSignal(value)

    def exec_Break(self, node):
        raise BreakSignal()

    def exec_Continue(self, node):
        raise ContinueSignal()

    def exec_ClassDecl(self, node):
        parent = None
        if node.parent is not None:
            parent = self.env.get(node.parent, node.line)
            if not isinstance(parent, NoonClass):
                raise NoonRuntimeError("«%s» ليس صنفًا" % node.parent, node.line)
        methods = {}
        for method in node.methods:
            methods[method.name] = NoonFunction(
                method.name, method.params, method.body, self.env, is_method=True)
        self.env.declare(node.name, NoonClass(node.name, parent, methods))

    def exec_Throw(self, node):
        raise NoonThrow(self.evaluate(node.value), node.line)

    def exec_Try(self, node):
        try:
            try:
                self.execute(node.body)
            except NoonThrow as thrown:
                if node.handler is None:
                    raise
                self.run_handler(node, thrown.value)
            except NoonRuntimeError as error:
                if node.handler is None:
                    raise
                self.run_handler(node, {
                    "نوع": "خطأ تشغيل",
                    "رسالة": error.message,
                    "سطر": error.line or node.line,
                })
        finally:
            if node.finally_body is not None:
                self.execute(node.finally_body)

    def run_handler(self, node, value):
        env = Environment(self.env)
        if node.error_name:
            env.declare(node.error_name, value)
        self.execute_block(node.handler.body, env)

    # ——————————— التعابير ———————————
    def eval_Literal(self, node):
        return node.value

    def eval_Identifier(self, node):
        return self.env.get(node.name, node.line)

    def eval_This(self, node):
        if not self.env.has("هذا"):
            raise NoonRuntimeError("«هذا» لا تُستعمل إلا داخل تابع", node.line)
        return self.env.get("هذا", node.line)

    def eval_Super(self, node):
        if not self.env.has("الأصل"):
            raise NoonRuntimeError(
                "«الأصل» لا تُستعمل إلا داخل صنف يرث صنفًا آخر", node.line)
        return self.env.get("الأصل", node.line)

    def eval_ListLit(self, node):
        return [self.evaluate(element) for element in node.elements]

    def eval_DictLit(self, node):
        result = {}
        for key_node, value_node in node.pairs:
            key = self.evaluate(key_node)
            if isinstance(key, bool) or not isinstance(key, (str, int, float)):
                raise NoonRuntimeError(
                    "مفتاح القاموس يجب أن يكون نصًّا أو عددًا", node.line)
            result[key] = self.evaluate(value_node)
        return result

    def eval_FuncExpr(self, node):
        return NoonFunction(node.name, node.params, node.body, self.env)

    def eval_Logical(self, node):
        left = self.evaluate(node.left)
        if node.op == "أو":
            return left if truthy(left) else self.evaluate(node.right)
        return self.evaluate(node.right) if truthy(left) else left

    def eval_Unary(self, node):
        value = self.evaluate(node.operand)
        if node.op == "ليس":
            return not truthy(value)
        if node.op == "-":
            if not is_number(value):
                raise NoonRuntimeError(
                    "لا يمكن نفي قيمة من نوع «%s»" % type_name(value), node.line)
            return -value
        if not is_number(value):
            raise NoonRuntimeError(
                "«+» الأحادية تحتاج عددًا، لا «%s»" % type_name(value), node.line)
        return value

    def eval_Binary(self, node):
        left = self.evaluate(node.left)
        right = self.evaluate(node.right)
        return self.binary(node.op, left, right, node.line)

    def eval_Index(self, node):
        obj = self.evaluate(node.obj)
        key = self.evaluate(node.key)
        return self.get_index(obj, key, node.line)

    def eval_Slice(self, node):
        obj = self.evaluate(node.obj)
        if not isinstance(obj, (str, list)):
            raise NoonRuntimeError(
                "لا يمكن تقطيع قيمة من نوع «%s»" % type_name(obj), node.line)
        start = self.index_int(node.start, node.line)
        end = self.index_int(node.end, node.line)
        return obj[start:end]

    def index_int(self, node, line):
        if node is None:
            return None
        value = self.evaluate(node)
        if not is_number(value) or (isinstance(value, float)
                                    and not value.is_integer()):
            raise NoonRuntimeError("حدود التقطيع يجب أن تكون أعدادًا صحيحة", line)
        return int(value)

    def eval_Member(self, node):
        obj = self.evaluate(node.obj)
        return self.get_member(obj, node.name, node.line)

    def eval_Call(self, node):
        callee = self.evaluate(node.callee)
        args = [self.evaluate(arg) for arg in node.args]
        return self.call(callee, args, node.line)

    # ——————————— العمليات ———————————
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
    def call(self, callee, args, line):
        if isinstance(callee, BuiltinFunction):
            callee.check(len(args), line)
            return callee.fn(self, args, line)

        if isinstance(callee, BoundBuiltin):
            builtin = callee.builtin
            builtin.check(len(args) + 1, line)
            return builtin.fn(self, [callee.receiver] + args, line)

        if isinstance(callee, NoonClass):
            instance = NoonInstance(callee)
            owner, init = callee.find_method(INIT_METHOD)
            if init is not None:
                self.call(init.bind(instance, owner), args, line)
            elif args:
                raise NoonRuntimeError(
                    "الصنف «%s» لا يملك تابع «%s»، فلا يقبل وسائط"
                    % (callee.name, INIT_METHOD), line)
            return instance

        if isinstance(callee, NoonFunction):
            return self.call_function(callee, args, line)

        raise NoonRuntimeError(
            "لا يمكن استدعاء قيمة من نوع «%s»" % type_name(callee), line)

    def call_function(self, function, args, line):
        required = sum(1 for _, default in function.params if default is None)
        if len(args) < required or len(args) > len(function.params):
            raise NoonRuntimeError(
                "الدالة «%s» تتوقّع %s وسيطًا، ووصلها %d"
                % (function.name,
                   str(required) if required == len(function.params)
                   else "%d..%d" % (required, len(function.params)),
                   len(args)), line)

        env = Environment(function.closure)
        for index, (name, default) in enumerate(function.params):
            if index < len(args):
                env.declare(name, args[index])
            else:
                previous = self.env
                self.env = env
                try:
                    env.declare(name, self.evaluate(default))
                finally:
                    self.env = previous

        try:
            self.execute_block(function.body.body, env)
        except ReturnSignal as signal:
            return signal.value
        except RecursionError:
            raise NoonRuntimeError(
                "تجاوز عمق الاستدعاء (تعاود لا ينتهي؟) في «%s»" % function.name,
                line)
        return None

    # ——————————— العرض ———————————
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


def run(source, out=None):
    """ينفّذ شيفرة «نون» ويُرجع المُفسِّر (للاختبارات والتضمين)."""
    interpreter = Interpreter(out=out)
    interpreter.run(source)
    return interpreter
