// مشاركة الشيفرة برابط: deflate خام + base64 للروابط، مثل encode_share في
// hooks/noon_docs.py. تستعمله ساحة التجربة ومحرّر الكتل.

function toBase64Url(bytes) {
  let binary = "";
  for (let i = 0; i < bytes.length; i += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  }
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}
function fromBase64Url(text) {
  const binary = atob(text.replace(/-/g, "+").replace(/_/g, "/") + "===".slice((text.length + 3) % 4));
  return Uint8Array.from(binary, (c) => c.charCodeAt(0));
}
async function pipe(bytes, transform) {
  const stream = new Blob([bytes]).stream().pipeThrough(transform);
  return new Uint8Array(await new Response(stream).arrayBuffer());
}
export async function encodeShare(code) {
  return toBase64Url(await pipe(new TextEncoder().encode(code), new CompressionStream("deflate-raw")));
}
export async function decodeShare(token) {
  return new TextDecoder().decode(await pipe(fromBase64Url(token), new DecompressionStream("deflate-raw")));
}
