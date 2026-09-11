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

// The footer link carries the key of the newest entry (the title of the one
// on top, the same in every language). The browser keeps the key it last
// opened the changelog on; while the two differ, the link shows a mark.
// A reader who has never opened it sees the mark too: what is there is new
// to them. localStorage can be unavailable (private windows, blocked site
// data): the mark then shows every time, which is the harmless side.
var CHANGELOG_SEEN_KEY = 'changelog_seen';

function changelogLatestKey() {
    var link = document.getElementById('changelog-link');
    return link ? (link.getAttribute('data-changelog-latest') || '') : '';
}

function markChangelogIfUnseen() {
    var latest = changelogLatestKey();
    var mark = document.getElementById('changelog-new');
    if (!latest || !mark) {
        return;
    }
    var seen = null;
    try { seen = localStorage.getItem(CHANGELOG_SEEN_KEY); } catch (e) {}
    mark.hidden = (seen === latest);
}

function rememberChangelogSeen() {
    var latest = changelogLatestKey();
    if (latest) {
        try { localStorage.setItem(CHANGELOG_SEEN_KEY, latest); } catch (e) {}
    }
    var mark = document.getElementById('changelog-new');
    if (mark) {
        mark.hidden = true;
    }
}

function openChangelog() {
    loadChangelog();
    rememberChangelogSeen();
    document.getElementById('changelog-overlay').style.display = 'block';
    document.getElementById('changelog-modal').style.display = 'flex';
}
markChangelogIfUnseen();
function closeChangelog() {
    document.getElementById('changelog-overlay').style.display = 'none';
    document.getElementById('changelog-modal').style.display = 'none';
}
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') closeChangelog();
});
