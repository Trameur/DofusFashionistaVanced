from django.contrib.staticfiles.storage import (
    HashedFilesMixin,
    ManifestStaticFilesStorage,
)


class LenientManifestStaticFilesStorage(ManifestStaticFilesStorage):
    """Manifest static storage that never 500s on a missing asset.

    Under the strict ManifestStaticFilesStorage a ``{% static %}`` reference to
    a file that was not collected (e.g. an item icon missing from the source)
    raises ``ValueError`` and takes down the whole page -- the encyclopedia
    lists every item, so a single missing 60x60 icon 500s the listing.

    Here real, collected files are still hashed so deploys keep busting the
    CSS/JS cache, but a missing asset degrades to its plain (unhashed) URL -- a
    broken image at worst -- instead of raising.
    """
    manifest_strict = False

    def url(self, name, force=False):
        try:
            return super().url(name, force=force)
        except ValueError:
            # Not in the manifest and not on disk: fall back to the unhashed
            # URL (StaticFilesStorage behaviour) rather than 500-ing the page.
            return super(HashedFilesMixin, self).url(name)
