"""A channel that tells a newcomer where to write and how a badge is earned.

The server had no orientation channel at all. Someone arriving found six
channels and no indication of what belongs where, and three coloured badges
with no way of knowing how anyone got one. A badge nobody knows how to earn
decorates; it does not invite.

One message per language rather than one message carrying all five: Discord
caps a message at 2000 characters, and five languages do not fit. It also
reads better -- a reader finds their own flag and stops.

The order is the audience's, not the server's. Google Analytics puts Spanish
first on the site (44% of clicks, ahead of French at 18% and Portuguese at
11%), while every message in this guild is French or English. The Spanish and
Brazilian players use the tool and do not come here; writing in their language
is the cheapest thing that could change that.

Read-only by design: it is a sign, not a conversation.

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
BOT = '1507755622295142460'

#: Discord permission bit for sending messages.
SEND_MESSAGES = 1 << 11

SITE = 'https://dofusfashionista.gg'
KOFI = 'https://ko-fi.com/dofusfashionista'

#: French first because that is what the guild speaks today, then the site's
#: real audience order. Each message stands alone: nobody should have to read
#: another language to understand this one.
MESSAGES = [
    ('fr', """## 🇫🇷 Bienvenue

**Dofus Fashionista** construit un stuff optimisé à partir de tes contraintes : PA, PM, résistances, et le poids que tu donnes à chaque statistique. Dofus 3, bêta, Dofus 2, Retro et Touch.
→ %(site)s

**Où écrire**
**#bug-report** — quelque chose ne marche pas. Joins le lien de partage de ton stuff : ça permet de reproduire en un clic.
**#suggestions** — une idée, un manque, ou une règle du jeu que l'outil modélise mal.
**#roadmap** — ce qui est prévu · **#dev-update** — ce qui vient de sortir.

**Les badges**
🐛 **Chasseur de bugs** — tu as signalé un défaut qui a été corrigé.
💡 **Idée en ligne** — tu as proposé quelque chose qui tourne aujourd'hui sur le site.
💛 **Soutien** — tu as soutenu le projet.

Ils sont attribués en relisant ce qui est écrit ici, pas distribués au hasard. Un message précis suffit : ce qui se passe, ce que tu attendais, et le lien.

Le site n'a aucune publicité et l'idée est que ça reste ainsi. Ce sont les dons qui paient le serveur : %(kofi)s"""),

    ('es', """## 🇪🇸 Bienvenido

**Dofus Fashionista** crea un equipamiento optimizado a partir de tus condiciones: PA, PM, resistencias y el peso que le das a cada característica. Dofus 3, beta, Dofus 2, Retro y Touch.
→ %(site)s

**Dónde escribir**
**#bug-report** — algo no funciona. Añade el enlace para compartir tu equipo: permite reproducir el fallo en un clic.
**#suggestions** — una idea, algo que falta, o una regla del juego que la herramienta modela mal.
**#roadmap** — lo que está previsto · **#dev-update** — lo que acaba de salir.

**Las insignias**
🐛 **Chasseur de bugs** — has avisado de un fallo que ha sido corregido.
💡 **Idée en ligne** — has propuesto algo que hoy funciona en la web.
💛 **Soutien** — has apoyado el proyecto.

Se conceden releyendo lo que se escribe aquí, no se reparten al azar. Basta con un mensaje preciso: qué ocurre, qué esperabas, y el enlace.

Puedes escribir en español, se te responderá. La web no tiene ninguna publicidad y la idea es que siga así: %(kofi)s"""),

    ('pt', """## 🇧🇷 Bem-vindo

**Dofus Fashionista** monta um equipamento otimizado a partir das tuas condições: PA, PM, resistências e o peso que dás a cada característica. Dofus 3, beta, Dofus 2, Retro e Touch.
→ %(site)s

**Onde escrever**
**#bug-report** — alguma coisa não funciona. Junta o link de partilha do teu equipamento: permite reproduzir com um clique.
**#suggestions** — uma ideia, algo em falta, ou uma regra do jogo que a ferramenta modela mal.
**#roadmap** — o que está previsto · **#dev-update** — o que acabou de sair.

**Os emblemas**
🐛 **Chasseur de bugs** — comunicaste um defeito que foi corrigido.
💡 **Idée en ligne** — sugeriste algo que hoje funciona no site.
💛 **Soutien** — apoiaste o projeto.

São atribuídos relendo o que se escreve aqui, não distribuídos ao acaso. Basta uma mensagem precisa: o que acontece, o que esperavas, e o link.

Podes escrever em português, terás resposta. O site não tem publicidade nenhuma e a ideia é que continue assim: %(kofi)s"""),

    ('en', """## 🇬🇧 Welcome

**Dofus Fashionista** builds an optimised set from your own constraints: AP, MP, resistances, and the weight you give each stat. Dofus 3, beta, Dofus 2, Retro and Touch.
→ %(site)s

**Where to write**
**#bug-report** — something is broken. Add the share link to your build: it makes it reproducible in one click.
**#suggestions** — an idea, a gap, or a game rule the tool gets wrong.
**#roadmap** — what is planned · **#dev-update** — what just shipped.

**The badges**
🐛 **Chasseur de bugs** — you reported a defect that was fixed.
💡 **Idée en ligne** — you suggested something that runs on the site today.
💛 **Soutien** — you supported the project.

They are handed out by re-reading what is written here, not at random. A precise message is enough: what happens, what you expected, and the link.

The site carries no advertising and the idea is to keep it that way. Donations are what pays for the server: %(kofi)s"""),

    ('de', """## 🇩🇪 Willkommen

**Dofus Fashionista** baut aus deinen Vorgaben ein optimiertes Set: AP, MP, Resistenzen und das Gewicht, das du jedem Wert gibst. Dofus 3, Beta, Dofus 2, Retro und Touch.
→ %(site)s

**Wo man schreibt**
**#bug-report** — etwas funktioniert nicht. Häng den Teilen-Link deines Sets an: damit lässt es sich mit einem Klick nachstellen.
**#suggestions** — eine Idee, eine Lücke, oder eine Spielregel, die das Werkzeug falsch abbildet.
**#roadmap** — was geplant ist · **#dev-update** — was gerade online ging.

**Die Abzeichen**
🐛 **Chasseur de bugs** — du hast einen Fehler gemeldet, der behoben wurde.
💡 **Idée en ligne** — du hast etwas vorgeschlagen, das heute auf der Seite läuft.
💛 **Soutien** — du hast das Projekt unterstützt.

Sie werden vergeben, indem hier nachgelesen wird, nicht nach Zufall. Eine genaue Nachricht genügt: was passiert, was du erwartet hast, und der Link.

Die Seite hat keinerlei Werbung, und das soll so bleiben. Spenden bezahlen den Server: %(kofi)s"""),
]


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

    rendus = [(langue, corps % {'site': SITE, 'kofi': KOFI})
              for langue, corps in MESSAGES]
    print('channel: #%s  [%s]' % (
        CHANNEL, 'exists' if CHANNEL in existants else 'to create'))
    for langue, corps in rendus:
        etat = 'ok' if len(corps) <= 2000 else 'TOO LONG'
        print('  %s  %4d characters  %s' % (langue, len(corps), etat))
    trop = [l for l, c in rendus if len(c) > 2000]
    if trop:
        print('Discord caps a message at 2000: %s' % ', '.join(trop))
        return 1

    if not args.apply:
        print('\ndry run. Nothing was changed. Re-run with --apply.')
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
            print('  could not create the channel: %s' % reponse.status_code)
            return 1
        salon = reponse.json()['id']
        print('  created #%s' % CHANNEL)

    # The bot belongs to @everyone, so the deny above silences it too. A named
    # exception lets it write without reopening the channel to anyone.
    discord_api.write(made, 'PUT', '/channels/%s/permissions/%s' % (salon, BOT),
                      type=1, allow=str(SEND_MESSAGES), deny='0')

    # Replace what this bot posted before, so re-running does not stack copies.
    # Only its own messages, never anyone else's.
    for m in discord_api.history(made, salon):
        if (m.get('author') or {}).get('id') == BOT:
            discord_api.write(made, 'DELETE',
                              '/channels/%s/messages/%s' % (salon, m['id']))

    for langue, corps in rendus:
        envoi = discord_api.write(made, 'POST', '/channels/%s/messages' % salon,
                                  content=corps)
        print('  %s : %s' % (langue, 'posted' if envoi.ok else envoi.status_code))
        if envoi.ok and langue == 'fr':
            discord_api.write(made, 'PUT', '/channels/%s/pins/%s'
                              % (salon, envoi.json()['id']))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
