#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مُشغِّل مباشر: python noon.py ملف.noon"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from noon.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
