# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Why a published build does not show in the gallery."""

# Reason order when several apply, the most concrete first
_ORDRE = ('missing_items', 'outdated_slots', 'conditions')


def refusal_reason(char):
    """The key of the reason the gallery hides this build, or None (also when unpublished)."""
    if not getattr(char, 'link_shared', False) or getattr(char, 'deleted', False):
        return None
    if not getattr(char, 'minimal_solution', None):
        # Already out of the gallery and sitemap, and /s/ answers 404
        return 'no_solution'
    from chardata.shared_builds_view import _get_shared_build_meta
    meta = _get_shared_build_meta(char)
    if not meta.get('is_invalid') and not meta.get('cannot_render'):
        return None
    drapeaux = {
        'missing_items': meta.get('has_missing_items'),
        'outdated_slots': meta.get('has_outdated_slots'),
        'conditions': meta.get('has_condition_issues'),
    }
    for cle in _ORDRE:
        if drapeaux.get(cle):
            return cle
    return 'no_solution' if meta.get('cannot_render') else None


def missing_piece_names(char):
    """Names of this build's missing pieces, in the reader's language."""
    from chardata.char_blobs import read_char_blob
    from chardata.legacy_missing import missing_names
    from fashionistapulp.translation import get_supported_language
    minimal = read_char_blob(getattr(char, 'minimal_solution', None), None,
                             'minimal_solution', char)
    if minimal is None:
        return []
    return missing_names(char, minimal, get_supported_language())


def refusal_sentence(reason, names=None):
    """The translated sentence to show, or an empty string."""
    from django.utils.translation import gettext as _
    if reason == 'missing_items':
        if names:
            return _('Not shown in the gallery: our catalogue no longer has '
                     '%(pieces)s. Replace what is missing and it comes '
                     'back.') % {'pieces': ', '.join(names)}
        return _('Not shown in the gallery: some of its items are no longer '
                 'in the game. Replace them and it comes back.')
    if reason == 'outdated_slots':
        return _('Not shown in the gallery: some pieces sit in a slot that no '
                 'longer takes them. Open the build and place them again.')
    if reason == 'conditions':
        return _('Not shown in the gallery: the build does not meet its own '
                 'conditions. Open it to see which ones.')
    if reason == 'no_solution':
        return _('Not shown in the gallery: this build has no saved gear yet.')
    return ''


def sentence_for(char):
    """The sentence for the author, shared by the project list and the build page."""
    reason = refusal_reason(char)
    if reason is None:
        return ''
    names = missing_piece_names(char) if reason == 'missing_items' else None
    return refusal_sentence(reason, names)
