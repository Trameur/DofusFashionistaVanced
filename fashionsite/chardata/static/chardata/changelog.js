function openChangelog() {
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
