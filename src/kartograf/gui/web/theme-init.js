// Before the first paint: the stored theme (key "nogat-theme", shared with Nogat's other
// pages; "auto" or nothing follows the system) and the stored language (key
// "kartograf-lang", Polish by default). A file, not an inline script: the page's CSP allows
// scripts of its own origin only.
(function () {
  try {
    var theme = localStorage.getItem("nogat-theme");
    if (theme === "light" || theme === "dark") document.documentElement.dataset.theme = theme;
    var lang = localStorage.getItem("kartograf-lang");
    if (lang === "en" || lang === "pl") document.documentElement.lang = lang;
  } catch (e) {
    // Storage refused (a private window): the system's theme and Polish.
  }
})();
