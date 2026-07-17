/* ═══════════════════════════════════════════════════════════════
   RootSearch — إعدادات عنوان الباك-اند (Frontend Runtime Config)
   ───────────────────────────────────────────────────────────────
   • عند التشغيل محليًا (localhost) → تستخدم الواجهة نفس الأصل مباشرةً.
   • عند النشر على Vercel → تستخدم رابط النفق العام للباك-اند المحلي.

   👇 غيّر السطر التالي فقط بعد تشغيل النفق (Cloudflare Tunnel أو ngrok)
      وضع فيه الرابط الذي يظهر لك (لا تضع "/" في النهاية):
   ═══════════════════════════════════════════════════════════════ */

(function () {
  // ⚠️ القيمة الافتراضية الاحتياطية
  var FALLBACK_REMOTE_BACKEND_URL = "https://ste-calculation-reward-ebony.trycloudflare.com";
  var APP_KEY = "bjalhi4q";
  var KEY = "backend_url";

  var host = location.hostname;
  var isLocal =
    host === "localhost" ||
    host === "127.0.0.1" ||
    host === "0.0.0.0" ||
    host === "";

  // محليًا: نفس الأصل (فارغ) — على Vercel: رابط النفق
  if (isLocal) {
    window.API_BASE = "";
    window.API_BASE_PROMISE = Promise.resolve("");
  } else {
    // على Vercel: جلب الرابط الديناميكي من مخزن المفاتيح السحابي
    window.API_BASE = FALLBACK_REMOTE_BACKEND_URL; // قيمة احتياطية فورية
    window.API_BASE_PROMISE = (async function () {
      try {
        const response = await fetch("https://keyvalue.immanuel.co/api/KeyVal/GetValue/" + APP_KEY + "/" + KEY + "?t=" + Date.now(), { cache: "no-store" });
        const encodedUrl = await response.json();
        if (encodedUrl && encodedUrl !== "null") {
          // فك تشفير Base64 للرابط
          const decodedUrl = atob(encodedUrl).trim();
          if (decodedUrl.startsWith("http")) {
            window.API_BASE = decodedUrl;
            console.log("[RootSearch] Loaded dynamic backend URL:", decodedUrl);
            return decodedUrl;
          }
        }
      } catch (err) {
        console.error("[RootSearch] Failed to fetch dynamic backend URL, using fallback:", err);
      }
      return window.API_BASE;
    })();
  }
})();
