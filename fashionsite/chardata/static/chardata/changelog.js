var changelogLoaded = false;

// The entries are fetched on first open, they used to sit in every page.
function loadChangelog() {
    if (changelogLoaded) {
        return;
    }
    changelogLoaded = true;
    var body = document.getElementById('changelog-body');
    var url = window.CHANGELOG_CONTENT_URL || '/changelog-content/';
    fetch(url)
        .then(function (r) { return r.ok ? r.text() : Promise.reject(r.status); })
        .then(function (html) { body.innerHTML = html; })
        .catch(function () { changelogLoaded = false; });
}

function openChangelog() {
    loadChangelog();
    document.getElementById('changelog-overlay').style.display = 'block';
    document.getElementById('changelog-modal').style.display = 'flex';
}
function closeChangelog() {
    document.getElementById('changelog-overlay').style.display = 'none';
    document.getElementById('changelog-modal').style.display = 'none';
}
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') closeChangelog();
});
