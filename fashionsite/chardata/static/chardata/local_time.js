(function () {
    function localize(root) {
        var lang = document.documentElement.lang || undefined;
        var nodes = (root || document).querySelectorAll('time[data-fm-local-time]');
        for (var i = 0; i < nodes.length; i++) {
            var date = new Date(nodes[i].getAttribute('datetime'));
            if (isNaN(date.getTime())) {
                continue;
            }
            nodes[i].textContent = date.toLocaleString(lang, {dateStyle: 'short', timeStyle: 'short'});
        }
    }
    window.fmLocalizeTimes = localize;
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () { localize(); });
    } else {
        localize();
    }
})();
