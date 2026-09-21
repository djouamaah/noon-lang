// أمثلة محرّر الكتل، بصيغة Blockly XML. كلٌّ منها يُترجَم إلى «نون» ويعمل كما هو.

const XML = (body, variables = []) =>
  '<xml xmlns="https://developers.google.com/blockly/xml">' +
  (variables.length
    ? "<variables>" + variables.map(([id, name]) => `<variable id="${id}">${name}</variable>`).join("") + "</variables>"
    : "") +
  body + "</xml>";

const text = (value) => `<block type="text"><field name="TEXT">${value}</field></block>`;
const number = (value) => `<shadow type="math_number"><field name="NUM">${value}</field></shadow>`;
const get = (id, name) => `<block type="variables_get"><field name="VAR" id="${id}">${name}</field></block>`;
const print = (inner, next = "") =>
  `<block type="noon_print"><value name="VALUE">${inner}</value>${next && `<next>${next}</next>`}</block>`;
const print2 = (a, b, next = "") =>
  `<block type="noon_print2"><value name="A">${a}</value><value name="B">${b}</value>` +
  `${next && `<next>${next}</next>`}</block>`;

export default [
  {
    name: "hello",
    title: "مرحبًا يا عالم",
    xml: XML(
      `<block type="noon_print" x="40" y="40"><value name="VALUE">${text("مرحبًا يا عالم")}</value>` +
      `<next><block type="controls_repeat_ext"><value name="TIMES">${number(3)}</value>` +
      `<statement name="DO">${print(text("نون تُبنى بالكتل"))}</statement></block></next></block>`),
  },
  {
    name: "table",
    title: "جدول الضرب",
    xml: XML(
      `<block type="controls_for" x="40" y="40"><field name="VAR" id="n">ع</field>` +
      `<value name="FROM">${number(1)}</value><value name="TO">${number(10)}</value>` +
      `<value name="BY">${number(1)}</value><statement name="DO">` +
      print(
        '<block type="text_join"><mutation items="3"></mutation>' +
        `<value name="ADD0">${get("n", "ع")}</value>` +
        `<value name="ADD1">${text(" × ٧ = ")}</value>` +
        '<value name="ADD2"><block type="math_arithmetic"><field name="OP">MULTIPLY</field>' +
        `<value name="A">${get("n", "ع")}</value><value name="B">${number(7)}</value></block></value>` +
        "</block>") +
      "</statement></block>",
      [["n", "ع"]]),
  },
  {
    name: "primes",
    title: "الأعداد الأولية (مكتبة رياضيات)",
    xml: XML(
      '<block type="variables_set" x="40" y="40"><field name="VAR" id="p">أوليات</field>' +
      '<value name="VALUE"><block type="noon_lib1"><field name="FUNC">الأعداد_الأولية</field>' +
      `<value name="N">${number(50)}</value></block></value><next>` +
      print2(text("الأعداد الأولية حتى ٥٠:"), get("p", "أوليات"),
        print2(text("عددها:"), `<block type="lists_length"><value name="VALUE">${get("p", "أوليات")}</value></block>`,
          print2(text("عاملي ١٠ ="),
            `<block type="noon_lib1"><field name="FUNC">عاملي</field><value name="N">${number(10)}</value></block>`,
            print2(text("القاسم المشترك الأكبر لـ ٨٤ و٣٦ ="),
              '<block type="noon_lib2"><field name="FUNC">قاسم_مشترك</field>' +
              `<value name="A">${number(84)}</value><value name="B">${number(36)}</value></block>`)))) +
      "</next></block>",
      [["p", "أوليات"]]),
  },
  {
    name: "grades",
    title: "درجات الطلاب",
    xml: XML(
      '<block type="variables_set" x="40" y="40"><field name="VAR" id="g">درجات</field>' +
      '<value name="VALUE"><block type="lists_create_with" inline="true"><mutation items="6"></mutation>' +
      [15, 12, 18, 9, 17, 7].map((n, i) =>
        `<value name="ADD${i}"><block type="math_number"><field name="NUM">${n}</field></block></value>`).join("") +
      "</block></value><next>" +
      print2(text("مرتّبة:"),
        '<block type="lists_sort"><field name="TYPE">NUMERIC</field><field name="DIRECTION">-1</field>' +
        `<value name="LIST">${get("g", "درجات")}</value></block>`,
        print2(text("المتوسط:"),
          '<block type="noon_lib_stats"><field name="FUNC">متوسط</field>' +
          `<value name="LIST">${get("g", "درجات")}</value></block>`,
          '<block type="controls_forEach"><field name="VAR" id="d">درجة</field>' +
          `<value name="LIST">${get("g", "درجات")}</value><statement name="DO">` +
          '<block type="controls_if"><mutation else="1"></mutation>' +
          '<value name="IF0"><block type="logic_compare"><field name="OP">GTE</field>' +
          `<value name="A">${get("d", "درجة")}</value><value name="B">${number(10)}</value></block></value>` +
          `<statement name="DO0">${print2(get("d", "درجة"), text("ناجح"))}</statement>` +
          `<statement name="ELSE">${print2(get("d", "درجة"), text("راسب"))}</statement>` +
          "</block></statement></block>")) +
      "</next></block>",
      [["g", "درجات"], ["d", "درجة"]]),
  },
  {
    name: "function",
    title: "دالة تُرجع قيمة",
    xml: XML(
      '<block type="procedures_defreturn" x="40" y="40"><mutation><arg name="س" varid="x"></arg></mutation>' +
      '<field name="NAME">مربع</field><value name="RETURN"><block type="math_arithmetic">' +
      `<field name="OP">MULTIPLY</field><value name="A">${get("x", "س")}</value>` +
      `<value name="B">${get("x", "س")}</value></block></value></block>` +
      '<block type="controls_for" x="40" y="200"><field name="VAR" id="i">ع</field>' +
      `<value name="FROM">${number(1)}</value><value name="TO">${number(5)}</value>` +
      `<value name="BY">${number(1)}</value><statement name="DO">` +
      print2(get("i", "ع"),
        '<block type="procedures_callreturn"><mutation name="مربع"><arg name="س"></arg></mutation>' +
        `<value name="ARG0">${get("i", "ع")}</value></block>`) +
      "</statement></block>",
      [["x", "س"], ["i", "ع"]]),
  },
  {
    name: "greet",
    title: "تحية (تقرأ من لسان الدخل)",
    xml: XML(
      '<block type="variables_set" x="40" y="40"><field name="VAR" id="n">اسم</field>' +
      '<value name="VALUE"><block type="noon_input"><field name="TYPE">TEXT</field>' +
      `<value name="PROMPT">${text("ما اسمك؟ ")}</value></block></value><next>` +
      print('<block type="text_join"><mutation items="3"></mutation>' +
        `<value name="ADD0">${text("أهلًا يا ")}</value><value name="ADD1">${get("n", "اسم")}</value>` +
        `<value name="ADD2">${text("!")}</value></block>`) +
      "</next></block>",
      [["n", "اسم"]]),
    stdin: "هند",
  },
];
