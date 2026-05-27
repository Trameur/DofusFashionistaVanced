import threading

from fashionistapulp.structure import set_current_game_version

GAME_VERSION_PREFIXES = {'beta', 'retro', 'touch', 'dofus2'}


class GameVersionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        parts = request.path_info.lstrip('/').split('/', 1)
        if parts[0] in GAME_VERSION_PREFIXES:
            version = parts[0]
        else:
            version = 'dofus3'
        request.game_version = version
        set_current_game_version(version)
        return self.get_response(request)
