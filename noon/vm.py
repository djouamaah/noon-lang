# -*- coding: utf-8 -*-
"""الآلة الافتراضية: تنفّذ البايت-كود الذي يُنتجه `compiler.py`.

آلة مكدّسية: مكدّس قيم واحد مشترك، وإطار لكل استدعاء فيه خاناته المحلّية
وموضع التعليمة. العمليات على القيم (الجمع، الفهرسة، العرض…) موروثة من
`Runtime`، أي هي نفسها التي يستعملها المُفسِّر؛ وما هنا طريقة التنفيذ فقط،
مع طرق مختصرة للحالات الشائعة (عددان، نصّان) تُعطي النتيجة نفسها.
"""

import sys

from . import builtins as B
from . import opcodes as O
from .bytecode import CompiledFunction
from .compiler import compile_program
from .errors import NoonRuntimeError, NoonThrow
from .parser import parse
from .runtime import INIT_METHOD, Runtime
from .values import (BoundBuiltin, BoundMethod, BuiltinFunction, Cell, Closure,
                     NoonClass, NoonInstance, SuperProxy, is_number, truthy,
                     type_name)

MAX_FRAMES = 5000

_UNSET = object()        # خليّة حُجزت لإغلاق قبل أن يُنفَّذ تصريح متغيّرها
_DONE = object()

_ADD, _SUB, _MUL = O.BINARY_INDEX["+"], O.BINARY_INDEX["-"], O.BINARY_INDEX["*"]
_MOD, _FLOORDIV = O.BINARY_INDEX["%"], O.BINARY_INDEX["//"]
_EQ, _NE = O.BINARY_INDEX["=="], O.BINARY_INDEX["!="]
_LT, _GT = O.BINARY_INDEX["<"], O.BINARY_INDEX[">"]
_LE, _GE = O.BINARY_INDEX["<="], O.BINARY_INDEX[">="]


class Frame:
    __slots__ = ("closure", "function", "locals", "ip", "base", "handlers",
                 "pending", "init_instance")

    def __init__(self, closure, function, slots, ip, base, init_instance=None):
        self.closure = closure
        self.function = function
        self.locals = slots
        self.ip = ip
        self.base = base
        self.handlers = []
        self.pending = None
        self.init_instance = init_instance


def _line(frame, ip):
    return frame.function.lines[(ip - 2) >> 1]


class VM(Runtime):
    def __init__(self, out=None):
        self.out = out if out is not None else sys.stdout
        self.globals = dict(B.GLOBALS)
        self.constants = set(B.GLOBALS)
        self.frames = []
        self.stack = []

    # ——————————————— الواجهة ———————————————

    def run(self, source, repl=False):
        """يترجم نصًّا وينفّذه، ويُرجع قيمة آخر تعبير إن كان repl."""
        return self.execute(compile_program(parse(source), repl=repl))

    def execute(self, script, globals_=None, constants=None):
        """ينفّذ برنامجًا مُترجَمًا؛ بعوامّ الآلة، أو بعوامّ وحدة تُستورد."""
        if not isinstance(script, CompiledFunction):
            raise TypeError("execute تنتظر دالة مُترجَمة")
        if globals_ is None:
            globals_, constants = self.globals, self.constants
        frames, stack = self.frames, self.stack
        frame_base, stack_base = len(frames), len(stack)
        frames.append(Frame(Closure(script, (), None, globals_, constants), script,
                            [None] * script.n_slots, 0, stack_base))
        try:
            return self._run(len(frames))
        finally:                                  # حالة نظيفة للصدفة بعد أي خطأ
            del frames[frame_base:]
            del stack[stack_base:]

    def load_module(self, program, module):
        """ينفّذ برنامج وحدة بعوامّ خاصّة بها."""
        globals_ = module.namespace = dict(B.GLOBALS)
        self.register_module(globals_, module)
        self.execute(compile_program(program), globals_, set(B.GLOBALS))

    def _locate(self, error):
        """وحدة الإطار الذي وقع فيه الخطأ، وسطر البرنامج الذي بدأ النداء إليها."""
        error.located = True
        frames = self.frames
        error.module = self.module_of(frames[-1].closure.globals)
        if error.module is None:
            return
        for frame in reversed(frames[:-1]):
            if self.module_of(frame.closure.globals) is None:
                error.program_line = _line(frame, frame.ip)
                return

    def call(self, callee, args, line):
        """استدعاء من خارج حلقة التنفيذ، كما تفعل `طبّق` و`فرز` بدالة المفتاح."""
        kind = type(callee)
        if kind is BuiltinFunction:
            callee.check(len(args), line)
            return callee.fn(self, list(args), line)
        if kind is BoundBuiltin:
            callee.builtin.check(len(args) + 1, line)
            return callee.builtin.fn(self, [callee.receiver] + list(args), line)
        stack = self.stack
        stack.append(callee)
        stack.extend(args)
        if not self._call(len(args), line):
            return stack.pop()
        try:
            return self._run(len(self.frames))
        except RecursionError:
            raise NoonRuntimeError("تجاوز عمق الاستدعاء (تعاود لا ينتهي؟) في «%s»"
                                   % getattr(callee, "name", "دالة"), line)

    # ——————————————— الاستدعاء ———————————————

    def _call(self, argc, line):
        """يُعِدّ الاستدعاء. يُرجع True إن دُفع إطار جديد، وإلا دُفعت النتيجة."""
        stack = self.stack
        callee = stack[-argc - 1]
        kind = type(callee)
        if kind is Closure:
            return self._push_frame(callee, None, None, argc, line)
        if kind is BoundMethod:
            return self._push_frame(callee.closure, callee.instance, None, argc, line)
        if kind is BuiltinFunction:
            callee.check(argc, line)
            args = stack[len(stack) - argc:]
            del stack[len(stack) - argc - 1:]
            stack.append(callee.fn(self, args, line))
            return False
        if kind is BoundBuiltin:
            builtin = callee.builtin
            builtin.check(argc + 1, line)
            args = [callee.receiver] + stack[len(stack) - argc:]
            del stack[len(stack) - argc - 1:]
            stack.append(builtin.fn(self, args, line))
            return False
        if kind is NoonClass:
            instance = NoonInstance(callee)
            owner, init = callee.find_method(INIT_METHOD)
            if init is not None:
                return self._push_frame(init, instance, instance, argc, line)
            if argc:
                raise NoonRuntimeError(
                    "الصنف «%s» لا يملك تابع «%s»، فلا يقبل وسائط"
                    % (callee.name, INIT_METHOD), line)
            stack[-1] = instance
            return False
        raise NoonRuntimeError(
            "لا يمكن استدعاء قيمة من نوع «%s»" % type_name(callee), line)

    def _push_frame(self, closure, instance, init_instance, argc, line):
        fn = closure.function
        total = len(fn.param_names)
        if argc < fn.required or argc > total:
            expected = (str(fn.required) if fn.required == total
                        else "%d..%d" % (fn.required, total))
            raise NoonRuntimeError("الدالة «%s» تتوقّع %s وسيطًا، ووصلها %d"
                                   % (fn.name, expected, argc), line)
        if len(self.frames) >= MAX_FRAMES:
            raise NoonRuntimeError(
                "تجاوز عمق الاستدعاء (تعاود لا ينتهي؟) في «%s»" % fn.name, line)

        stack = self.stack
        base = len(stack) - argc - 1
        slots = [None] * fn.n_slots
        offset = 1 if fn.is_method else 0
        if offset:
            slots[0] = instance
        if argc:
            slots[offset:offset + argc] = stack[base + 1:]
        del stack[base:]
        if fn.cell_params:
            given = offset + argc
            for slot in fn.cell_params:
                if slot < given:
                    slots[slot] = Cell(slots[slot])
        self.frames.append(Frame(closure, fn, slots, fn.entries[argc - fn.required],
                                 base, init_instance))
        return True

    # ——————————————— الأخطاء ———————————————

    def _unwind(self, error, base_depth, line):
        """يبحث عن «امسك» أو «أخيرًا» من الإطار الحالي نزولًا، وإلا يُعيد الرمي."""
        if isinstance(error, NoonThrow):
            value = error.value
        else:
            value = {"نوع": "خطأ تشغيل", "رسالة": error.message,
                     "سطر": error.line or line}
        frames, stack = self.frames, self.stack
        while len(frames) >= base_depth:
            frame = frames[-1]
            handlers = frame.handlers
            while handlers:
                index, depth = handlers.pop()
                catch_ip, finally_ip, finally_id = frame.function.handlers[index]
                del stack[depth:]
                if catch_ip >= 0:
                    stack.append(value)
                    frame.ip = catch_ip
                    return
                if finally_ip >= 0:
                    if frame.pending is None:
                        frame.pending = {}
                    frame.pending[finally_id] = error
                    frame.ip = finally_ip
                    return
            frames.pop()
            del stack[frame.base:]
        raise error

    # ——————————————— حلقة التنفيذ ———————————————

    def _run(self, base_depth):
        frames = self.frames
        stack = self.stack
        push = stack.append
        pop = stack.pop

        while True:
            frame = frames[-1]
            fn = frame.function
            globals_ = frame.closure.globals      # عوامّ ملف الدالة (انظر Closure)
            constants = frame.closure.constants
            code = fn.code
            consts = fn.consts
            names = fn.names
            slots = frame.locals
            ip = frame.ip
            try:
                while True:
                    opcode = code[ip]
                    arg = code[ip + 1]
                    ip += 2

                    if opcode == O.LOAD_LOCAL:
                        push(slots[arg])

                    elif opcode == O.BINARY:
                        right = pop()
                        left = stack[-1]
                        lt, rt = type(left), type(right)
                        if (lt is int or lt is float) and (rt is int or rt is float):
                            if arg == _ADD:
                                stack[-1] = left + right
                                continue
                            if arg == _LT:
                                stack[-1] = left < right
                                continue
                            if arg == _SUB:
                                stack[-1] = left - right
                                continue
                            if right != 0 and arg == _MOD:
                                stack[-1] = left % right
                                continue
                            if arg == _EQ:
                                stack[-1] = left == right
                                continue
                            if arg == _MUL:
                                stack[-1] = left * right
                                continue
                            if arg == _LE:
                                stack[-1] = left <= right
                                continue
                            if arg == _GT:
                                stack[-1] = left > right
                                continue
                            if arg == _GE:
                                stack[-1] = left >= right
                                continue
                            if arg == _NE:
                                stack[-1] = left != right
                                continue
                            if right != 0 and arg == _FLOORDIV:
                                stack[-1] = left // right
                                continue
                        elif lt is str and rt is str:
                            if arg == _ADD:
                                stack[-1] = left + right
                                continue
                            if arg == _EQ:
                                stack[-1] = left == right
                                continue
                            if arg == _NE:
                                stack[-1] = left != right
                                continue
                        stack[-1] = self.binary(O.BINARY_OPS[arg], left, right,
                                                _line(frame, ip))

                    elif opcode == O.LOAD_CONST:
                        push(consts[arg])

                    elif opcode == O.LOAD_GLOBAL:
                        try:
                            push(globals_[names[arg]])
                        except KeyError:
                            raise NoonRuntimeError("المتغيّر «%s» غير مُعرَّف"
                                                   % names[arg], _line(frame, ip))

                    elif opcode == O.RETURN:
                        value = pop()
                        del stack[frame.base:]
                        frames.pop()
                        if frame.init_instance is not None:
                            value = frame.init_instance
                        if len(frames) < base_depth:
                            return value
                        push(value)
                        break

                    elif opcode == O.JUMP_IF_FALSE:
                        value = pop()
                        if value is not True and (value is False or value is None
                                                  or not truthy(value)):
                            ip = arg

                    elif opcode == O.JUMP_IF_TRUE:
                        value = pop()
                        if value is True or (value is not False and value is not None
                                             and truthy(value)):
                            ip = arg

                    elif opcode == O.CALL:
                        frame.ip = ip
                        if self._call(arg, _line(frame, ip)):
                            break

                    elif opcode == O.JUMP:
                        ip = arg

                    elif opcode == O.GET_MEMBER:
                        stack[-1] = self.get_member(stack[-1], names[arg], _line(frame, ip))

                    elif opcode == O.STORE_LOCAL:
                        slots[arg] = pop()

                    elif opcode == O.SET_MEMBER:
                        obj = pop()
                        value = pop()
                        if isinstance(obj, NoonInstance):
                            obj.set(names[arg], value)
                        elif isinstance(obj, dict):
                            obj[names[arg]] = value
                        else:
                            raise NoonRuntimeError(
                                "لا يمكن إسناد عضو إلى قيمة من نوع «%s»" % type_name(obj),
                                _line(frame, ip))

                    elif opcode == O.STORE_GLOBAL:
                        name = names[arg]
                        if name not in globals_:
                            raise NoonRuntimeError(
                                "المتغيّر «%s» غير مُعرَّف؛ استعمل «متغير %s = ...» أوّلًا"
                                % (name, name), _line(frame, ip))
                        if name in constants:
                            raise NoonRuntimeError(
                                "«%s» ثابت، لا يمكن تغيير قيمته" % name, _line(frame, ip))
                        globals_[name] = pop()

                    elif opcode == O.LOAD_FREE:
                        value = frame.closure.cells[arg].value
                        if value is _UNSET:
                            raise NoonRuntimeError("المتغيّر «%s» غير مُعرَّف"
                                                   % fn.freevars[arg][2], _line(frame, ip))
                        push(value)

                    elif opcode == O.FOR_ITER:
                        value = next(stack[-1], _DONE)
                        if value is _DONE:
                            pop()
                            ip = arg
                        else:
                            push(value)

                    elif opcode == O.SET_INDEX:
                        key = pop()
                        obj = pop()
                        self.set_index(obj, key, pop(), _line(frame, ip))

                    elif opcode == O.JUMP_IF_TRUE_KEEP:
                        if truthy(stack[-1]):
                            ip = arg

                    elif opcode == O.JUMP_IF_FALSE_KEEP:
                        if not truthy(stack[-1]):
                            ip = arg

                    elif opcode == O.GET_INDEX:
                        key = pop()
                        obj = stack[-1]
                        if type(obj) is list and type(key) is int and -len(obj) <= key < len(obj):
                            stack[-1] = obj[key]
                        else:
                            stack[-1] = self.get_index(obj, key, _line(frame, ip))

                    elif opcode == O.POP:
                        pop()

                    elif opcode == O.MAKE_CLOSURE:
                        function = consts[arg]
                        cells = []
                        for kind, index, _ in function.freevars:
                            if kind == 0:
                                cell = slots[index]
                                if type(cell) is not Cell:
                                    cell = slots[index] = Cell(_UNSET)
                            else:
                                cell = frame.closure.cells[index]
                            cells.append(cell)
                        push(Closure(function, tuple(cells), frame.closure.owner,
                                             globals_, constants))

                    elif opcode == O.SWAP:
                        stack[-1], stack[-2] = stack[-2], stack[-1]

                    elif opcode == O.LOAD_CELL:
                        cell = slots[arg]
                        if cell is None or cell.value is _UNSET:
                            raise NoonRuntimeError("المتغيّر «%s» غير مُعرَّف"
                                                   % fn.slot_names[arg], _line(frame, ip))
                        push(cell.value)

                    elif opcode == O.STORE_CELL:
                        cell = slots[arg]
                        if cell is None or cell.value is _UNSET:
                            raise NoonRuntimeError(
                                "المتغيّر «%s» غير مُعرَّف؛ استعمل «متغير %s = ...» أوّلًا"
                                % (fn.slot_names[arg], fn.slot_names[arg]), _line(frame, ip))
                        cell.value = pop()

                    elif opcode == O.INIT_CELL:
                        value = pop()
                        cell = slots[arg]
                        if type(cell) is Cell and cell.value is _UNSET:
                            cell.value = value
                        else:
                            slots[arg] = Cell(value)

                    elif opcode == O.STORE_FREE:
                        cell = frame.closure.cells[arg]
                        if cell.value is _UNSET:
                            name = fn.freevars[arg][2]
                            raise NoonRuntimeError(
                                "المتغيّر «%s» غير مُعرَّف؛ استعمل «متغير %s = ...» أوّلًا"
                                % (name, name), _line(frame, ip))
                        cell.value = pop()

                    elif opcode == O.ENTER_SCOPE:
                        for slot in fn.scope_cells[arg]:
                            slots[slot] = None

                    elif opcode == O.NOT:
                        stack[-1] = not truthy(stack[-1])

                    elif opcode == O.NEGATE:
                        value = stack[-1]
                        if not is_number(value):
                            raise NoonRuntimeError(
                                "لا يمكن نفي قيمة من نوع «%s»" % type_name(value),
                                _line(frame, ip))
                        stack[-1] = -value

                    elif opcode == O.POSITIVE:
                        value = stack[-1]
                        if not is_number(value):
                            raise NoonRuntimeError(
                                "«+» الأحادية تحتاج عددًا، لا «%s»" % type_name(value),
                                _line(frame, ip))

                    elif opcode == O.DEFINE_GLOBAL or opcode == O.DEFINE_GLOBAL_CONST:
                        name = names[arg]
                        if name in globals_:
                            raise NoonRuntimeError(
                                "«%s» مُعرَّف مسبقًا في هذا النطاق" % name, _line(frame, ip))
                        globals_[name] = pop()
                        if opcode == O.DEFINE_GLOBAL_CONST:
                            constants.add(name)

                    elif opcode == O.DEFINE_GLOBAL_FORCE:
                        name = names[arg]
                        globals_[name] = pop()
                        constants.discard(name)

                    elif opcode == O.BUILD_LIST:
                        if arg:
                            items = stack[len(stack) - arg:]
                            del stack[len(stack) - arg:]
                        else:
                            items = []
                        push(items)

                    elif opcode == O.BUILD_DICT:
                        size = 2 * arg
                        items = stack[len(stack) - size:] if size else []
                        if size:
                            del stack[len(stack) - size:]
                        result = {}
                        for i in range(0, size, 2):
                            key = items[i]
                            if isinstance(key, bool) or not isinstance(key, (str, int, float)):
                                raise NoonRuntimeError(
                                    "مفتاح القاموس يجب أن يكون نصًّا أو عددًا",
                                    _line(frame, ip))
                            result[key] = items[i + 1]
                        push(result)

                    elif opcode == O.BUILD_CLASS:
                        count = arg >> 1
                        methods = stack[len(stack) - count:] if count else []
                        if count:
                            del stack[len(stack) - count:]
                        parent = None
                        if arg & 1:
                            parent = pop()
                            parent_name = pop()
                            if not isinstance(parent, NoonClass):
                                raise NoonRuntimeError("«%s» ليس صنفًا" % parent_name,
                                                       _line(frame, ip))
                        table = {}
                        klass = NoonClass(pop(), parent, table)
                        for method in methods:
                            method.owner = klass
                            table[method.function.name] = method
                        push(klass)

                    elif opcode == O.GET_SLICE:
                        end = pop() if arg & 2 else None
                        start = pop() if arg & 1 else None
                        stack[-1] = self._slice(stack[-1], start, end, arg,
                                                _line(frame, ip))

                    elif opcode == O.SUPER_PROXY:
                        instance = pop()
                        owner = frame.closure.owner
                        if owner is None or owner.parent is None:
                            raise NoonRuntimeError(
                                "«الأصل» لا تُستعمل إلا داخل صنف يرث صنفًا آخر",
                                _line(frame, ip))
                        push(SuperProxy(instance, owner.parent))

                    elif opcode == O.ITER_NEW:
                        stack[-1] = iter(self.iterate(stack[-1], _line(frame, ip)))

                    elif opcode == O.THROW:
                        raise NoonThrow(pop(), _line(frame, ip))

                    elif opcode == O.SETUP_TRY:
                        frame.handlers.append((arg, len(stack)))

                    elif opcode == O.POP_TRY:
                        frame.handlers.pop()

                    elif opcode == O.END_FINALLY:
                        if frame.pending:
                            error = frame.pending.pop(arg, None)
                            if error is not None:
                                raise error

                    elif opcode == O.RAISE_ERROR:
                        raise NoonRuntimeError(consts[arg], _line(frame, ip))

                    else:
                        raise NoonRuntimeError("تعليمة غير معروفة: %d" % opcode,
                                               _line(frame, ip))

            except (NoonRuntimeError, NoonThrow) as error:
                if isinstance(error, NoonRuntimeError) and not error.located:
                    self._locate(error)
                self._unwind(error, base_depth, _line(frame, ip))

    def _slice(self, obj, start, end, mask, line):
        if not isinstance(obj, (str, list)):
            raise NoonRuntimeError("لا يمكن تقطيع قيمة من نوع «%s»" % type_name(obj), line)
        bounds = []
        for present, value in ((mask & 1, start), (mask & 2, end)):
            if not present:
                bounds.append(None)
                continue
            if not is_number(value) or (isinstance(value, float) and not value.is_integer()):
                raise NoonRuntimeError("حدود التقطيع يجب أن تكون أعدادًا صحيحة", line)
            bounds.append(int(value))
        return obj[bounds[0]:bounds[1]]


def run(source, out=None):
    """يترجم شيفرة «نون» وينفّذها في آلة جديدة، ويُرجع الآلة."""
    vm = VM(out=out)
    vm.run(source)
    return vm
