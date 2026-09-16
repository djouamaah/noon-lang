# -*- coding: utf-8 -*-
"""المُحلِّل النحوي: يبني الشجرة النحوية من الرموز.

مُحلِّل نزولي تعاودي (recursive descent) بأسبقيات صريحة:

    أو  <  و  <  المساواة  <  المقارنة  <  الجمع  <  الضرب  <
    الأحادي  <  الأُسّ  <  الاستدعاء/الفهرسة/العضو  <  الأوّلي
"""

from . import ast_nodes as A
from .errors import NoonSyntaxError
from .lexer import tokenize

_ASSIGN_OPS = {
    "ASSIGN": None, "PLUS_EQ": "+", "MINUS_EQ": "-",
    "STAR_EQ": "*", "SLASH_EQ": "/",
}

_EQUALITY = {"EQ": "==", "NE": "!="}
_COMPARISON = {"LT": "<", "GT": ">", "LE": "<=", "GE": ">=", "IN": "في"}
_TERM = {"PLUS": "+", "MINUS": "-"}
_FACTOR = {"STAR": "*", "SLASH": "/", "PERCENT": "%", "DSLASH": "//"}

# أسماء الرموز بالعربية في رسائل الخطأ
_NAMES = {
    "NEWLINE": "نهاية سطر", "EOF": "نهاية الملف", "IDENT": "اسم",
    "NUMBER": "عدد", "STRING": "نص", "LPAREN": "(", "RPAREN": ")",
    "LBRACE": "{", "RBRACE": "}", "LBRACKET": "[", "RBRACKET": "]",
    "COMMA": "فاصلة", "COLON": "نقطتان", "ASSIGN": "=",
}


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    # ——— أدوات ———
    @property
    def current(self):
        return self.tokens[self.pos]

    def peek(self, offset=0):
        j = min(self.pos + offset, len(self.tokens) - 1)
        return self.tokens[j]

    def check(self, *types):
        return self.current.type in types

    def advance(self):
        token = self.current
        if token.type != "EOF":
            self.pos += 1
        return token

    def match(self, *types):
        if self.check(*types):
            return self.advance()
        return None

    def expect(self, type_, what=None):
        if self.check(type_):
            return self.advance()
        expected = what or _NAMES.get(type_, type_)
        found = self._describe(self.current)
        raise NoonSyntaxError("توقّعت %s ولكن وجدت %s" % (expected, found),
                              self.current.line, self.current.col)

    @staticmethod
    def _describe(token):
        if token.type == "EOF":
            return "نهاية الملف"
        if token.type == "NEWLINE":
            return "نهاية السطر"
        return "«%s»" % token.value

    def skip_newlines(self):
        while self.check("NEWLINE"):
            self.advance()

    def end_statement(self):
        if self.check("EOF") or self.check("RBRACE"):
            return
        if self.match("NEWLINE"):
            return
        raise NoonSyntaxError(
            "توقّعت نهاية الجملة ولكن وجدت %s" % self._describe(self.current),
            self.current.line, self.current.col)

    # ——— البرنامج ———
    def parse(self):
        body = []
        self.skip_newlines()
        while not self.check("EOF"):
            body.append(self.statement())
            self.skip_newlines()
        return A.Program(body, line=1)

    def block(self):
        """كتلة بين قوسين معقوفين."""
        self.skip_newlines()
        brace = self.expect("LBRACE", "«{»")
        body = []
        self.skip_newlines()
        while not self.check("RBRACE"):
            if self.check("EOF"):
                raise NoonSyntaxError("كتلة لم تُغلق بـ«}»", brace.line, brace.col)
            body.append(self.statement())
            self.skip_newlines()
        self.expect("RBRACE", "«}»")
        return A.Block(body, line=brace.line)

    # ——— الجُمل ———
    def statement(self):
        token = self.current
        if token.type in ("VAR", "CONST"):
            return self.var_decl()
        if token.type == "IF":
            return self.if_stmt()
        if token.type == "WHILE":
            return self.while_stmt()
        if token.type == "FOR":
            return self.for_stmt()
        if token.type == "FUNC" and self.peek(1).type == "IDENT":
            return self.func_decl()
        if token.type == "CLASS":
            return self.class_decl()
        if token.type == "RETURN":
            return self.return_stmt()
        if token.type == "TRY":
            return self.try_stmt()
        if token.type == "THROW":
            self.advance()
            value = self.expression()
            self.end_statement()
            return A.Throw(value, line=token.line)
        if token.type == "BREAK":
            self.advance()
            self.end_statement()
            return A.Break(line=token.line)
        if token.type == "CONTINUE":
            self.advance()
            self.end_statement()
            return A.Continue(line=token.line)
        if token.type == "LBRACE" and not self.looks_like_dict():
            return self.block()
        return self.expr_statement()

    def looks_like_dict(self):
        """هل «{» التي في أوّل الجملة بداية قاموس لا بداية كتلة؟

        القاموس يبدأ بـ«مفتاح:»، أما الكتلة فلا.
        """
        offset = 1
        while self.peek(offset).type == "NEWLINE":
            offset += 1
        if self.peek(offset).type not in ("STRING", "NUMBER", "IDENT"):
            return False
        return self.peek(offset + 1).type == "COLON"

    def var_decl(self):
        token = self.advance()
        name = self.expect("IDENT", "اسم متغير").value
        value = None
        if self.match("ASSIGN"):
            self.skip_newlines()
            value = self.expression()
        elif token.type == "CONST":
            raise NoonSyntaxError("الثابت «%s» يجب أن تُسند إليه قيمة" % name,
                                  token.line, token.col)
        self.end_statement()
        return A.VarDecl(name, value, token.type == "CONST", line=token.line)

    def if_stmt(self):
        token = self.advance()
        cond = self.condition()
        then_branch = self.block()
        else_branch = None
        save = self.pos
        self.skip_newlines()
        if self.match("ELSE"):
            if self.check("IF"):
                else_branch = self.if_stmt()
            else:
                else_branch = self.block()
        else:
            self.pos = save
        return A.If(cond, then_branch, else_branch, line=token.line)

    def while_stmt(self):
        token = self.advance()
        cond = self.condition()
        body = self.block()
        return A.While(cond, body, line=token.line)

    def for_stmt(self):
        token = self.advance()
        paren = bool(self.match("LPAREN"))
        name = self.expect("IDENT", "اسم متغير الحلقة").value
        self.expect("IN", "«في»")
        iterable = self.expression()
        if paren:
            self.expect("RPAREN", "«)»")
        body = self.block()
        return A.ForIn(name, iterable, body, line=token.line)

    def condition(self):
        """الشرط: الأقواس حوله اختيارية."""
        if self.match("LPAREN"):
            self.skip_newlines()
            expr = self.expression()
            self.skip_newlines()
            self.expect("RPAREN", "«)»")
            return expr
        return self.expression()

    def params(self):
        self.expect("LPAREN", "«(»")
        params = []
        self.skip_newlines()
        if not self.check("RPAREN"):
            while True:
                self.skip_newlines()
                name = self.expect("IDENT", "اسم وسيط").value
                default = None
                if self.match("ASSIGN"):
                    default = self.expression()
                params.append((name, default))
                self.skip_newlines()
                if not self.match("COMMA"):
                    break
        self.skip_newlines()
        self.expect("RPAREN", "«)»")
        return params

    def func_decl(self):
        token = self.advance()
        name = self.expect("IDENT", "اسم الدالة").value
        params = self.params()
        body = self.block()
        return A.FuncDecl(name, params, body, line=token.line)

    def class_decl(self):
        token = self.advance()
        name = self.expect("IDENT", "اسم الصنف").value
        parent = None
        if self.match("EXTENDS"):
            parent = self.expect("IDENT", "اسم الصنف الأب").value
        self.skip_newlines()
        brace = self.expect("LBRACE", "«{»")
        methods = []
        self.skip_newlines()
        while not self.check("RBRACE"):
            if self.check("EOF"):
                raise NoonSyntaxError("جسم الصنف لم يُغلق بـ«}»", brace.line, brace.col)
            self.match("FUNC")          # كلمة «دالة» اختيارية داخل الصنف
            m_token = self.current
            m_name = self.expect("IDENT", "اسم تابع").value
            m_params = self.params()
            m_body = self.block()
            methods.append(A.FuncDecl(m_name, m_params, m_body, line=m_token.line))
            self.skip_newlines()
        self.expect("RBRACE", "«}»")
        return A.ClassDecl(name, parent, methods, line=token.line)

    def return_stmt(self):
        token = self.advance()
        value = None
        if not self.check("NEWLINE", "RBRACE", "EOF"):
            value = self.expression()
        self.end_statement()
        return A.Return(value, line=token.line)

    def try_stmt(self):
        token = self.advance()
        body = self.block()
        error_name, handler, finally_body = None, None, None
        save = self.pos
        self.skip_newlines()
        if self.match("CATCH"):
            if self.match("LPAREN"):
                error_name = self.expect("IDENT", "اسم متغير الخطأ").value
                self.expect("RPAREN", "«)»")
            elif self.check("IDENT"):
                error_name = self.advance().value
            handler = self.block()
            save = self.pos
            self.skip_newlines()
        if self.match("FINALLY"):
            finally_body = self.block()
        else:
            self.pos = save
        if handler is None and finally_body is None:
            raise NoonSyntaxError("«حاول» يحتاج إلى «امسك» أو «أخيرًا»",
                                  token.line, token.col)
        return A.Try(body, error_name, handler, finally_body, line=token.line)

    def expr_statement(self):
        token = self.current
        expr = self.expression()
        op_token = self.current
        if op_token.type in _ASSIGN_OPS:
            self.advance()
            self.skip_newlines()
            value = self.expression()
            if not isinstance(expr, (A.Identifier, A.Index, A.Member)):
                raise NoonSyntaxError("لا يمكن الإسناد إلى هذا التعبير",
                                      op_token.line, op_token.col)
            self.end_statement()
            return A.Assign(expr, _ASSIGN_OPS[op_token.type], value,
                            line=op_token.line)
        self.end_statement()
        return A.ExprStmt(expr, line=token.line)

    # ——— التعابير ———
    def expression(self):
        return self.logic_or()

    def logic_or(self):
        expr = self.logic_and()
        while self.check("OR"):
            token = self.advance()
            self.skip_newlines()
            expr = A.Logical("أو", expr, self.logic_and(), line=token.line)
        return expr

    def logic_and(self):
        expr = self.equality()
        while self.check("AND"):
            token = self.advance()
            self.skip_newlines()
            expr = A.Logical("و", expr, self.equality(), line=token.line)
        return expr

    def equality(self):
        expr = self.comparison()
        while self.current.type in _EQUALITY:
            token = self.advance()
            expr = A.Binary(_EQUALITY[token.type], expr, self.comparison(),
                            line=token.line)
        return expr

    def comparison(self):
        expr = self.term()
        while self.current.type in _COMPARISON:
            token = self.advance()
            expr = A.Binary(_COMPARISON[token.type], expr, self.term(),
                            line=token.line)
        return expr

    def term(self):
        expr = self.factor()
        while self.current.type in _TERM:
            token = self.advance()
            expr = A.Binary(_TERM[token.type], expr, self.factor(), line=token.line)
        return expr

    def factor(self):
        expr = self.unary()
        while self.current.type in _FACTOR:
            token = self.advance()
            expr = A.Binary(_FACTOR[token.type], expr, self.unary(), line=token.line)
        return expr

    def unary(self):
        if self.check("NOT", "MINUS", "PLUS"):
            token = self.advance()
            op = {"NOT": "ليس", "MINUS": "-", "PLUS": "+"}[token.type]
            return A.Unary(op, self.unary(), line=token.line)
        return self.power()

    def power(self):
        expr = self.call_chain()
        if self.check("POW"):
            token = self.advance()
            return A.Binary("**", expr, self.unary(), line=token.line)  # يمين-تجميعي
        return expr

    def call_chain(self):
        expr = self.primary()
        while True:
            if self.check("LPAREN"):
                token = self.advance()
                args = self.arguments()
                expr = A.Call(expr, args, line=token.line)
            elif self.check("LBRACKET"):
                token = self.advance()
                self.skip_newlines()
                start = None if self.check("COLON") else self.expression()
                if self.match("COLON"):
                    end = None if self.check("RBRACKET") else self.expression()
                    expr = A.Slice(expr, start, end, line=token.line)
                else:
                    expr = A.Index(expr, start, line=token.line)
                self.skip_newlines()
                self.expect("RBRACKET", "«]»")
            elif self.check("DOT"):
                token = self.advance()
                name = self.expect("IDENT", "اسم عضو").value
                expr = A.Member(expr, name, line=token.line)
            else:
                return expr

    def arguments(self):
        args = []
        self.skip_newlines()
        if not self.check("RPAREN"):
            while True:
                self.skip_newlines()
                args.append(self.expression())
                self.skip_newlines()
                if not self.match("COMMA"):
                    break
        self.skip_newlines()
        self.expect("RPAREN", "«)»")
        return args

    def primary(self):
        token = self.current

        if token.type == "NUMBER" or token.type == "STRING":
            self.advance()
            return A.Literal(token.value, line=token.line)
        if token.type == "TRUE":
            self.advance()
            return A.Literal(True, line=token.line)
        if token.type == "FALSE":
            self.advance()
            return A.Literal(False, line=token.line)
        if token.type == "NULL":
            self.advance()
            return A.Literal(None, line=token.line)
        if token.type == "IDENT":
            self.advance()
            return A.Identifier(token.value, line=token.line)
        if token.type == "THIS":
            self.advance()
            return A.This(line=token.line)
        if token.type == "SUPER":
            self.advance()
            return A.Super(line=token.line)
        if token.type == "FUNC":
            self.advance()
            name = self.advance().value if self.check("IDENT") else None
            params = self.params()
            body = self.block()
            return A.FuncExpr(name, params, body, line=token.line)
        if token.type == "LPAREN":
            self.advance()
            self.skip_newlines()
            expr = self.expression()
            self.skip_newlines()
            self.expect("RPAREN", "«)»")
            return expr
        if token.type == "LBRACKET":
            self.advance()
            elements = []
            self.skip_newlines()
            if not self.check("RBRACKET"):
                while True:
                    self.skip_newlines()
                    if self.check("RBRACKET"):      # فاصلة زائدة في النهاية
                        break
                    elements.append(self.expression())
                    self.skip_newlines()
                    if not self.match("COMMA"):
                        break
            self.skip_newlines()
            self.expect("RBRACKET", "«]»")
            return A.ListLit(elements, line=token.line)
        if token.type == "LBRACE":
            self.advance()
            pairs = []
            self.skip_newlines()
            if not self.check("RBRACE"):
                while True:
                    self.skip_newlines()
                    if self.check("RBRACE"):
                        break
                    key = self.expression()
                    self.expect("COLON", "«:»")
                    self.skip_newlines()
                    pairs.append((key, self.expression()))
                    self.skip_newlines()
                    if not self.match("COMMA"):
                        break
            self.skip_newlines()
            self.expect("RBRACE", "«}»")
            return A.DictLit(pairs, line=token.line)

        raise NoonSyntaxError("تعبير غير متوقّع: %s" % self._describe(token),
                              token.line, token.col)


def parse(source):
    return Parser(tokenize(source)).parse()
