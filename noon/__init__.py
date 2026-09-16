# -*- coding: utf-8 -*-
"""لغة «نون»: لغة برمجة عربية الصيغة، مُفسَّرة، مكتوبة بـ Python."""

from .errors import NoonError, NoonRuntimeError, NoonSyntaxError, NoonThrow
from .interpreter import Interpreter, run
from .lexer import tokenize
from .parser import parse

__all__ = [
    "Interpreter", "run", "parse", "tokenize",
    "NoonError", "NoonSyntaxError", "NoonRuntimeError", "NoonThrow",
]
__version__ = "1.0.0"
