# -*- coding: utf-8 -*-
"""عُقد الشجرة النحوية المجرّدة (AST) للغة «نون»."""


class Node:
    _fields = ()

    def __init__(self, *args, **kwargs):
        if len(args) > len(self._fields):
            raise TypeError("%s يقبل %d حقلًا" % (type(self).__name__,
                                                  len(self._fields)))
        for name, value in zip(self._fields, args):
            setattr(self, name, value)
        for name in self._fields[len(args):]:
            setattr(self, name, kwargs.pop(name, None))
        self.line = kwargs.pop("line", 0)
        if kwargs:
            raise TypeError("حقول غير معروفة: %s" % ", ".join(kwargs))

    def __repr__(self):
        inner = ", ".join("%s=%r" % (f, getattr(self, f)) for f in self._fields)
        return "%s(%s)" % (type(self).__name__, inner)


# ——————————— الجُمل ———————————

class Program(Node):
    _fields = ("body",)


class Block(Node):
    _fields = ("body",)


class VarDecl(Node):
    _fields = ("name", "value", "constant")


class Assign(Node):
    _fields = ("target", "op", "value")


class ExprStmt(Node):
    _fields = ("expr",)


class If(Node):
    _fields = ("cond", "then_branch", "else_branch")


class While(Node):
    _fields = ("cond", "body")


class ForIn(Node):
    _fields = ("name", "iterable", "body")


class FuncDecl(Node):
    _fields = ("name", "params", "body")


class Return(Node):
    _fields = ("value",)


class Break(Node):
    _fields = ()


class Continue(Node):
    _fields = ()


class ClassDecl(Node):
    _fields = ("name", "parent", "methods")


class Try(Node):
    _fields = ("body", "error_name", "handler", "finally_body")


class Throw(Node):
    _fields = ("value",)


# ——————————— التعابير ———————————

class Literal(Node):
    _fields = ("value",)


class ListLit(Node):
    _fields = ("elements",)


class DictLit(Node):
    _fields = ("pairs",)


class Identifier(Node):
    _fields = ("name",)


class This(Node):
    _fields = ()


class Super(Node):
    _fields = ()


class Unary(Node):
    _fields = ("op", "operand")


class Binary(Node):
    _fields = ("op", "left", "right")


class Logical(Node):
    _fields = ("op", "left", "right")


class Call(Node):
    _fields = ("callee", "args")


class Index(Node):
    _fields = ("obj", "key")


class Slice(Node):
    _fields = ("obj", "start", "end")


class Member(Node):
    _fields = ("obj", "name")


class FuncExpr(Node):
    _fields = ("name", "params", "body")
