/* ═══════════════════════════════════════════════════════════════
   RootSearch — إعدادات عنوان الباك-اند (Frontend Runtime Config)
   ───────────────────────────────────────────────────────────────
   • عند التشغيل محليًا (localhost) → تستخدم الواجهة نفس الأصل مباشرةً.
   • عند النشر على Vercel → تستخدم رابط النفق العام للباك-اند المحلي.

   👇 غيّر السطر التالي فقط بعد تشغيل النفق (Cloudflare Tunnel أو ngrok)
      وضع فيه الرابط الذي يظهر لك (لا تضع "/" في النهاية):
   ═══════════════════════════════════════════════════════════════ */

(function () {
  // ⚠️ استبدل هذا بالرابط العام للباك-اند من النفق (يجب أن يكون https)
  var REMOTE_BACKEND_URL = "https://ste-calculation-reward-ebony.trycloudflare.com";

  var host = location.hostname;
  var isLocal =
    host === "localhost" ||
    host === "127.0.0.1" ||
    host === "0.0.0.0" ||
    host === "";

  // محليًا: نفس الأصل (فارغ) — على Vercel: رابط النفق
  window.API_BASE = isLocal ? "" : REMOTE_BACKEND_URL;
})();
