// تلوين «نون» في CodeMirror: مُحلِّل لفظي صغير يحاكي noon/lexer.py.
// الكلمات المفتاحية والدوال المدمجة تأتي من language.js المولَّد من المُفسِّر نفسه.

import { StreamLanguage, HighlightStyle, indentUnit } from "@codemirror/language";
import { tags } from "@lezer/highlight";
import DATA from "./language.js";
import { normalize } from "./normalize.js";

const DIGIT = /[0-9\u0660-\u0669\u06F0-\u06F9]/;
const NUMBER = /^[0-9\u0660-\u0669\u06F0-\u06F9][0-9\u0660-\u0669\u06F0-\u06F9\u066C_]*(?:[.\u066B][0-9\u0660-\u0669\u06F0-\u06F9]+)?/;
const IDENT_START = /[\p{L}_]/u;
const IDENT_PART = /[\p{L}\p{N}_\u064B-\u0655\u0670\u06D6\u0640]/u;
const TWO_CHAR = new Set(["**", "==", "!=", "<=", ">=", "+=", "-=", "*=", "/=", "//", "&&", "||"]);
const OPERATORS = new Set(["+", "-", "*", "/", "%", "=", "<", ">", "!"]);

const BUILTINS = new Set(DATA.builtins);
const CONSTANTS = new Set(DATA.constants);
const METHODS = new Set(DATA.methods);

function readString(stream, quote) {
  let escaped = false;
  let ch;
  while ((ch = stream.next()) != null) {
    if (escaped) escaped = false;
    else if (ch === "\\") escaped = true;
    else if (ch === quote) return;
  }
}

export const noonLanguage = StreamLanguage.define({
  name: "noon",

  startState: () => ({ depth: 0, afterDot: false, expectName: false }),

  copyState: (s) => ({ ...s }),

  token(stream, state) {
    if (stream.eatSpace()) return null;
    const ch = stream.peek();

    if (ch === "#") {
      stream.skipToEnd();
      return "comment";
    }

    if (ch === '"' || ch === "'") {
      stream.next();
      readString(stream, ch);
      state.afterDot = state.expectName = false;
      return "string";
    }

    if (DIGIT.test(ch) && stream.match(NUMBER)) {
      state.afterDot = state.expectName = false;
      return "number";
    }

    if (IDENT_START.test(ch)) {
      stream.next();
      stream.eatWhile((c) => IDENT_PART.test(c));
      const word = stream.current();

      if (state.afterDot) {
        state.afterDot = false;
        return METHODS.has(word) && stream.match(/^\s*\(/, false) ? "builtin" : "property";
      }
      if (state.expectName) {
        state.expectName = false;
        return "def";
      }

      const keyword = DATA.keywords[normalize(word)];
      if (keyword) {
        if (keyword === "FUNC" || keyword === "CLASS" || keyword === "EXTENDS") {
          state.expectName = true;
        }
        if (keyword === "TRUE" || keyword === "FALSE" || keyword === "NULL") return "atom";
        if (keyword === "THIS" || keyword === "SUPER") return "variable-2";
        if (keyword === "AND" || keyword === "OR" || keyword === "NOT") return "operator";
        return "keyword";
      }
      // تابع داخل صنف بلا «دالة»: اسم ثم وسائط ثم كتلة على السطر نفسه
      if (stream.match(/^\s*\([^()]*\)\s*\{/, false)) return "def";
      if (BUILTINS.has(word)) return "builtin";
      if (CONSTANTS.has(word)) return "atom";
      return "variable";
    }

    stream.next();
    state.expectName = false;
    if (ch === ".") {
      state.afterDot = true;
      return "punctuation";
    }
    state.afterDot = false;
    if (ch === "{") state.depth++;
    if (ch === "}") state.depth = Math.max(0, state.depth - 1);
    if (TWO_CHAR.has(ch + (stream.peek() || ""))) {
      stream.next();
      return "operator";
    }
    if (OPERATORS.has(ch)) return "operator";
    return "punctuation";
  },

  indent(state, textAfter, context) {
    const closing = /^\s*\}/.test(textAfter) ? 1 : 0;
    return Math.max(0, state.depth - closing) * context.unit;
  },

  languageData: {
    commentTokens: { line: "#" },
    closeBrackets: { brackets: ["(", "[", "{", '"', "'"] },
    indentOnInput: /^\s*\}$/,
  },
});

// الألوان من متغيّرات CSS، فتتبع الوضعين الفاتح والداكن دون إعادة إنشاء المحرّر
export const noonHighlight = HighlightStyle.define([
  { tag: tags.keyword, color: "var(--tok-keyword)", fontWeight: "600" },
  { tag: tags.definition(tags.variableName), color: "var(--tok-def)", fontWeight: "600" },
  { tag: tags.standard(tags.variableName), color: "var(--tok-builtin)" },
  { tag: tags.special(tags.variableName), color: "var(--tok-this)", fontStyle: "italic" },
  { tag: tags.atom, color: "var(--tok-atom)" },
  { tag: tags.number, color: "var(--tok-number)" },
  { tag: tags.string, color: "var(--tok-string)" },
  { tag: tags.comment, color: "var(--tok-comment)", fontStyle: "italic" },
  { tag: tags.operator, color: "var(--tok-operator)" },
  { tag: tags.propertyName, color: "var(--tok-property)" },
  { tag: tags.punctuation, color: "var(--tok-punct)" },
]);

export const noonIndent = indentUnit.of("    ");
