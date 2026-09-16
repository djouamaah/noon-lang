# -*- coding: utf-8 -*-
"""قياس سرعة المحرّكين على برامج نموذجية.

    python tools/benchmark.py            # كل البرامج، ٥ مرّات لكل محرّك
    python tools/benchmark.py -n 3

يُطبع أفضل زمن لكل محرّك (الأفضل لا المتوسط: الضجيج يُبطئ ولا يُسرّع)، ويُتحقَّق
أن ناتج المحرّكين واحد قبل الوثوق بالأرقام.
"""

import argparse
import io
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from noon.compiler import compile_source  # noqa: E402
from noon.interpreter import Interpreter  # noqa: E402
from noon.vm import VM  # noqa: E402

PROGRAMS = {
    "تعاود (فيبوناتشي ٢٢)": """
دالة فيبو(ن) { إذا (ن < ٢) { أرجع ن } أرجع فيبو(ن - ١) + فيبو(ن - ٢) }
اطبع(فيبو(٢٢))
""",
    "حلقات وحساب": """
متغير مجموع_ = ٠
متغير ع = ٠
طالما (ع < ٢٠٠٠٠٠) {
    إذا (ع % ٣ == ٠ أو ع % ٥ == ٠) { مجموع_ += ع }
    ع += ١
}
اطبع(مجموع_)
""",
    "غربال الأعداد الأوّلية": """
دالة غربال(حد) {
    متغير علامات = [صحيح] * (حد + ١)
    متغير ن = ٢
    طالما (ن * ن <= حد) {
        إذا (علامات[ن]) {
            متغير م = ن * ن
            طالما (م <= حد) { علامات[م] = خطأ
                              م += ن }
        }
        ن += ١
    }
    متغير عدد_ = ٠
    لكل ك في مدى(٢، حد + ١) { إذا (علامات[ك]) { عدد_ += ١ } }
    أرجع عدد_
}
اطبع(غربال(٦٠٠٠٠))
""",
    "أصناف وتوابع": """
صنف متّجه {
    تهيئة(س، ص) { هذا.س = س
                  هذا.ص = ص }
    جمع(آخر) { أرجع متّجه(هذا.س + آخر.س، هذا.ص + آخر.ص) }
}
متغير م = متّجه(٠، ٠)
لكل ن في مدى(٢٠٠٠٠) { م = م.جمع(متّجه(ن، ١)) }
اطبع(م.س، م.ص)
""",
    "إغلاق ودوال عليا": """
دالة صانع(ك) { أرجع دالة(س) { أرجع س * ك + ١ } }
متغير د = صانع(٣)
متغير ق = مدى(٣٠٠٠٠)
اطبع(مجموع(طبّق(د، رشّح(دالة(س) { أرجع س % ٢ == ٠ }، ق))))
""",
}


def best_times(runners, source, repeat):
    """أفضل زمن لكل محرّك، بالتناوب بينهما في كل جولة.

    القياس المتتابع (المحرّك الأول كلّه ثم الثاني) يحمّل أحدهما تقلّبَ حِمل
    الجهاز؛ التناوب يوزّعه عليهما بالتساوي.
    """
    best = [float("inf")] * len(runners)
    outputs = [None] * len(runners)
    for _ in range(repeat):
        for i, make_runner in enumerate(runners):
            buffer = io.StringIO()
            runner = make_runner(buffer)
            start = time.perf_counter()
            runner(source)
            best[i] = min(best[i], time.perf_counter() - start)
            outputs[i] = buffer.getvalue()
    return best, outputs


def main(argv=None):
    parser = argparse.ArgumentParser(description="قياس سرعة محرّكَي «نون»")
    parser.add_argument("-n", "--repeat", type=int, default=5)
    args = parser.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    sys.setrecursionlimit(20000)

    print("%-26s %12s %12s %12s %8s" % ("البرنامج", "المُفسِّر", "الآلة", "الترجمة", "التسريع"))
    ratios = []
    for name, source in PROGRAMS.items():
        (tree, vm), (tree_out, vm_out) = best_times(
            [lambda out: Interpreter(out=out).run, lambda out: VM(out=out).run],
            source, args.repeat)
        if tree_out != vm_out:
            raise SystemExit("المحرّكان اختلفا في «%s»: %r ≠ %r" % (name, tree_out, vm_out))
        start = time.perf_counter()
        compile_source(source)
        compile_ms = (time.perf_counter() - start) * 1000
        ratios.append(tree / vm)
        print("%-26s %10.1f م.ث %10.1f م.ث %9.2f م.ث %7.1f×" % (
            name, tree * 1000, vm * 1000, compile_ms, tree / vm))

    geometric = 1.0
    for ratio in ratios:
        geometric *= ratio
    geometric **= 1.0 / len(ratios)
    print("\nمتوسّط التسريع (هندسي): %.1f×  ·  Python %s" % (
        geometric, sys.version.split()[0]))


if __name__ == "__main__":
    main()
