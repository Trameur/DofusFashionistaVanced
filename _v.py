import re
from django.template import Template, RequestContext
from django.test import RequestFactory
rf = RequestFactory()
snip = '''{% load i18n %}{% trans "Built using data from " %}{% if current_game_version == 'retro' %}<a href="http://www.ankama-games.com/">Ankama</a> &amp; <a href="https://dofusretrotools.com/">Dofus Retro Tools</a>{% else %}<a href="https://docs.dofusdu.de/">dofusdude</a>{% endif %}'''
for gv in ('retro','dofus3'):
    r = rf.get('/'); r.game_version = gv
    out = re.sub(r'\s+',' ', Template(snip).render(RequestContext(r))).strip()
    print("RESULT %-7s -> %s" % (gv, out))
