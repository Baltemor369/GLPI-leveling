"""
Patch appliqué au build Docker sur le template HTML statique de Streamlit.
Injecte :
  1. CSS de fond sombre (empêche le flash blanc entre les pages)
  2. Overlay JS thématisé (masque la transition pendant le chargement)
"""
import os
import streamlit

index_path = os.path.join(os.path.dirname(streamlit.__file__), "static", "index.html")
html = open(index_path, encoding="utf-8").read()

# ── 1. CSS fond sombre permanent ──────────────────────────────────────────────
CSS = (
    "<style>"
    "html,body,#root{background-color:#2c1810!important;margin:0;padding:0}"
    "</style>"
)

# ── 2. Overlay de navigation thématisé ───────────────────────────────────────
JS = """<script>
(function () {
  var ov = null, t = null;

  function mkOv() {
    if (ov) return;
    ov = document.createElement("div");
    ov.style.cssText = [
      "position:fixed", "inset:0", "background:#2c1810",
      "z-index:99999", "display:flex", "flex-direction:column",
      "align-items:center", "justify-content:center",
      "color:#c9a84c", "font-family:Georgia,serif",
      "opacity:0", "transition:opacity 0.2s ease", "pointer-events:none"
    ].join(";");
    ov.innerHTML =
      "<div style=\\"font-size:2rem\\">&#x2694;</div>" +
      "<div style=\\"font-size:0.65rem;letter-spacing:3px;margin-top:10px\\">CHARGEMENT...</div>";
    document.body.appendChild(ov);
  }

  function show() {
    mkOv();
    clearTimeout(t);
    ov.style.opacity = "1";
    ov.style.pointerEvents = "all";
    t = setTimeout(hide, 6000); /* failsafe */
  }

  function hide() {
    if (!ov) return;
    ov.style.opacity = "0";
    ov.style.pointerEvents = "none";
  }

  var lastPath = location.pathname;

  new MutationObserver(function () {
    /* Navigation détectée via changement d'URL */
    if (location.pathname !== lastPath) {
      lastPath = location.pathname;
      show();
    }
    /* Page prête : stMainBlockContainer a du contenu */
    var mc = document.querySelector("[data-testid=\\"stMainBlockContainer\\"]");
    if (mc && mc.childElementCount > 0 && ov && ov.style.opacity === "1") {
      clearTimeout(t);
      t = setTimeout(hide, 200);
    }
  }).observe(document.body, { childList: true, subtree: true });
})();
</script>"""

html = html.replace("</head>", CSS + "</head>", 1)
html = html.replace("</body>", JS + "</body>", 1)

open(index_path, "w", encoding="utf-8").write(html)
print(f"[patch] {index_path} patched OK")
