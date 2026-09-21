# -*- coding: utf-8 -*-
"""لغة «نون»: لغة برمجة عربية الصيغة، مُفسَّرة، مكتوبة بـ Python."""

from .compiler import compile_source
from .errors import NoonError, NoonRuntimeError, NoonSyntaxError, NoonThrow
from .interpreter import Interpreter, run
from .lexer import tokenize
from .parser import parse
from .vm import VM

__all__ = [
    "VM", "Interpreter", "compile_source", "run", "parse", "tokenize",
    "NoonError", "NoonSyntaxError", "NoonRuntimeError", "NoonThrow",
]
__version__ = "1.2.0"
