# -*- coding: utf-8 -*-
"""المترجِم: الشجرة النحوية ← بايت-كود تنفّذه الآلة الافتراضية (`vm.py`).

دلالات الترجمة مطابقة للمُفسِّر (`interpreter.py`)؛ والاختبارات تشغّل كل
برنامج في المحرّكين وتقارن الناتج. أهمّ ما يلزم لذلك:

**الأسماء تُحَلّ وقت الترجمة.** كل اسم إمّا خانة محلّية مرقّمة، أو خليّة
(محلّي التقطته دالة داخلية)، أو متغيّر حرّ من دالة محيطة، أو عامّ. المستوى
الأعلى من البرنامج عامّ (قاموس)، فتبقى تعريفات الصدفة التفاعلية بين الأسطر.

**التعريف اللاحق يُعيد الربط.** في المُفسِّر يُبحث عن الاسم حين يُنفَّذ، فدالة
داخلية ترى متغيّرًا عُرِّف بعدها في الدالة المحيطة. لذلك تُسجَّل كل إحالة من
دالة داخلية إلى ما خارجها، وإذا عُرِّف الاسم لاحقًا في نطاق أقرب إليها أُعيد
توجيه تعليمتها إلى التعريف الجديد (انظر `_rebind_watchers`).

**الخلايا تُنشأ لكل دخول إلى النطاق.** المُفسِّر يصنع بيئة جديدة في كل دورة
حلقة، فالإغلاق داخل الحلقة يلتقط متغيّرات دورته. هنا تُفرغ `ENTER_SCOPE`
خلايا النطاق في أوّل كل دورة، و`INIT_CELL` تملأ خليّة جديدة عند التصريح.

**«أخيرًا» على كل طريق خروج.** تُنسخ كتلتها بعد النجاح، وفي طريق الخطأ
(ثم تُعيد `END_FINALLY` رميه)، وقبل كل `أرجع` و`توقف` و`استمر` تعبرها.
"""

from . import ast_nodes as A
from . import opcodes as O
from .bytecode import CompiledFunction
from .errors import MISPLACED
from .parser import parse

THIS = "هذا"


class Local:
    """متغيّر محلّي معروف وقت الترجمة."""

    __slots__ = ("name", "slot", "const", "scope", "fn", "is_cell", "is_param",
                 "refs", "decls")

    def __init__(self, name, slot, const, scope, fn):
        self.name = name
        self.slot = slot
        self.const = const
        self.scope = scope
        self.fn = fn
        self.is_cell = False
        self.is_param = False
        self.refs = []           # مواضع قراءته والإسناد إليه في شيفرة دالته
        self.decls = []          # مواضع تصريحه (تصير INIT_CELL إن التُقط)


class Scope:
    __slots__ = ("names", "parent", "fn", "index", "is_global")

    def __init__(self, parent, fn, index, is_global=False):
        self.names = {}
        self.parent = parent     # قد يكون نطاقًا في الدالة المحيطة
        self.fn = fn
        self.index = index
        self.is_global = is_global


class Watch:
    """إحالة من دالة داخلية إلى اسم خارجها، قد يُعاد ربطها بتعريف لاحق."""

    __slots__ = ("fn", "pos", "chain", "resolved", "load")

    def __init__(self, fn, pos, chain, resolved, load):
        self.fn = fn
        self.pos = pos
        self.chain = chain       # نطاقات الدوال المحيطة، من الأقرب إلى الأبعد
        self.resolved = resolved  # Local، أو None إن كان عامًّا
        self.load = load


class Loop:
    __slots__ = ("continue_target", "breaks", "try_depth", "has_iterator")

    def __init__(self, continue_target, try_depth, has_iterator):
        self.continue_target = continue_target
        self.breaks = []
        self.try_depth = try_depth
        self.has_iterator = has_iterator


class TryContext:
    """موضع الشيفرة الحالي من جملة «حاول»."""

    __slots__ = ("state", "finally_body")

    def __init__(self, state, finally_body):
        self.state = state       # body | catch_fin | catch | finally
        self.finally_body = finally_body


class FunctionState:
    def __init__(self, name, parent, is_method=False, is_script=False):
        self.out = CompiledFunction(name, is_method, is_script)
        self.parent = parent
        self.scope = None
        self.root_scope = None
        self.loops = []
        self.tries = []
        self.free_map = {}
        self.const_map = {}
        self.name_map = {}
        self.finally_count = 0


class Compiler:
    def __init__(self):
        self.fs = None
        self.watchers = {}

    # ——————————————— أدوات الإصدار ———————————————

    def emit(self, opcode, arg=0, line=0):
        code = self.fs.out.code
        pos = len(code)
        code.append(opcode)
        code.append(arg)
        self.fs.out.lines.append(line)
        return pos

    def here(self):
        return len(self.fs.out.code)

    def patch(self, pos, target=None):
        self.fs.out.code[pos + 1] = self.here() if target is None else target

    def const(self, value):
        fs = self.fs
        if isinstance(value, CompiledFunction):
            fs.out.consts.append(value)
            return len(fs.out.consts) - 1
        key = (type(value).__name__, repr(value))
        if key not in fs.const_map:
            fs.out.consts.append(value)
            fs.const_map[key] = len(fs.out.consts) - 1
        return fs.const_map[key]

    def name_index(self, name):
        fs = self.fs
        if name not in fs.name_map:
            fs.out.names.append(name)
            fs.name_map[name] = len(fs.out.names) - 1
        return fs.name_map[name]

    def raise_error(self, message, line):
        self.emit(O.RAISE_ERROR, self.const(message), line)

    # ——————————————— النطاقات والأسماء ———————————————

    def in_global_scope(self):
        return self.fs.scope.is_global

    def begin_scope(self, line):
        fs = self.fs
        scope = Scope(fs.scope, fs, len(fs.out.scope_cells))
        fs.out.scope_cells.append([])
        fs.scope = scope
        if fs.loops:                    # نطاق يُدخَل أكثر من مرّة في الإطار نفسه
            self.emit(O.ENTER_SCOPE, scope.index, line)
        return scope

    def end_scope(self):
        fs = self.fs
        scope = fs.scope
        fs.out.scope_cells[scope.index] = sorted(
            local.slot for local in scope.names.values() if local.is_cell)
        fs.scope = scope.parent

    def declare_local(self, name, const=False):
        fs = self.fs
        slot = fs.out.n_slots
        fs.out.n_slots += 1
        fs.out.slot_names.append(name)
        local = Local(name, slot, const, fs.scope, fs)
        fs.scope.names[name] = local
        self._rebind_watchers(name, local)
        return local

    def lookup(self, name):
        scope = self.fs.scope
        while scope is not None:
            if not scope.is_global and name in scope.names:
                return scope.names[name]
            scope = scope.parent
        return None

    def promote(self, local):
        """محلّي التقطته دالة داخلية: تعليماته كلها تصير تعليمات خلايا."""
        if local.is_cell:
            return
        local.is_cell = True
        code = local.fn.out.code
        for pos in local.refs:
            if code[pos] == O.LOAD_LOCAL:
                code[pos] = O.LOAD_CELL
            elif code[pos] == O.STORE_LOCAL:
                code[pos] = O.STORE_CELL
        for pos in local.decls:
            code[pos] = O.INIT_CELL
        if local.is_param:
            local.fn.out.cell_params.append(local.slot)

    def capture(self, fs, local):
        """فهرس المتغيّر الحرّ في `fs` الذي يصل إلى `local` عبر سلسلة الدوال."""
        if local in fs.free_map:
            return fs.free_map[local]
        self.promote(local)
        if fs.parent is local.fn:
            entry = (0, local.slot, local.name)
        else:
            entry = (1, self.capture(fs.parent, local), local.name)
        fs.out.freevars.append(entry)
        fs.free_map[local] = len(fs.out.freevars) - 1
        return fs.free_map[local]

    def _watch(self, name, pos, resolved, load):
        fs = self.fs
        if fs.parent is None:
            return
        chain = []
        scope = fs.root_scope.parent
        while scope is not None:
            chain.append(scope)
            scope = scope.parent
        self.watchers.setdefault(name, []).append(
            Watch(fs, pos, chain, resolved, load))

    def _rebind_watchers(self, name, local):
        for watch in self.watchers.get(name, ()):
            chain = watch.chain
            if local.scope not in chain:
                continue
            if watch.resolved is not None and watch.resolved.scope in chain and \
                    chain.index(watch.resolved.scope) <= chain.index(local.scope):
                continue                 # الإحالة مربوطة بتعريف أقرب
            index = self.capture(watch.fn, local)
            code = watch.fn.out.code
            code[watch.pos] = O.LOAD_FREE if watch.load else O.STORE_FREE
            code[watch.pos + 1] = index
            watch.resolved = local

    def load_name(self, name, line):
        local = self.lookup(name)
        fs = self.fs
        if local is None:
            pos = self.emit(O.LOAD_GLOBAL, self.name_index(name), line)
            self._watch(name, pos, None, True)
        elif local.fn is fs:
            pos = self.emit(O.LOAD_CELL if local.is_cell else O.LOAD_LOCAL,
                            local.slot, line)
            local.refs.append(pos)
        else:
            pos = self.emit(O.LOAD_FREE, self.capture(fs, local), line)
            self._watch(name, pos, local, True)

    def store_name(self, name, line):
        """يخزّن قمّة المكدس في اسم موجود (إسناد لا تصريح)."""
        local = self.lookup(name)
        fs = self.fs
        if local is None:
            pos = self.emit(O.STORE_GLOBAL, self.name_index(name), line)
            self._watch(name, pos, None, False)
        elif local.const:
            self.raise_error("«%s» ثابت، لا يمكن تغيير قيمته" % name, line)
        elif local.fn is fs:
            pos = self.emit(O.STORE_CELL if local.is_cell else O.STORE_LOCAL,
                            local.slot, line)
            local.refs.append(pos)
        else:
            pos = self.emit(O.STORE_FREE, self.capture(fs, local), line)
            self._watch(name, pos, local, False)

    def emit_decl(self, local, line):
        pos = self.emit(O.INIT_CELL if local.is_cell else O.STORE_LOCAL, local.slot, line)
        local.decls.append(pos)

    # ——————————————— البرنامج والدوال ———————————————

    def compile_program(self, program, repl=False):
        fs = FunctionState("<البرنامج>", None, is_script=True)
        self.fs = fs
        fs.scope = fs.root_scope = Scope(None, fs, -1, is_global=True)

        body = program.body
        last_line = body[-1].line if body else 1
        if repl and body and isinstance(body[-1], A.ExprStmt):
            for statement in body[:-1]:
                self.statement(statement)
            self.expression(body[-1].expr)
        else:
            for statement in body:
                self.statement(statement)
            self.emit(O.LOAD_CONST, self.const(None), last_line)
        self.emit(O.RETURN, 0, last_line)
        fs.out.entries = [0]
        # بعد اكتمال البرنامج كلّه فقط: إعادة الربط قد تُعدّل دالة منتهية حتى آخر سطر
        _strip_noops(fs.out, set())
        return fs.out

    def function(self, name, params, body, line, is_method=False):
        parent = self.fs
        fs = FunctionState(name, parent, is_method=is_method)
        self.fs = fs
        fs.root_scope = fs.scope = Scope(parent.scope, fs, 0)
        fs.out.scope_cells.append([])
        out = fs.out

        if is_method:
            self.declare_local(THIS).is_param = True
        out.param_names = [param for param, _ in params]
        required = sum(1 for _, default in params if default is None)
        out.required = required

        for param, _ in params[:required]:
            self.declare_local(param).is_param = True
        entries = []
        for param, default in params[required:]:
            entries.append(self.here())
            if default is None:
                self.emit(O.LOAD_CONST, self.const(None), line)
            else:
                self.expression(default)
            local = self.declare_local(param)
            local.is_param = True
            self.emit_decl(local, line)
        entries.append(self.here())
        out.entries = entries

        for statement in body.body:
            self.statement(statement)
        end_line = body.body[-1].line if body.body else line
        self.emit(O.LOAD_CONST, self.const(None), end_line)
        self.emit(O.RETURN, 0, end_line)
        self.end_scope()

        self.fs = parent
        self.emit(O.MAKE_CLOSURE, self.const(out), line)
        return out

    # ——————————————— الجُمل ———————————————

    def statement(self, node):
        getattr(self, "stmt_" + type(node).__name__)(node)

    def block(self, node):
        self.begin_scope(node.line)
        for statement in node.body:
            self.statement(statement)
        self.end_scope()

    def stmt_Block(self, node):
        self.block(node)

    def stmt_ExprStmt(self, node):
        self.expression(node.expr)
        self.emit(O.POP, 0, node.line)

    def stmt_VarDecl(self, node):
        if node.value is None:
            self.emit(O.LOAD_CONST, self.const(None), node.line)
        else:
            self.expression(node.value)
        if self.in_global_scope():
            self.emit(O.DEFINE_GLOBAL_CONST if node.constant else O.DEFINE_GLOBAL,
                      self.name_index(node.name), node.line)
        elif node.name in self.fs.scope.names:
            self.raise_error("«%s» مُعرَّف مسبقًا في هذا النطاق" % node.name, node.line)
        else:
            self.emit_decl(self.declare_local(node.name, node.constant), node.line)

    def _declare_named(self, name, line, build):
        """«دالة» و«صنف»: تستبدلان ما في النطاق بالاسم نفسه كما في المُفسِّر."""
        if self.in_global_scope():
            build()
            self.emit(O.DEFINE_GLOBAL_FORCE, self.name_index(name), line)
            return
        existing = self.fs.scope.names.get(name)
        if existing is not None:
            existing.const = False
            build()
            pos = self.emit(O.STORE_CELL if existing.is_cell else O.STORE_LOCAL,
                            existing.slot, line)
            existing.refs.append(pos)
        else:
            local = self.declare_local(name)
            build()
            self.emit_decl(local, line)

    def stmt_FuncDecl(self, node):
        self._declare_named(node.name, node.line, lambda: self.function(
            node.name, node.params, node.body, node.line))

    def stmt_ClassDecl(self, node):
        self.emit(O.LOAD_CONST, self.const(node.name), node.line)
        if node.parent is not None:              # الأب يُحَلّ قبل تعريف الاسم
            self.emit(O.LOAD_CONST, self.const(node.parent), node.line)
            self.load_name(node.parent, node.line)

        def build():
            for method in node.methods:
                self.function(method.name, method.params, method.body, method.line,
                              is_method=True)
            self.emit(O.BUILD_CLASS,
                      len(node.methods) * 2 + (1 if node.parent is not None else 0),
                      node.line)

        self._declare_named(node.name, node.line, build)

    def stmt_Assign(self, node):
        target, line = node.target, node.line
        binary = O.BINARY_INDEX.get(node.op) if node.op else None

        if isinstance(target, A.Identifier) and node.op and isinstance(node.value, A.Literal):
            # «ع += ١»: حساب ثابت لا أثر له، فيُقرأ الهدف أوّلًا بلا تبديل
            self.load_name(target.name, line)
            self.expression(node.value)
            self.emit(O.BINARY, binary, line)
            self.store_name(target.name, line)
            return

        # المُفسِّر يحسب القيمة قبل قراءة الهدف، فالترتيب هنا مثله
        self.expression(node.value)
        if isinstance(target, A.Identifier):
            if node.op:
                self.load_name(target.name, line)
                self.emit(O.SWAP, 0, line)
                self.emit(O.BINARY, binary, line)
            self.store_name(target.name, line)
        elif isinstance(target, A.Index):
            if node.op:
                self.expression(target.obj)
                self.expression(target.key)
                self.emit(O.GET_INDEX, 0, line)
                self.emit(O.SWAP, 0, line)
                self.emit(O.BINARY, binary, line)
            self.expression(target.obj)
            self.expression(target.key)
            self.emit(O.SET_INDEX, 0, line)
        else:
            if node.op:
                self.expression(target.obj)
                self.emit(O.GET_MEMBER, self.name_index(target.name), line)
                self.emit(O.SWAP, 0, line)
                self.emit(O.BINARY, binary, line)
            self.expression(target.obj)
            self.emit(O.SET_MEMBER, self.name_index(target.name), line)

    def condition(self, node, jump_if):
        """شرط تُهمّ صدقيّته لا قيمته: قفزات مباشرة بدل حساب القيمة ثم فحصها.

        يُرجع مواضع القفزات التي تُنفَّذ حين تكون صدقيّة الشرط هي `jump_if`،
        ليرقّعها المُنادي. «و» و«أو» تُختصران كما في التعبير تمامًا.
        """
        if isinstance(node, A.Unary) and node.op == "ليس":
            return self.condition(node.operand, not jump_if)
        if isinstance(node, A.Logical):
            # «أ و ب» كاذبة إن كذب أ؛ «أ أو ب» صادقة إن صدق أ
            short_value = node.op == "أو"
            if short_value == jump_if:
                patches = self.condition(node.left, jump_if)
                return patches + self.condition(node.right, jump_if)
            skip = self.condition(node.left, not jump_if)
            patches = self.condition(node.right, jump_if)
            for pos in skip:
                self.patch(pos)
            return patches
        self.expression(node)
        return [self.emit(O.JUMP_IF_TRUE if jump_if else O.JUMP_IF_FALSE, 0, node.line)]

    def stmt_If(self, node):
        to_else = self.condition(node.cond, False)
        self.statement(node.then_branch)
        if node.else_branch is None:
            for pos in to_else:
                self.patch(pos)
            return
        to_end = self.emit(O.JUMP, 0, node.line)
        for pos in to_else:
            self.patch(pos)
        self.statement(node.else_branch)
        self.patch(to_end)

    def stmt_While(self, node):
        fs = self.fs
        start = self.here()
        to_exit = self.condition(node.cond, False)
        loop = Loop(start, len(fs.tries), has_iterator=False)
        fs.loops.append(loop)
        self.block(node.body)
        fs.loops.pop()
        self.emit(O.JUMP, start, node.line)
        for pos in to_exit + loop.breaks:
            self.patch(pos)

    def stmt_ForIn(self, node):
        fs = self.fs
        self.expression(node.iterable)
        self.emit(O.ITER_NEW, 0, node.line)
        start = self.here()
        to_exit = self.emit(O.FOR_ITER, 0, node.line)
        loop = Loop(start, len(fs.tries), has_iterator=True)
        fs.loops.append(loop)
        self.begin_scope(node.line)
        self.emit_decl(self.declare_local(node.name), node.line)
        for statement in node.body.body:
            self.statement(statement)
        self.end_scope()
        fs.loops.pop()
        self.emit(O.JUMP, start, node.line)
        if loop.breaks:                           # «توقف» تترك المكرِّر في المكدس
            for pos in loop.breaks:
                self.patch(pos)
            self.emit(O.POP, 0, node.line)
        self.patch(to_exit)

    def _leave_tries(self, depth, line, pop_handlers):
        """قبل مغادرة كتل «حاول» بقفزة: أزِل مُعالِجاتها وانسخ «أخيرًا»."""
        fs = self.fs
        saved = fs.tries
        for i in range(len(saved) - 1, depth - 1, -1):
            context = saved[i]
            if pop_handlers and context.state in ("body", "catch_fin"):
                self.emit(O.POP_TRY, 0, line)
            if context.finally_body is not None and context.state != "finally":
                fs.tries = saved[:i]
                self.block(context.finally_body)
        fs.tries = saved

    def stmt_Break(self, node):
        loops = self.fs.loops
        if not loops:
            self.raise_error(MISPLACED["break"], node.line)
            return
        self._leave_tries(loops[-1].try_depth, node.line, pop_handlers=True)
        loops[-1].breaks.append(self.emit(O.JUMP, 0, node.line))

    def stmt_Continue(self, node):
        loops = self.fs.loops
        if not loops:
            self.raise_error(MISPLACED["continue"], node.line)
            return
        self._leave_tries(loops[-1].try_depth, node.line, pop_handlers=True)
        self.emit(O.JUMP, loops[-1].continue_target, node.line)

    def stmt_Return(self, node):
        if node.value is None:
            self.emit(O.LOAD_CONST, self.const(None), node.line)
        else:
            self.expression(node.value)
        if self.fs.out.is_script:
            self.raise_error(MISPLACED["return"], node.line)
            return
        self._leave_tries(0, node.line, pop_handlers=False)
        self.emit(O.RETURN, 0, node.line)

    def stmt_Throw(self, node):
        self.expression(node.value)
        self.emit(O.THROW, 0, node.line)

    def stmt_Try(self, node):
        fs = self.fs
        out = fs.out
        line = node.line
        final = node.finally_body
        final_id = fs.finally_count
        fs.finally_count += 1

        handler = len(out.handlers)
        out.handlers.append([-1, -1, final_id])
        catch_handler = None
        self.emit(O.SETUP_TRY, handler, line)
        fs.tries.append(TryContext("body", final))
        self.block(node.body)
        fs.tries.pop()
        self.emit(O.POP_TRY, 0, line)
        to_after = [self.emit(O.JUMP, 0, line)]

        if node.handler is not None:
            out.handlers[handler][0] = self.here()
            self.begin_scope(line)
            if node.error_name:
                self.emit_decl(self.declare_local(node.error_name), line)
            else:
                self.emit(O.POP, 0, line)
            if final is not None:                 # خطأ داخل «امسك» يمرّ بـ«أخيرًا»
                catch_handler = len(out.handlers)
                out.handlers.append([-1, -1, final_id])
                self.emit(O.SETUP_TRY, catch_handler, line)
            fs.tries.append(TryContext("catch_fin" if final is not None else "catch",
                                       final))
            for statement in node.handler.body:
                self.statement(statement)
            fs.tries.pop()
            if final is not None:
                self.emit(O.POP_TRY, 0, line)
            self.end_scope()
            to_after.append(self.emit(O.JUMP, 0, line))

        if final is not None:
            error_path = self.here()
            out.handlers[handler][1] = error_path
            if catch_handler is not None:
                out.handlers[catch_handler][1] = error_path
            fs.tries.append(TryContext("finally", None))
            self.block(final)
            fs.tries.pop()
            self.emit(O.END_FINALLY, final_id, line)
            for pos in to_after:
                self.patch(pos)
            fs.tries.append(TryContext("finally", None))
            self.block(final)
            fs.tries.pop()
        else:
            for pos in to_after:
                self.patch(pos)

        out.handlers[handler] = tuple(out.handlers[handler])
        if catch_handler is not None:
            out.handlers[catch_handler] = tuple(out.handlers[catch_handler])

    # ——————————————— التعابير ———————————————

    def expression(self, node):
        getattr(self, "expr_" + type(node).__name__)(node)

    def expr_Literal(self, node):
        self.emit(O.LOAD_CONST, self.const(node.value), node.line)

    def expr_Identifier(self, node):
        self.load_name(node.name, node.line)

    def expr_This(self, node):
        if self.lookup(THIS) is None:
            self.raise_error("«هذا» لا تُستعمل إلا داخل تابع", node.line)
        else:
            self.load_name(THIS, node.line)

    def expr_Super(self, node):
        if self.lookup(THIS) is None:
            self.raise_error("«الأصل» لا تُستعمل إلا داخل صنف يرث صنفًا آخر", node.line)
            return
        self.load_name(THIS, node.line)
        self.emit(O.SUPER_PROXY, 0, node.line)

    def expr_ListLit(self, node):
        for element in node.elements:
            self.expression(element)
        self.emit(O.BUILD_LIST, len(node.elements), node.line)

    def expr_DictLit(self, node):
        for key, value in node.pairs:
            self.expression(key)
            self.expression(value)
        self.emit(O.BUILD_DICT, len(node.pairs), node.line)

    def expr_FuncExpr(self, node):
        self.function(node.name, node.params, node.body, node.line)

    def expr_Logical(self, node):
        self.expression(node.left)
        jump = O.JUMP_IF_FALSE_KEEP if node.op == "و" else O.JUMP_IF_TRUE_KEEP
        to_end = self.emit(jump, 0, node.line)
        self.emit(O.POP, 0, node.line)
        self.expression(node.right)
        self.patch(to_end)

    def expr_Unary(self, node):
        self.expression(node.operand)
        self.emit({"ليس": O.NOT, "-": O.NEGATE, "+": O.POSITIVE}[node.op], 0, node.line)

    def expr_Binary(self, node):
        self.expression(node.left)
        self.expression(node.right)
        self.emit(O.BINARY, O.BINARY_INDEX[node.op], node.line)

    def expr_Call(self, node):
        self.expression(node.callee)
        for arg in node.args:
            self.expression(arg)
        self.emit(O.CALL, len(node.args), node.line)

    def expr_Index(self, node):
        self.expression(node.obj)
        self.expression(node.key)
        self.emit(O.GET_INDEX, 0, node.line)

    def expr_Slice(self, node):
        self.expression(node.obj)
        mask = 0
        if node.start is not None:
            self.expression(node.start)
            mask |= 1
        if node.end is not None:
            self.expression(node.end)
            mask |= 2
        self.emit(O.GET_SLICE, mask, node.line)

    def expr_Member(self, node):
        self.expression(node.obj)
        self.emit(O.GET_MEMBER, self.name_index(node.name), node.line)


def _strip_noops(fn, seen):
    """يحذف `ENTER_SCOPE` التي لا خلايا في نطاقها، ويُعيد حساب القفزات.

    تُصدَر لكل نطاق داخل حلقة قبل أن يُعرف هل سيُلتقط منه شيء؛ وأغلب النطاقات
    لا يُلتقط منها شيء، وكانت تُكلّف ٥–٨٪ من التعليمات المنفَّذة في الحلقات.
    """
    if id(fn) in seen:
        return
    seen.add(id(fn))
    code, lines = fn.code, fn.lines
    new_code, new_lines, mapping = [], [], {}
    for ip in range(0, len(code), 2):
        mapping[ip] = len(new_code)
        opcode, arg = code[ip], code[ip + 1]
        if opcode == O.ENTER_SCOPE and not fn.scope_cells[arg]:
            continue
        new_code.append(opcode)
        new_code.append(arg)
        new_lines.append(lines[ip >> 1])
    mapping[len(code)] = len(new_code)

    if len(new_code) != len(code):
        for ip in range(0, len(new_code), 2):
            if new_code[ip] in O.JUMPS:
                new_code[ip + 1] = mapping[new_code[ip + 1]]
        fn.entries = [mapping[ip] for ip in fn.entries]
        fn.handlers = [(mapping[c] if c >= 0 else -1, mapping[f] if f >= 0 else -1, i)
                       for c, f, i in fn.handlers]
        fn.code, fn.lines = new_code, new_lines

    for value in fn.consts:
        if isinstance(value, CompiledFunction):
            _strip_noops(value, seen)


def compile_program(program, repl=False):
    return Compiler().compile_program(program, repl=repl)


def compile_source(source, repl=False):
    """نصّ «نون» ← الدالة المُترجَمة للبرنامج."""
    return compile_program(parse(source), repl=repl)
