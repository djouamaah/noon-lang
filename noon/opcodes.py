# -*- coding: utf-8 -*-
"""تعليمات البايت-كود.

كل تعليمة عددان: الرمز ثم وسيطه (صفر إن لم يكن له معنى)، فالقراءة موحّدة
وسريعة: `op = code[ip]; arg = code[ip + 1]; ip += 2`.
القفزات مطلقة إلى موضع في `code`.

الأرقام جزء من صيغة ملفات ‎.noonc: لا تُعَد ترقيمها، وأضِف الجديد في آخرها
وارفع `bytecode.FORMAT_VERSION`.
"""

(
    LOAD_CONST,           # ادفع ثابتًا
    LOAD_LOCAL,           # ادفع خانة محلّية
    STORE_LOCAL,          # خزّن في خانة محلّية (يستهلك)
    LOAD_CELL,            # محلّي التقطته دالة داخلية: القيمة داخل خليّة
    STORE_CELL,
    INIT_CELL,            # تصريح بمحلّي مُلتقَط: يملأ خليّة جديدة أو مُعَدّة سلفًا
    LOAD_FREE,            # متغيّر من دالة محيطة، عبر خلايا الإغلاق
    STORE_FREE,
    LOAD_GLOBAL,          # الوسيط: فهرس الاسم
    STORE_GLOBAL,
    DEFINE_GLOBAL,        # «متغير» في المستوى الأعلى: خطأ إن سبق تعريفه
    DEFINE_GLOBAL_CONST,  # «ثابت» في المستوى الأعلى
    DEFINE_GLOBAL_FORCE,  # «دالة» و«صنف» في المستوى الأعلى: تستبدل بلا اعتراض
    POP,
    SWAP,
    BINARY,               # الوسيط: فهرس العملية في BINARY_OPS
    NEGATE,
    POSITIVE,
    NOT,
    JUMP,
    JUMP_IF_FALSE,        # يستهلك القيمة
    JUMP_IF_FALSE_KEEP,   # يُبقيها إن قفز (لـ«و»)
    JUMP_IF_TRUE_KEEP,    # يُبقيها إن قفز (لـ«أو»)
    CALL,                 # الوسيط: عدد الوسائط
    RETURN,
    MAKE_CLOSURE,         # الوسيط: فهرس الدالة في الثوابت
    BUILD_LIST,           # الوسيط: عدد العناصر
    BUILD_DICT,           # الوسيط: عدد الأزواج
    BUILD_CLASS,          # الوسيط: عدد التوابع × ٢ + (١ إن كان له أب)
    GET_INDEX,
    SET_INDEX,            # المكدس: قيمة، كائن، مفتاح
    GET_SLICE,            # الوسيط: ١ إن وُجدت البداية + ٢ إن وُجدت النهاية
    GET_MEMBER,           # الوسيط: فهرس الاسم
    SET_MEMBER,           # المكدس: قيمة، كائن
    SUPER_PROXY,          # «الأصل»: يستهلك «هذا»
    ITER_NEW,
    FOR_ITER,             # الوسيط: موضع الخروج عند النفاد
    THROW,
    SETUP_TRY,            # الوسيط: فهرس المُعالِج في جدول الدالة
    POP_TRY,
    END_FINALLY,          # الوسيط: رقم «أخيرًا»؛ يُعيد رمي الخطأ المعلَّق إن وُجد
    ENTER_SCOPE,          # الوسيط: رقم النطاق؛ يُفرغ خلاياه لدورة جديدة
    RAISE_ERROR,          # الوسيط: فهرس رسالة الخطأ في الثوابت
    JUMP_IF_TRUE,         # يستهلك القيمة (شروط «إذا» و«طالما» المركّبة)
) = range(44)

JUMPS = frozenset([JUMP, JUMP_IF_FALSE, JUMP_IF_TRUE, JUMP_IF_FALSE_KEEP,
                   JUMP_IF_TRUE_KEEP, FOR_ITER])

BINARY_OPS = ["+", "-", "*", "/", "//", "%", "**",
              "==", "!=", "<", ">", "<=", ">=", "في"]
BINARY_INDEX = {op: i for i, op in enumerate(BINARY_OPS)}

# أسماء عربية للعرض في مُفكِّك التجميع
NAMES = {
    LOAD_CONST: "ادفع_ثابتًا",
    LOAD_LOCAL: "ادفع_محلّيًّا",
    STORE_LOCAL: "خزّن_محلّيًّا",
    LOAD_CELL: "ادفع_خليّة",
    STORE_CELL: "خزّن_خليّة",
    INIT_CELL: "هيّئ_خليّة",
    LOAD_FREE: "ادفع_حرًّا",
    STORE_FREE: "خزّن_حرًّا",
    LOAD_GLOBAL: "ادفع_عامًّا",
    STORE_GLOBAL: "خزّن_عامًّا",
    DEFINE_GLOBAL: "عرّف_عامًّا",
    DEFINE_GLOBAL_CONST: "عرّف_ثابتًا",
    DEFINE_GLOBAL_FORCE: "عرّف_مستبدلًا",
    POP: "أسقط",
    SWAP: "بادل",
    BINARY: "عملية",
    NEGATE: "سالب",
    POSITIVE: "موجب",
    NOT: "ليس",
    JUMP: "اقفز",
    JUMP_IF_FALSE: "اقفز_إن_كذب",
    JUMP_IF_FALSE_KEEP: "اقفز_إن_كذب_مُبقيًا",
    JUMP_IF_TRUE_KEEP: "اقفز_إن_صدق_مُبقيًا",
    CALL: "نادِ",
    RETURN: "أرجع",
    MAKE_CLOSURE: "اصنع_دالة",
    BUILD_LIST: "ابنِ_قائمة",
    BUILD_DICT: "ابنِ_قاموسًا",
    BUILD_CLASS: "ابنِ_صنفًا",
    GET_INDEX: "اجلب_بالفهرس",
    SET_INDEX: "ضع_بالفهرس",
    GET_SLICE: "اقتطع",
    GET_MEMBER: "اجلب_عضوًا",
    SET_MEMBER: "ضع_عضوًا",
    SUPER_PROXY: "الأصل",
    ITER_NEW: "ابدأ_التكرار",
    FOR_ITER: "التالي_أو_اقفز",
    THROW: "ارمِ",
    SETUP_TRY: "هيّئ_المحاولة",
    POP_TRY: "أنهِ_المحاولة",
    END_FINALLY: "نهاية_أخيرًا",
    ENTER_SCOPE: "ادخل_نطاقًا",
    RAISE_ERROR: "ارمِ_خطأ",
    JUMP_IF_TRUE: "اقفز_إن_صدق",
}

assert len(NAMES) == 44, "لكل تعليمة اسم عربي"
