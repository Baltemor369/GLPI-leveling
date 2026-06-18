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
# Couvre html/body/#root ET les conteneurs Streamlit pour ne laisser
# aucune surface blanche apparaître pendant la transition React.
CSS = (
    "<style>"
    "html,body,#root,.stApp,[data-testid='stApp'],"
    "section[data-testid='stSidebar'],"
    "[data-testid='stSidebarContent'],"
    "[data-testid='stSidebarUserContent'],"
    "[data-testid='stHeader'],"
    "[data-testid='stToolbar']"
    "{background-color:#2c1810!important;margin:0;padding:0}"
    "</style>"
)

# ── 2. Overlay de navigation thématisé ───────────────────────────────────────
# L'overlay est déclenché AU CLIC (phase capture) avant que le navigateur
# traite la navigation — c'est la seule façon d'être plus rapide que le flash.
# Il se retire dès que Streamlit a rendu le contenu de la nouvelle page.
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
      "opacity:1", "transition:opacity 0.3s ease", "pointer-events:all"
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
    t = setTimeout(hide, 8000); /* failsafe si la page ne charge pas */
  }

  function hide() {
    if (!ov) return;
    ov.style.opacity = "0";
    ov.style.pointerEvents = "none";
  }

  /* Intercepte le clic en phase CAPTURE (avant que le navigateur traite
     la navigation) pour afficher l'overlay AVANT tout flash blanc. */
  document.addEventListener("click", function (e) {
    var a = e.target.closest("a[href]");
    if (!a) return;
    var href = a.getAttribute("href") || "";
    if (href.startsWith("javascript:") || href.startsWith("#") || href.startsWith("mailto:")) return;
    show();
  }, true);

  /* Cache l'overlay quand Streamlit a fini de rendre la nouvelle page. */
  new MutationObserver(function () {
    var mc = document.querySelector("[data-testid=\\"stMainBlockContainer\\"]");
    if (mc && mc.childElementCount > 0 && ov && ov.style.opacity === "1") {
      clearTimeout(t);
      t = setTimeout(hide, 150);
    }
  }).observe(document.body, { childList: true, subtree: true });
})();
</script>"""

html = html.replace("</head>", CSS + "</head>", 1)
html = html.replace("</body>", JS + "</body>", 1)

open(index_path, "w", encoding="utf-8").write(html)
print(f"[patch] {index_path} patched OK")
