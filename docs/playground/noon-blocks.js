// كتل «نون»: الكتل الخاصّة باللغة، ومترجِم الكتل إلى شيفرة «نون»، وصندوق الأدوات.
//
// الكتل المدمجة في Blockly (الشروط والحلقات والمتغيّرات والدوال…) تُستعمل كما هي،
// بعناوين عربية من مفردات «نون»؛ وما يخصّ اللغة (اطبع، اقرأ، مكتبة رياضيات…)
// كتلٌ معرَّفة هنا. والشيفرة الناتجة «نون» عادية: تُقرأ وتُنسخ إلى ساحة التجربة.

import LANGUAGE from "./language.js";
import { normalize } from "./normalize.js";

// الأسبقية كما في noon/parser.py: الأصغر أشدّ ارتباطًا
export const ORDER = {
  ATOMIC: 0, POSTFIX: 1, POWER: 2, UNARY: 3, MULTIPLICATIVE: 4, ADDITIVE: 5,
  RELATIONAL: 6, EQUALITY: 7, AND: 8, OR: 9, NONE: 99,
};
const POSTFIX_OPERAND = 1.5;     // ما قبل ( أو [ أو . : يُقوَّس إلا الذرّي واللاحق
const POWER_RIGHT = 3.5;         // يمين ** يقبل الأحادي والأسّ بلا أقواس

const KEYWORDS = new Set(Object.keys(LANGUAGE.keywords));
const BUILTINS = new Set([...LANGUAGE.builtins, ...LANGUAGE.constants]);
const MATH_MODULE = "رياضيات";
const COMMA = "، ";

// ——— الأسماء ———

// اسم يكتبه المستخدم ← معرّف «نون» صالح: المسافات «_»، ولا كلمة مفتاحية ولا دالة مدمجة
export function noonName(raw) {
  let name = String(raw ?? "").trim()
    .replace(/[\s\-]+/gu, "_")
    .replace(/[^\p{L}\p{M}\p{N}_]/gu, "");
  if (!name) name = "س";
  if (/^\p{N}/u.test(name)) name = "_" + name;
  if (KEYWORDS.has(normalize(name)) || BUILTINS.has(name) || name === MATH_MODULE) name += "_";
  return name;
}

// وسائط كتلة تعريف دالة، بأسماء «نون»
function params(block) {
  return block.getProcedureDef()[1].map(noonName);
}

function variableName(block, field = "VAR") {
  const model = block.getField(field)?.getVariable?.();
  return noonName(model ? (model.getName ? model.getName() : model.name) : block.getFieldValue(field));
}

export function quote(text) {
  return '"' + String(text)
    .replace(/\\/g, "\\\\").replace(/"/g, '\\"')
    .replace(/\r?\n/g, "\\n").replace(/\t/g, "\\t") + '"';
}

// ——— الكتل الخاصّة بـ«نون» ———

const CUSTOM_BLOCKS = [
  {
    type: "noon_print", message0: "اطبع %1",
    args0: [{ type: "input_value", name: "VALUE" }],
    previousStatement: null, nextStatement: null, style: "io_blocks",
    tooltip: "يطبع القيمة ثم ينتقل إلى سطر جديد.",
  },
  {
    type: "noon_print2", message0: "اطبع %1 %2",
    args0: [{ type: "input_value", name: "A" }, { type: "input_value", name: "B" }],
    inputsInline: true, previousStatement: null, nextStatement: null, style: "io_blocks",
    tooltip: "يطبع القيمتين بينهما مسافة.",
  },
  {
    type: "noon_input", message0: "اقرأ %1 بعد عرض %2",
    args0: [
      { type: "field_dropdown", name: "TYPE", options: [["نصًّا", "TEXT"], ["عددًا", "NUMBER"]] },
      { type: "input_value", name: "PROMPT", check: "String" },
    ],
    output: null, style: "io_blocks",
    tooltip: "يقرأ سطرًا من لسان «الدخل». اترك الرسالة فارغة إن لم تُرد عرض شيء.",
  },
  {
    type: "noon_math_single", message0: "%1 %2",
    args0: [
      { type: "field_dropdown", name: "OP", options: [
        ["الجذر التربيعي لـ", "جذر"], ["القيمة المطلقة لـ", "مطلق"],
        ["تقريب", "تقريب"], ["أرضية", "أرضية"], ["سقف", "سقف"]] },
      { type: "input_value", name: "NUM", check: "Number" },
    ],
    output: "Number", style: "math_blocks",
  },
  {
    type: "noon_convert", message0: "%1 %2",
    args0: [
      { type: "field_dropdown", name: "OP", options: [
        ["نصًّا من", "نص"], ["عددًا من", "عدد"], ["نوع", "نوع"]] },
      { type: "input_value", name: "VALUE" },
    ],
    output: null, style: "text_blocks",
    tooltip: "«نوع» يُرجع اسم نوع القيمة: عدد، نص، قائمة…",
  },
  {
    type: "noon_contains", message0: "%1 يحتوي %2",
    args0: [{ type: "input_value", name: "CONTAINER" }, { type: "input_value", name: "ITEM" }],
    inputsInline: true, output: "Boolean", style: "logic_blocks",
    tooltip: "هل في القائمة هذا العنصر؟ أو في النص هذا المقطع؟",
  },
  {
    type: "noon_range", message0: "الأعداد من %1 إلى %2",
    args0: [
      { type: "input_value", name: "FROM", check: "Number" },
      { type: "input_value", name: "TO", check: "Number" },
    ],
    inputsInline: true, output: "Array", style: "list_blocks",
    tooltip: "قائمة الأعداد الصحيحة بين الحدّين، شاملةً الحدّين.",
  },
  {
    type: "noon_list_get", message0: "العنصر رقم %1 من %2",
    args0: [
      { type: "input_value", name: "INDEX", check: "Number" },
      { type: "input_value", name: "LIST", check: "Array" },
    ],
    inputsInline: true, output: null, style: "list_blocks",
    tooltip: "العدّ يبدأ من ١: العنصر رقم ١ هو الأوّل.",
  },
  {
    type: "noon_list_set", message0: "اجعل العنصر رقم %1 من %2 = %3",
    args0: [
      { type: "input_value", name: "INDEX", check: "Number" },
      { type: "input_value", name: "LIST", check: "Array" },
      { type: "input_value", name: "VALUE" },
    ],
    inputsInline: true, previousStatement: null, nextStatement: null, style: "list_blocks",
    tooltip: "العدّ يبدأ من ١: العنصر رقم ١ هو الأوّل.",
  },
  {
    type: "noon_list_append", message0: "أضف %1 إلى القائمة %2",
    args0: [{ type: "input_value", name: "VALUE" }, { type: "input_value", name: "LIST", check: "Array" }],
    inputsInline: true, previousStatement: null, nextStatement: null, style: "list_blocks",
  },
  {
    type: "noon_list_math", message0: "%1 %2",
    args0: [
      { type: "field_dropdown", name: "OP", options: [
        ["مجموع", "مجموع"], ["أكبر قيمة في", "أقصى"], ["أصغر قيمة في", "أدنى"]] },
      { type: "input_value", name: "LIST", check: "Array" },
    ],
    output: "Number", style: "list_blocks",
  },
  {
    type: "noon_lib1", message0: "رياضيات: %1 %2",
    args0: [
      { type: "field_dropdown", name: "FUNC", options: [
        ["عاملي", "عاملي"], ["فيبوناتشي رقم", "فيبوناتشي"], ["أوّلي؟", "أولي"],
        ["الأعداد الأولية حتى", "الأعداد_الأولية"], ["العوامل الأولية لـ", "عوامل_أولية"],
        ["الجذر الصحيح لـ", "جذر_صحيح"]] },
      { type: "input_value", name: "N", check: "Number" },
    ],
    output: null, style: "library_blocks",
    tooltip: "من وحدة «رياضيات» في مكتبة «نون» القياسية.",
  },
  {
    type: "noon_lib2", message0: "رياضيات: %1 %2 و %3",
    args0: [
      { type: "field_dropdown", name: "FUNC", options: [
        ["القاسم المشترك الأكبر لـ", "قاسم_مشترك"], ["المضاعف المشترك الأصغر لـ", "مضاعف_مشترك"],
        ["توافيق", "توافيق"], ["تباديل", "تباديل"]] },
      { type: "input_value", name: "A", check: "Number" },
      { type: "input_value", name: "B", check: "Number" },
    ],
    inputsInline: true, output: "Number", style: "library_blocks",
    tooltip: "من وحدة «رياضيات» في مكتبة «نون» القياسية.",
  },
  {
    type: "noon_lib_stats", message0: "رياضيات: %1 القائمة %2",
    args0: [
      { type: "field_dropdown", name: "FUNC", options: [
        ["متوسط", "متوسط"], ["وسيط", "وسيط"], ["منوال", "منوال"],
        ["تباين", "تباين"], ["الانحراف المعياري لـ", "انحراف_معياري"]] },
      { type: "input_value", name: "LIST", check: "Array" },
    ],
    output: "Number", style: "library_blocks",
    tooltip: "من وحدة «رياضيات» في مكتبة «نون» القياسية.",
  },
];

// عناوين الكتل المدمجة بمفردات «نون» (ترجمة Blockly العربية فيها أخطاء، ولا تعرف اللغة)
const MESSAGES = {
  CONTROLS_IF_MSG_IF: "إذا", CONTROLS_IF_MSG_ELSEIF: "وإلا إذا", CONTROLS_IF_MSG_ELSE: "وإلا",
  CONTROLS_IF_MSG_THEN: "نفّذ", CONTROLS_IF_IF_TITLE_IF: "إذا",
  CONTROLS_IF_ELSEIF_TITLE_ELSEIF: "وإلا إذا", CONTROLS_IF_ELSE_TITLE_ELSE: "وإلا",
  CONTROLS_REPEAT_TITLE: "كرّر %1 مرّة", CONTROLS_REPEAT_INPUT_DO: "نفّذ",
  CONTROLS_WHILEUNTIL_OPERATOR_WHILE: "طالما", CONTROLS_WHILEUNTIL_OPERATOR_UNTIL: "حتّى",
  CONTROLS_WHILEUNTIL_INPUT_DO: "نفّذ",
  CONTROLS_FOR_TITLE: "لكل %1 من %2 إلى %3 بخطوة %4", CONTROLS_FOR_INPUT_DO: "نفّذ",
  CONTROLS_FOREACH_TITLE: "لكل %1 في %2", CONTROLS_FOREACH_INPUT_DO: "نفّذ",
  CONTROLS_FLOW_STATEMENTS_OPERATOR_BREAK: "توقف",
  CONTROLS_FLOW_STATEMENTS_OPERATOR_CONTINUE: "استمر",
  LOGIC_OPERATION_AND: "و", LOGIC_OPERATION_OR: "أو", LOGIC_NEGATE_TITLE: "ليس %1",
  LOGIC_BOOLEAN_TRUE: "صحيح", LOGIC_BOOLEAN_FALSE: "خطأ", LOGIC_NULL: "عدم",
  VARIABLES_DEFAULT_NAME: "عنصر", VARIABLES_SET: "اجعل %1 = %2", MATH_CHANGE_TITLE: "زِد %1 بمقدار %2",
  NEW_VARIABLE: "متغيّر جديد…", NEW_VARIABLE_TITLE: "اسم المتغيّر الجديد:",
  RENAME_VARIABLE: "أعِد تسمية المتغيّر…", DELETE_VARIABLE: "احذف المتغيّر «%1»",
  PROCEDURES_DEFNORETURN_TITLE: "دالة", PROCEDURES_DEFRETURN_TITLE: "دالة",
  PROCEDURES_DEFNORETURN_PROCEDURE: "افعل_شيئا", PROCEDURES_DEFRETURN_PROCEDURE: "احسب_شيئا",
  PROCEDURES_DEFRETURN_RETURN: "أرجع", PROCEDURES_DEFNORETURN_DO: "", PROCEDURES_DEFRETURN_DO: "",
  PROCEDURES_BEFORE_PARAMS: "بالوسائط:", PROCEDURES_CALL_BEFORE_PARAMS: "بالوسائط:",
  PROCEDURES_MUTATORCONTAINER_TITLE: "الوسائط", PROCEDURES_MUTATORARG_TITLE: "وسيط:",
  TEXT_JOIN_TITLE_CREATEWITH: "اجمع نصًّا من", TEXT_CREATE_JOIN_TITLE_JOIN: "اجمع",
  TEXT_LENGTH_TITLE: "طول %1", TEXT_ISEMPTY_TITLE: "%1 فارغ", TEXT_REVERSE_MESSAGE0: "اعكس %1",
  LISTS_CREATE_EMPTY_TITLE: "قائمة فارغة", LISTS_CREATE_WITH_INPUT_WITH: "قائمة من",
  LISTS_CREATE_WITH_CONTAINER_TITLE_ADD: "قائمة", LISTS_CREATE_WITH_ITEM_TITLE: "عنصر",
  LISTS_REPEAT_TITLE: "قائمة فيها %1 مكرّرًا %2 مرّة", LISTS_LENGTH_TITLE: "طول %1",
  LISTS_ISEMPTY_TITLE: "%1 فارغة", LISTS_REVERSE_MESSAGE0: "اعكس %1",
  LISTS_SORT_TITLE: "رتّب %1 %2 %3", LISTS_SORT_TYPE_NUMERIC: "عدديًّا",
  LISTS_SORT_TYPE_TEXT: "أبجديًّا", LISTS_SORT_TYPE_IGNORECASE: "أبجديًّا",
  LISTS_SORT_ORDER_ASCENDING: "تصاعديًّا", LISTS_SORT_ORDER_DESCENDING: "تنازليًّا",
  MATH_RANDOM_INT_TITLE: "عدد عشوائي من %1 إلى %2", MATH_MODULO_TITLE: "باقي قسمة %1 ÷ %2",
  MATH_IS_EVEN: "زوجي", MATH_IS_ODD: "فردي", MATH_IS_PRIME: "أوّلي", MATH_IS_WHOLE: "صحيح",
  MATH_IS_POSITIVE: "موجب", MATH_IS_NEGATIVE: "سالب", MATH_IS_DIVISIBLE_BY: "يقبل القسمة على",
};

// ——— صندوق الأدوات ———

const num = (value) => ({ shadow: { type: "math_number", fields: { NUM: value } } });
const txt = (value) => ({ shadow: { type: "text", fields: { TEXT: value } } });

export const TOOLBOX = {
  kind: "categoryToolbox",
  contents: [
    { kind: "category", name: "الإخراج والإدخال", categorystyle: "io_category", contents: [
      { kind: "block", type: "noon_print", inputs: { VALUE: txt("مرحبًا يا عالم") } },
      { kind: "block", type: "noon_print2", inputs: { A: txt("النتيجة:"), B: num(42) } },
      { kind: "block", type: "noon_input", inputs: { PROMPT: txt("ما اسمك؟") } },
    ] },
    { kind: "category", name: "المنطق", categorystyle: "logic_category", contents: [
      { kind: "block", type: "controls_if" },
      { kind: "block", type: "controls_if", extraState: { hasElse: true } },
      { kind: "block", type: "logic_compare" },
      { kind: "block", type: "logic_operation" },
      { kind: "block", type: "logic_negate" },
      { kind: "block", type: "logic_boolean" },
      { kind: "block", type: "logic_null" },
      { kind: "block", type: "noon_contains" },
    ] },
    { kind: "category", name: "الحلقات", categorystyle: "loop_category", contents: [
      { kind: "block", type: "controls_repeat_ext", inputs: { TIMES: num(10) } },
      { kind: "block", type: "controls_whileUntil" },
      { kind: "block", type: "controls_for", fields: { VAR: { name: "ع" } },
        inputs: { FROM: num(1), TO: num(10), BY: num(1) } },
      { kind: "block", type: "controls_forEach", fields: { VAR: { name: "عنصر" } } },
      { kind: "block", type: "controls_flow_statements" },
    ] },
    { kind: "category", name: "الحساب", categorystyle: "math_category", contents: [
      { kind: "block", type: "math_number", fields: { NUM: 0 } },
      { kind: "block", type: "math_arithmetic", inputs: { A: num(1), B: num(1) } },
      { kind: "block", type: "noon_math_single", inputs: { NUM: num(9) } },
      { kind: "block", type: "math_modulo", inputs: { DIVIDEND: num(64), DIVISOR: num(10) } },
      { kind: "block", type: "math_number_property", inputs: { NUMBER_TO_CHECK: num(0) } },
      { kind: "block", type: "math_random_int", inputs: { FROM: num(1), TO: num(100) } },
      { kind: "block", type: "math_constant" },
    ] },
    { kind: "category", name: "مكتبة رياضيات", categorystyle: "library_category", contents: [
      { kind: "label", text: "من الوحدة «رياضيات»: استورد(\"رياضيات\")" },
      { kind: "block", type: "noon_lib1", inputs: { N: num(10) } },
      { kind: "block", type: "noon_lib1", fields: { FUNC: "الأعداد_الأولية" }, inputs: { N: num(50) } },
      { kind: "block", type: "noon_lib2", inputs: { A: num(12), B: num(18) } },
      { kind: "block", type: "noon_lib_stats" },
    ] },
    { kind: "category", name: "النصوص", categorystyle: "text_category", contents: [
      { kind: "block", type: "text" },
      { kind: "block", type: "text_join" },
      { kind: "block", type: "text_length", inputs: { VALUE: txt("نون") } },
      { kind: "block", type: "text_isEmpty", inputs: { VALUE: txt("") } },
      { kind: "block", type: "text_reverse", inputs: { TEXT: txt("سلام") } },
      { kind: "block", type: "noon_convert" },
    ] },
    { kind: "category", name: "القوائم", categorystyle: "list_category", contents: [
      { kind: "block", type: "lists_create_empty" },
      { kind: "block", type: "lists_create_with", inline: true },
      { kind: "block", type: "noon_range", inputs: { FROM: num(1), TO: num(10) } },
      { kind: "block", type: "lists_repeat", inputs: { NUM: num(5) } },
      { kind: "block", type: "noon_list_get", inputs: { INDEX: num(1) } },
      { kind: "block", type: "noon_list_set", inputs: { INDEX: num(1) } },
      { kind: "block", type: "noon_list_append" },
      { kind: "block", type: "lists_length" },
      { kind: "block", type: "lists_isEmpty" },
      { kind: "block", type: "noon_list_math" },
      { kind: "block", type: "lists_sort" },
      { kind: "block", type: "lists_reverse" },
    ] },
    { kind: "sep" },
    { kind: "category", name: "المتغيّرات", categorystyle: "variable_category", custom: "VARIABLE" },
    { kind: "category", name: "الدوال", categorystyle: "procedure_category", custom: "PROCEDURE" },
  ],
};

// ——— الألوان: فاتح وداكن، بألوان موقع التوثيق ———

const BLOCK_COLOURS = {
  io: "#0f7a70", logic: "#3f6ec6", loop: "#a8650c", math: "#5b62c7", library: "#b24a6f",
  text: "#2e7d4f", list: "#7a4fb0", variable: "#c0504d", procedure: "#1f7fa8",
};

function defineThemes(Blockly) {
  const blockStyles = {};
  const categoryStyles = {};
  for (const [name, colour] of Object.entries(BLOCK_COLOURS)) {
    blockStyles[name + "_blocks"] = { colourPrimary: colour };
    categoryStyles[name + "_category"] = { colour };
  }
  blockStyles.variable_dynamic_blocks = blockStyles.variable_blocks;
  blockStyles.hat_blocks = { colourPrimary: BLOCK_COLOURS.procedure, hat: "cap" };
  const fontStyle = { family: '"IBM Plex Sans Arabic", system-ui, sans-serif', weight: "600", size: 12 };
  const base = { base: Blockly.Themes.Classic, blockStyles, categoryStyles, fontStyle, startHats: false };
  return {
    light: Blockly.Theme.defineTheme("noon-light", { ...base, componentStyles: {
      workspaceBackgroundColour: "#fbfaf7", toolboxBackgroundColour: "#ffffff",
      toolboxForegroundColour: "#22262a", flyoutBackgroundColour: "#f1efe9",
      flyoutForegroundColour: "#22262a", flyoutOpacity: 1, scrollbarColour: "#b9b4a8",
      insertionMarkerColour: "#22262a", insertionMarkerOpacity: 0.25,
      selectedGlowColour: "#b07a22", cursorColour: "#b07a22",
    } }),
    dark: Blockly.Theme.defineTheme("noon-dark", { ...base, componentStyles: {
      workspaceBackgroundColour: "#15191c", toolboxBackgroundColour: "#1d2226",
      toolboxForegroundColour: "#e3e6e8", flyoutBackgroundColour: "#252b30",
      flyoutForegroundColour: "#e3e6e8", flyoutOpacity: 1, scrollbarColour: "#4a535a",
      insertionMarkerColour: "#ffffff", insertionMarkerOpacity: 0.3,
      selectedGlowColour: "#e0ad55", cursorColour: "#e0ad55",
    } }),
  };
}

// ——— المترجِم: الكتل ← «نون» ———

function createGenerator(Blockly) {
  class NoonGenerator extends Blockly.CodeGenerator {
    constructor() {
      super("نون");
      this.INDENT = "    ";
    }

    init(workspace) {
      super.init?.(workspace);
      this.definitions_ = Object.create(null);
      this.usesMath_ = false;
      this.variables_ = new Set();
      this.isInitialized = true;
    }

    // المتغيّرات تُصرَّح في أوّل البرنامج، والدوال قبل أن تُستعمل
    finish(code) {
      const head = [];
      if (this.usesMath_) head.push(`متغير ${MATH_MODULE} = استورد("${MATH_MODULE}")`);
      for (const name of this.variables_) head.push(`متغير ${name} = عدم`);
      const parts = [];
      if (head.length) parts.push(head.join("\n"));
      parts.push(...Object.values(this.definitions_));
      if (code.trim()) parts.push(code);
      this.definitions_ = Object.create(null);
      return parts.join("\n\n");
    }

    scrub_(block, code, thisOnly) {
      const next = block.nextConnection && block.nextConnection.targetBlock();
      return code + (thisOnly ? "" : this.blockToCode(next));
    }

    scrubNakedValue() {
      return "";                // كتلة قيمة وحدها في مساحة العمل لا تفعل شيئًا
    }

    math(name) {
      this.usesMath_ = true;
      return `${MATH_MODULE}.${name}`;
    }

    // اسم متغيّر يُستعمل هنا؛ يُصرَّح عامًّا إلا إن كان وسيط دالة أو متغيّر حلقة تحيط به
    useVariable(block, field = "VAR") {
      const name = variableName(block, field);
      let parent = block.getSurroundParent();
      while (parent) {
        if ((parent.type === "controls_for" || parent.type === "controls_forEach")
            && variableName(parent) === name) return name;
        if (parent.type.startsWith("procedures_def") && params(parent).includes(name)) return name;
        parent = parent.getSurroundParent();
      }
      this.variables_.add(name);
      return name;
    }

    value(block, input, order, fallback = "عدم") {
      return this.valueToCode(block, input, order) || fallback;
    }

    body(block, input) {
      return this.statementToCode(block, input);
    }

    args(block, count) {
      const list = [];
      for (let i = 0; i < count; i++) list.push(this.value(block, "ARG" + i, ORDER.NONE));
      return list.join(COMMA);
    }
  }

  const g = new NoonGenerator();
  const f = g.forBlock;
  const O = ORDER;

  // الإخراج والإدخال
  f.noon_print = (b) => `اطبع(${g.valueToCode(b, "VALUE", O.NONE)})\n`;
  f.noon_print2 = (b) =>
    `اطبع(${g.value(b, "A", O.NONE, '""')}${COMMA}${g.value(b, "B", O.NONE, '""')})\n`;
  f.noon_input = (b) => {
    const read = `اقرأ(${g.valueToCode(b, "PROMPT", O.NONE)})`;
    return b.getFieldValue("TYPE") === "NUMBER" ? [`عدد(${read})`, O.POSTFIX] : [read, O.POSTFIX];
  };

  // المنطق
  f.controls_if = (b) => {
    let code = "";
    let n = 0;
    do {
      const cond = g.value(b, "IF" + n, O.NONE, "خطأ");
      code += (n === 0 ? "إذا (" : " وإلا إذا (") + cond + ") {\n" + g.body(b, "DO" + n) + "}";
      n++;
    } while (b.getInput("IF" + n));
    if (b.getInput("ELSE")) code += " وإلا {\n" + g.body(b, "ELSE") + "}";
    return code + "\n";
  };
  const COMPARE = { EQ: "==", NEQ: "!=", LT: "<", LTE: "<=", GT: ">", GTE: ">=" };
  f.logic_compare = (b) => {
    const op = COMPARE[b.getFieldValue("OP")];
    const order = op === "==" || op === "!=" ? O.EQUALITY : O.RELATIONAL;
    return [`${g.value(b, "A", order, "0")} ${op} ${g.value(b, "B", order, "0")}`, order];
  };
  f.logic_operation = (b) => {
    const and = b.getFieldValue("OP") === "AND";
    const order = and ? O.AND : O.OR;
    const fallback = and ? "صحيح" : "خطأ";
    return [`${g.value(b, "A", order, fallback)} ${and ? "و" : "أو"} ${g.value(b, "B", order, fallback)}`, order];
  };
  f.logic_negate = (b) => [`ليس ${g.value(b, "BOOL", O.UNARY, "صحيح")}`, O.UNARY];
  f.logic_boolean = (b) => [b.getFieldValue("BOOL") === "TRUE" ? "صحيح" : "خطأ", O.ATOMIC];
  f.logic_null = () => ["عدم", O.ATOMIC];
  f.noon_contains = (b) =>
    [`${g.value(b, "ITEM", O.RELATIONAL)} في ${g.value(b, "CONTAINER", O.RELATIONAL, "[]")}`, O.RELATIONAL];

  // الحلقات
  f.controls_repeat_ext = (b) =>
    `لكل _ في مدى(${g.value(b, "TIMES", O.NONE, "0")}) {\n${g.body(b, "DO")}}\n`;
  f.controls_whileUntil = (b) => {
    const until = b.getFieldValue("MODE") === "UNTIL";
    const cond = until ? `ليس ${g.value(b, "BOOL", O.UNARY, "خطأ")}` : g.value(b, "BOOL", O.NONE, "خطأ");
    return `طالما (${cond}) {\n${g.body(b, "DO")}}\n`;
  };
  const literal = (code) => (/^-?\d+(\.\d+)?$/.test(code) ? Number(code) : null);
  f.controls_for = (b) => {
    const name = variableName(b);
    const from = g.value(b, "FROM", O.NONE, "0");
    const to = g.value(b, "TO", O.NONE, "0");
    const by = g.value(b, "BY", O.NONE, "1");
    const [a, z, s] = [literal(from), literal(to), literal(by)];
    let range;
    if (a !== null && z !== null && s !== null) {
      const step = Math.abs(s) || 1;             // كما في Blockly: الاتجاه من الحدّين
      if (a <= z) {
        range = step === 1 ? `مدى(${a}${COMMA}${z + 1})` : `مدى(${a}${COMMA}${z + 1}${COMMA}${step})`;
      } else {
        range = `مدى(${a}${COMMA}${z - 1}${COMMA}${-step})`;
      }
    } else {
      const end = `${g.value(b, "TO", O.ADDITIVE, "0")} + 1`;
      range = by === "1" ? `مدى(${from}${COMMA}${end})` : `مدى(${from}${COMMA}${end}${COMMA}${by})`;
    }
    return `لكل ${name} في ${range} {\n${g.body(b, "DO")}}\n`;
  };
  f.controls_forEach = (b) =>
    `لكل ${variableName(b)} في ${g.value(b, "LIST", O.NONE, "[]")} {\n${g.body(b, "DO")}}\n`;
  f.controls_flow_statements = (b) => (b.getFieldValue("FLOW") === "BREAK" ? "توقف\n" : "استمر\n");

  // الحساب
  f.math_number = (b) => {
    const n = Number(b.getFieldValue("NUM"));
    return [String(n), n < 0 ? O.UNARY : O.ATOMIC];
  };
  const ARITHMETIC = {
    ADD: ["+", O.ADDITIVE], MINUS: ["-", O.ADDITIVE], MULTIPLY: ["*", O.MULTIPLICATIVE],
    DIVIDE: ["/", O.MULTIPLICATIVE], POWER: ["**", O.POWER],
  };
  f.math_arithmetic = (b) => {
    const [op, order] = ARITHMETIC[b.getFieldValue("OP")];
    if (op === "**") {
      return [`${g.value(b, "A", O.POWER, "0")} ** ${g.value(b, "B", POWER_RIGHT, "0")}`, O.POWER];
    }
    // يمين الطرح والقسمة يُقوَّس إن كان من الدرجة نفسها: أ - (ب - ج)
    const rightOrder = op === "-" || op === "/" ? order - 0.5 : order;
    return [`${g.value(b, "A", order, "0")} ${op} ${g.value(b, "B", rightOrder, "0")}`, order];
  };
  f.noon_math_single = (b) => [`${b.getFieldValue("OP")}(${g.value(b, "NUM", O.NONE, "0")})`, O.POSTFIX];
  f.math_modulo = (b) =>
    [`${g.value(b, "DIVIDEND", O.MULTIPLICATIVE, "0")} % ${g.value(b, "DIVISOR", O.MULTIPLICATIVE - 0.5, "1")}`,
      O.MULTIPLICATIVE];
  f.math_random_int = (b) =>
    [`عشوائي(${g.value(b, "FROM", O.NONE, "0")}${COMMA}${g.value(b, "TO", O.NONE, "0")})`, O.POSTFIX];
  f.math_number_property = (b) => {
    const x = (order) => g.value(b, "NUMBER_TO_CHECK", order, "0");
    switch (b.getFieldValue("PROPERTY")) {
      case "EVEN": return [`${x(O.MULTIPLICATIVE)} % 2 == 0`, O.EQUALITY];
      case "ODD": return [`${x(O.MULTIPLICATIVE)} % 2 == 1`, O.EQUALITY];
      case "WHOLE": return [`${x(O.MULTIPLICATIVE)} % 1 == 0`, O.EQUALITY];
      case "PRIME": return [`${g.math("أولي")}(${x(O.NONE)})`, O.POSTFIX];
      case "POSITIVE": return [`${x(O.RELATIONAL)} > 0`, O.RELATIONAL];
      case "NEGATIVE": return [`${x(O.RELATIONAL)} < 0`, O.RELATIONAL];
      case "DIVISIBLE_BY":
        return [`${x(O.MULTIPLICATIVE)} % ${g.value(b, "DIVISOR", O.MULTIPLICATIVE - 0.5, "1")} == 0`,
          O.EQUALITY];
    }
    return ["خطأ", O.ATOMIC];
  };
  f.math_constant = (b) => {
    switch (b.getFieldValue("CONSTANT")) {
      case "PI": return ["باي", O.ATOMIC];
      case "E": return [g.math("ه"), O.POSTFIX];
      case "GOLDEN_RATIO": return [g.math("نسبة_ذهبية"), O.POSTFIX];
      case "SQRT2": return ["جذر(2)", O.POSTFIX];
      case "SQRT1_2": return ["جذر(0.5)", O.POSTFIX];
      case "INFINITY": return ['عدد("inf")', O.POSTFIX];
    }
    return ["0", O.ATOMIC];
  };
  f.noon_lib1 = (b) => [`${g.math(b.getFieldValue("FUNC"))}(${g.value(b, "N", O.NONE, "0")})`, O.POSTFIX];
  f.noon_lib2 = (b) =>
    [`${g.math(b.getFieldValue("FUNC"))}(${g.value(b, "A", O.NONE, "0")}${COMMA}${g.value(b, "B", O.NONE, "0")})`,
      O.POSTFIX];
  f.noon_lib_stats = (b) =>
    [`${g.math(b.getFieldValue("FUNC"))}(${g.value(b, "LIST", O.NONE, "[]")})`, O.POSTFIX];

  // النصوص
  f.text = (b) => [quote(b.getFieldValue("TEXT")), O.ATOMIC];
  f.text_join = (b) => {
    const parts = [];
    for (let i = 0; i < b.itemCount_; i++) parts.push(g.value(b, "ADD" + i, O.ADDITIVE, '""'));
    if (parts.length === 0) return ['""', O.ATOMIC];
    // «+» يجمع الأعداد جمعًا حسابيًّا، فالأوّل يُحوَّل نصًّا ليصير الباقي وصلًا
    const first = g.value(b, "ADD0", O.NONE, '""');
    const head = /^"/.test(first) && literalText(first) ? first : `نص(${first})`;
    if (parts.length === 1) return [head, O.POSTFIX];
    return [[head, ...parts.slice(1)].join(" + "), O.ADDITIVE];
  };
  const literalText = (code) => /^"(?:[^"\\]|\\.)*"$/.test(code);
  f.text_length = (b) => [`طول(${g.value(b, "VALUE", O.NONE, '""')})`, O.POSTFIX];
  f.text_isEmpty = (b) => [`طول(${g.value(b, "VALUE", O.NONE, '""')}) == 0`, O.EQUALITY];
  f.text_reverse = (b) => [`عكس(${g.value(b, "TEXT", O.NONE, '""')})`, O.POSTFIX];
  f.noon_convert = (b) => [`${b.getFieldValue("OP")}(${g.value(b, "VALUE", O.NONE)})`, O.POSTFIX];

  // القوائم
  f.lists_create_empty = () => ["[]", O.ATOMIC];
  f.lists_create_with = (b) => {
    const items = [];
    for (let i = 0; i < b.itemCount_; i++) items.push(g.value(b, "ADD" + i, O.NONE));
    return [`[${items.join(COMMA)}]`, O.ATOMIC];
  };
  f.noon_range = (b) => {
    const from = g.value(b, "FROM", O.NONE, "0");
    const to = g.value(b, "TO", O.NONE, "0");
    const z = literal(to);
    const end = z !== null ? String(z + 1) : `${g.value(b, "TO", O.ADDITIVE, "0")} + 1`;
    return [`مدى(${from}${COMMA}${end})`, O.POSTFIX];
  };
  f.lists_repeat = (b) =>
    [`[${g.value(b, "ITEM", O.NONE)}] * ${g.value(b, "NUM", O.MULTIPLICATIVE - 0.5, "0")}`, O.MULTIPLICATIVE];
  // العدّ من ١ في الكتل، ومن ٠ في «نون»
  const index = (b) => {
    const code = g.value(b, "INDEX", O.ADDITIVE, "1");
    const n = literal(code);
    return n !== null ? String(n - 1) : `${code} - 1`;
  };
  f.noon_list_get = (b) => [`${g.value(b, "LIST", POSTFIX_OPERAND, "[]")}[${index(b)}]`, O.POSTFIX];
  f.noon_list_set = (b) =>
    `${g.value(b, "LIST", POSTFIX_OPERAND, "[]")}[${index(b)}] = ${g.value(b, "VALUE", O.NONE)}\n`;
  f.noon_list_append = (b) =>
    `${g.value(b, "LIST", POSTFIX_OPERAND, "[]")}.أضف(${g.value(b, "VALUE", O.NONE)})\n`;
  f.lists_length = (b) => [`طول(${g.value(b, "VALUE", O.NONE, "[]")})`, O.POSTFIX];
  f.lists_isEmpty = (b) => [`طول(${g.value(b, "VALUE", O.NONE, "[]")}) == 0`, O.EQUALITY];
  f.noon_list_math = (b) => [`${b.getFieldValue("OP")}(${g.value(b, "LIST", O.NONE, "[]")})`, O.POSTFIX];
  f.lists_sort = (b) => {
    const list = g.value(b, "LIST", O.NONE, "[]");
    return [b.getFieldValue("DIRECTION") === "-1" ? `فرز(${list}${COMMA}عدم${COMMA}صحيح)` : `فرز(${list})`,
      O.POSTFIX];
  };
  f.lists_reverse = (b) => [`عكس(${g.value(b, "LIST", O.NONE, "[]")})`, O.POSTFIX];

  // المتغيّرات
  f.variables_get = (b) => [g.useVariable(b), O.ATOMIC];
  f.variables_set = (b) => `${g.useVariable(b)} = ${g.value(b, "VALUE", O.NONE)}\n`;
  f.math_change = (b) => `${g.useVariable(b)} += ${g.value(b, "DELTA", O.NONE, "0")}\n`;

  // الدوال: تُجمع في أوّل البرنامج فتُنادى من أيّ مكان بعدها
  const define = (b) => {
    const name = noonName(b.getFieldValue("NAME"));
    let body = g.body(b, "STACK");
    if (b.getInput("RETURN")) {
      const value = g.valueToCode(b, "RETURN", O.NONE);
      if (value) body += `${g.INDENT}أرجع ${value}\n`;
    }
    g.definitions_["%" + name] = `دالة ${name}(${params(b).join(COMMA)}) {\n${body}}`;
    return null;
  };
  f.procedures_defnoreturn = define;
  f.procedures_defreturn = define;
  const callCode = (b) => {
    let count = 0;
    while (b.getInput("ARG" + count)) count++;
    return `${noonName(b.getFieldValue("NAME"))}(${g.args(b, count)})`;
  };
  f.procedures_callnoreturn = (b) => callCode(b) + "\n";
  f.procedures_callreturn = (b) => [callCode(b), O.POSTFIX];
  f.procedures_ifreturn = (b) => {
    const cond = g.value(b, "CONDITION", O.NONE, "خطأ");
    const value = b.hasReturnValue_ ? " " + g.value(b, "VALUE", O.NONE) : "";
    return `إذا (${cond}) {\n${g.INDENT}أرجع${value}\n}\n`;
  };

  return g;
}

// ——— الواجهة ———

export function createNoonBlocks(Blockly) {
  Object.assign(Blockly.Msg, MESSAGES);
  Blockly.common.defineBlocksWithJsonArray(CUSTOM_BLOCKS);
  return { generator: createGenerator(Blockly), toolbox: TOOLBOX, themes: defineThemes(Blockly) };
}

// كل نوع كتلة في صندوق الأدوات (للفحص الذاتي في الصفحة: لكلٍّ مترجِم)
export function toolboxBlockTypes(toolbox = TOOLBOX) {
  const types = new Set();
  const walk = (items) => {
    for (const item of items) {
      if (item.kind === "block") types.add(item.type);
      if (item.contents) walk(item.contents);
    }
  };
  walk(toolbox.contents);
  return [...types];
}
