// مطابقة `normalize` في noon/lexer.py: توحيد الهمزات والألف المقصورة والتاء، وحذف
// التطويل. التشكيل لا يُحذف، فـ«صنّف» اسم لا الكلمة المفتاحية «صنف».
// ملف مستقلّ بلا اعتماديات حتى يختبره tests/test_playground.py بـ Node.

export function normalize(word) {
  return word
    .replace(/\u0640/g, "")
    .replace(/[\u0623\u0625\u0622\u0671]/g, "\u0627")
    .replace(/\u0649/g, "\u064A")
    .replace(/\u0629/g, "\u0647");
}
