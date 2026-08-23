"""A channel that tells a newcomer where to write and how a badge is earned.

The server had no orientation channel at all. Someone arriving found six
channels and no indication of what belongs where, and three coloured badges
with no way of knowing how anyone got one. A badge nobody knows how to earn
decorates; it does not invite.

Read-only by design: it is a sign, not a conversation. Everything else stays
where the conversation already happens.

Dry run by default.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import discord_api  # noqa: E402

GUILD = '1188892643766321173'
CHANNEL = 'bienvenue'

#: Discord permission bit for sending messages.
SEND_MESSAGES = 1 << 11

# Written in French and English because that is what the channels actually
# hold. Nothing is promised that the site does not already do.
MESSAGE = """# Bienvenue

**Dofus Fashionista** construit un stuff optimisé à partir de tes contraintes : PA, PM, résistances, poids de chaque statistique. Dofus 3, bêta, Dofus 2, Retro et Touch, en cinq langues.
→ https://dofusfashionista.gg

## Où écrire quoi

**#bug-report** — quelque chose ne marche pas. Un lien de partage de ton stuff aide énormément : il permet de reproduire en un clic.
**#suggestions** — une idée, un manque, ou une règle du jeu que l'outil modélise mal.
**#roadmap** — ce qui est prévu. **#dev-update** — ce qui vient d'être mis en ligne.

## Les badges, et comment on les obtient

Ils ne sont pas décoratifs. Ils ont été attribués en relisant tout ce qui a été écrit ici depuis 2024.

🐛 **Chasseur de bugs** — tu as signalé un défaut qui a été reproduit et corrigé.
💡 **Idée en ligne** — tu as proposé quelque chose qui tourne aujourd'hui sur le site.
💛 **Soutien** — tu as soutenu le projet.

Un message précis suffit : ce qui se passe, ce que tu attendais, et le lien du stuff. C'est tout.

## Le site est sans publicité

Et l'idée est que ça reste ainsi. Ce sont les dons qui paient le serveur : https://ko-fi.com/dofusfashionista

---

## Welcome

**Dofus Fashionista** builds an optimised set from your own constraints: AP, MP, resistances, the weight you give each stat. Dofus 3, beta, Dofus 2, Retro and Touch, in five languages.

**#bug-report** — something is broken. A share link to your build helps enormously.
**#suggestions** — an idea, a gap, or a game rule the tool gets wrong.

🐛 **Chasseur de bugs** — you reported a defect that was reproduced and fixed.
💡 **Idée en ligne** — you suggested something that runs on the site today.
💛 **Soutien** — you supported the project.

There is no advertising on the site, and the idea is to keep it that way."""


def main():
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass

    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument('--apply', action='store_true')
    args = parseur.parse_args()

    made = discord_api.session()
    existants = discord_api.channels(made, GUILD)

    print('channel: #%s  [%s]' % (
        CHANNEL, 'exists' if CHANNEL in existants else 'to create'))
    print('read-only for @everyone, pinned, placed first')
    print()
    print(MESSAGE)
    print()

    if not args.apply:
        print('dry run. Nothing was changed. Re-run with --apply.')
        return 0

    salon = existants.get(CHANNEL)
    if not salon:
        reponse = discord_api.write(
            made, 'POST', '/guilds/%s/channels' % GUILD,
            name=CHANNEL, type=0, position=0,
            topic='Où écrire quoi, et comment on obtient un badge.',
            # The guild id doubles as the @everyone role id.
            permission_overwrites=[{'id': GUILD, 'type': 0,
                                    'deny': str(SEND_MESSAGES)}])
        if not reponse.ok:
            print('  could not create the channel: %s %s'
                  % (reponse.status_code, reponse.text[:200]))
            return 1
        salon = reponse.json()['id']
        print('  created #%s' % CHANNEL)

    # The bot belongs to @everyone, so the deny above silences it too. A
    # named exception lets it write without reopening the channel to anyone.
    moi = discord_api.get(made, '/users/@me')
    ouverture = discord_api.write(
        made, 'PUT', '/channels/%s/permissions/%s' % (salon, moi['id']),
        type=1, allow=str(SEND_MESSAGES), deny='0')
    if not ouverture.ok:
        print('  could not grant myself write access: %s' % ouverture.status_code)

    envoi = discord_api.write(made, 'POST', '/channels/%s/messages' % salon,
                              content=MESSAGE)
    if not envoi.ok:
        print('  could not post: %s %s' % (envoi.status_code, envoi.text[:200]))
        return 1
    message_id = envoi.json()['id']
    print('  posted')

    epingle = discord_api.write(made, 'PUT', '/channels/%s/pins/%s'
                                % (salon, message_id))
    print('  pinned: %s' % ('ok' if epingle.ok else epingle.status_code))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
