/* Injecte le token CSRF sur tous les hx-post/put/patch/delete */
document.addEventListener('htmx:configRequest', function (evt) {
    if (['post', 'put', 'patch', 'delete'].includes(evt.detail.verb)) {
        var meta = document.querySelector('meta[name="csrf-token"]');
        if (meta) {
            evt.detail.headers['X-CSRFToken'] = meta.content;
        }
    }
});
