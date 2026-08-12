# -*- coding: utf-8 -*-
"""Original, hand-written guide content for the Dofus Fashionista.

This is real editorial content (not scraped item data): walkthroughs and
explanations written for players, in the five site languages. It lives in a
plain data structure rather than the gettext catalogs because long-form
articles don't belong in .po files, and because every language is written by
hand so it reads naturally instead of like a machine translation.

Each guide: a slug and a per-language block with title, a short description
(used for the listing card + meta description), and an HTML body.
The body uses simple markup (h2/p/ul/li/a/strong) and links back into the tool
with root-relative URLs so the version namespace doesn't matter.
"""
from __future__ import annotations

ORDER = ['getting-started', 'beginner-mistakes', 'choosing-your-class', 'how-it-works', 'stats-explained', 'critical-hits', 'scrolls-and-characteristics', 'ap-mp-range-caps', 'tuning-your-weights', 'game-modes', 'reading-an-item', 'set-bonuses', 'dofus-and-trophies', 'understanding-your-solution', 'mono-vs-multi-element', 'resistance-explained', 'monster-weaknesses', 'vitality-and-hp', 'gearing-up', 'comparing-builds', 'forgemagie-planning', 'crafting-and-professions', 'prospecting-and-drops', 'transcendence-runes', 'versions-explained']


GUIDES = {
    # ------------------------------------------------------------------ #
    # Critical hits are a genuinely different SYSTEM per version: Retro (1.29)
    # uses the old 1/X fraction where Agility raises the rate, while the modern
    # game (Dofus 3, beta, Dofus 2, Touch) uses a flat percentage where Agility
    # does nothing. So this guide carries one content per system, selected from
    # the version the reader is on. Sources: DofuX (dofux.org) 1.29 crit
    # calculator (1/X + Agility) for Retro; official forums / Touch crit rework
    # (percentage, 50% cap) for modern.
    'critical-hits': {
        'published': '2026-07-22',
        'version_groups': {'retro': 'retro'},
        'i18n_by_group': {
            'modern': {
                'en': {
                    'title': 'Critical hits in modern Dofus: how they really work',
                    'desc': "In modern Dofus, crit is a percentage: spell base plus gear, capped at 50%, and Agility does nothing. How to build for critical hits.",
                    'lead': "In Dofus 3, the beta, Dofus 2 and Touch, critical hits run on percentages. Here is what actually drives your crit rate, and when to build for it.",
                    'body': '''
<h2>How critical hits work now</h2>
<p>In modern Dofus (Dofus 3, the beta, Dofus 2 and Touch), your critical hit rate is a <strong>percentage</strong>. Every spell and weapon has its own base crit chance, usually somewhere between 5% and 25%. Gear that gives +Critical Hits adds its percentage on top of that base, and the total is your chance to crit with that attack.</p>

<h2>Agility does not touch your crit rate</h2>
<p>This is the big difference from the old game: in modern Dofus, <strong>Agility has no effect on critical hits</strong>. Your crit rate comes only from the spell's base and your gear's +Critical Hits. Building Agility for crits is a Retro habit that does nothing here.</p>

<h2>The cap, and crit damage</h2>
<p>No matter how much +Critical Hits you stack, your chance is capped at <strong>50%</strong> per attack. Once you are there, more crit chance is wasted. Separately, the Critical Damage stat (the "+X on critical hits" you see on items) makes your crits hit harder but does <em>not</em> change how often they land. Chance and damage are two different stats.</p>

<h2>When to build for crits</h2>
<p>Crits are worth chasing when the spell's critical line adds a meaningful bonus and you can push the rate high enough to rely on it. A spell that gains little on a crit, or a build stuck at a low rate, is usually better served by flat damage or Power. In the Fashionista, weight Critical Hits when your key spells reward it, and check the spell before you commit.</p>

<p><em>Wondering if crits fit your build? <a href="/setup/">Weight them here.</a></em></p>
''',
                },
                'fr': {
                    'title': "Les coups critiques sur le Dofus moderne : comment ça marche",
                    'desc': "Sur le Dofus moderne, le critique est un pourcentage : base du sort plus stuff, plafonné à 50 %, et l'Agilité n'y fait rien. Comment build pour les critiques.",
                    'lead': "Sur Dofus 3, la bêta, Dofus 2 et Touch, les coups critiques tournent en pourcentages. Voici ce qui décide vraiment ton taux, et quand build pour.",
                    'body': '''
<h2>Comment marchent les coups critiques aujourd'hui</h2>
<p>Sur le Dofus moderne (Dofus 3, la bêta, Dofus 2 et Touch), ton taux de coup critique est un <strong>pourcentage</strong>. Chaque sort et chaque arme a sa propre chance de critique de base, en général entre 5 % et 25 %. Le stuff qui donne des +Coups Critiques ajoute son pourcentage par-dessus cette base, et le total est ta chance de critiquer avec cette attaque.</p>

<h2>L'Agilité ne touche pas ton taux de critique</h2>
<p>C'est la grande différence avec l'ancien jeu : sur le Dofus moderne, <strong>l'Agilité n'a aucun effet sur les coups critiques</strong>. Ton taux vient uniquement de la base du sort et des +Coups Critiques de ton stuff. Monter l'Agilité pour les critiques est un réflexe Rétro qui ne sert à rien ici.</p>

<h2>Le plafond, et les dommages critiques</h2>
<p>Peu importe combien de +Coups Critiques tu empiles, ta chance est plafonnée à <strong>50 %</strong> par attaque. Une fois à ce niveau, plus de taux de critique est gaspillé. À part ça, la stat Dommages Critiques (le « +X en cas de critique » sur les items) fait taper tes critiques plus fort mais ne change <em>pas</em> leur fréquence. Chance et dégâts sont deux stats différentes.</p>

<h2>Quand build pour les critiques</h2>
<p>Les critiques valent le coup quand la ligne critique du sort ajoute un vrai bonus et que tu peux monter le taux assez haut pour compter dessus. Un sort qui gagne peu en critique, ou un build coincé à un taux bas, est souvent mieux servi par des dommages fixes ou de la Puissance. Dans la Fashionista, pondère les Coups Critiques quand tes sorts clés le récompensent, et vérifie le sort avant de t'engager.</p>

<p><em>Tu te demandes si les critiques collent à ton build ? <a href="/setup/">Pondère-les ici.</a></em></p>
''',
                },
                'es': {
                    'title': "Los golpes críticos en el Dofus moderno: cómo funcionan",
                    'desc': "En el Dofus moderno, el crítico es un porcentaje: base del hechizo más equipo, con tope del 50 %, y la Agilidad no hace nada. Cómo construir para críticos.",
                    'lead': "En Dofus 3, la beta, Dofus 2 y Touch, los golpes críticos van por porcentajes. Esto es lo que decide de verdad tu tasa, y cuándo construir para ella.",
                    'body': '''
<h2>Cómo funcionan los críticos ahora</h2>
<p>En el Dofus moderno (Dofus 3, la beta, Dofus 2 y Touch), tu tasa de golpe crítico es un <strong>porcentaje</strong>. Cada hechizo y cada arma tiene su propia probabilidad de crítico base, normalmente entre el 5 % y el 25 %. El equipo que da +Golpes Críticos suma su porcentaje sobre esa base, y el total es tu probabilidad de criticar con ese ataque.</p>

<h2>La Agilidad no toca tu tasa de crítico</h2>
<p>Esta es la gran diferencia con el juego antiguo: en el Dofus moderno, <strong>la Agilidad no tiene ningún efecto sobre los golpes críticos</strong>. Tu tasa viene solo de la base del hechizo y de los +Golpes Críticos de tu equipo. Subir Agilidad para los críticos es un hábito de Retro que aquí no sirve de nada.</p>

<h2>El tope, y el daño crítico</h2>
<p>Por mucho +Golpes Críticos que acumules, tu probabilidad está limitada al <strong>50 %</strong> por ataque. Una vez ahí, más tasa de crítico se desperdicia. Aparte, la estadística Daño Crítico (el «+X en crítico» de los objetos) hace que tus críticos peguen más fuerte pero <em>no</em> cambia su frecuencia. Probabilidad y daño son dos estadísticas distintas.</p>

<h2>Cuándo construir para críticos</h2>
<p>Los críticos merecen la pena cuando la línea crítica del hechizo añade un bonus real y puedes subir la tasa lo suficiente como para depender de ella. Un hechizo que gana poco en crítico, o un build atascado en una tasa baja, suele estar mejor servido con daño fijo o Potencia. En la Fashionista, pondera los Golpes Críticos cuando tus hechizos clave lo recompensen, y revisa el hechizo antes de comprometerte.</p>

<p><em>¿Te preguntas si los críticos encajan en tu build? <a href="/setup/">Pondéralos aquí.</a></em></p>
''',
                },
                'pt': {
                    'title': "Os golpes críticos no Dofus moderno: como funcionam",
                    'desc': "No Dofus moderno, o crítico é uma porcentagem: base do feitiço mais equipamento, com teto de 50 %, e a Agilidade não faz nada. Como construir para críticos.",
                    'lead': "No Dofus 3, no beta, no Dofus 2 e no Touch, os golpes críticos funcionam por porcentagens. Aqui está o que decide sua taxa, e quando construir para ela.",
                    'body': '''
<h2>Como os críticos funcionam agora</h2>
<p>No Dofus moderno (Dofus 3, o beta, Dofus 2 e Touch), sua taxa de golpe crítico é uma <strong>porcentagem</strong>. Cada feitiço e cada arma tem sua própria chance de crítico base, geralmente entre 5 % e 25 %. O equipamento que dá +Golpes Críticos soma sua porcentagem sobre essa base, e o total é sua chance de critar com aquele ataque.</p>

<h2>A Agilidade não mexe na sua taxa de crítico</h2>
<p>Essa é a grande diferença em relação ao jogo antigo: no Dofus moderno, <strong>a Agilidade não tem nenhum efeito sobre os golpes críticos</strong>. Sua taxa vem só da base do feitiço e dos +Golpes Críticos do seu equipamento. Subir Agilidade para os críticos é um hábito de Retro que aqui não serve para nada.</p>

<h2>O teto, e o dano crítico</h2>
<p>Não importa quanto +Golpes Críticos você empilhe, sua chance é limitada a <strong>50 %</strong> por ataque. Uma vez lá, mais taxa de crítico é desperdiçada. À parte disso, o atributo Dano Crítico (o «+X no crítico» dos itens) faz seus críticos baterem mais forte mas <em>não</em> muda a frequência deles. Chance e dano são dois atributos diferentes.</p>

<h2>Quando construir para críticos</h2>
<p>Os críticos valem a pena quando a linha crítica do feitiço adiciona um bônus real e você consegue subir a taxa alto o bastante para contar com ela. Um feitiço que ganha pouco no crítico, ou um build preso numa taxa baixa, costuma ser melhor servido por dano fixo ou Potência. Na Fashionista, pondere os Golpes Críticos quando seus feitiços principais recompensarem, e confira o feitiço antes de se comprometer.</p>

<p><em>Será que os críticos combinam com seu build? <a href="/setup/">Pondere-os aqui.</a></em></p>
''',
                },
                'de': {
                    'title': "Kritische Treffer im modernen Dofus: wie sie wirklich funktionieren",
                    'desc': "Im modernen Dofus ist Kritisch ein Prozentwert: Zauber-Basis plus Ausrüstung, gedeckelt bei 50 %, und Flinkheit bringt nichts. So baust du auf Kritische.",
                    'lead': "In Dofus 3, der Beta, Dofus 2 und Touch laufen kritische Treffer über Prozente. Hier steht, was deine Kritrate wirklich treibt, und wann du darauf baust.",
                    'body': '''
<h2>Wie kritische Treffer heute funktionieren</h2>
<p>Im modernen Dofus (Dofus 3, die Beta, Dofus 2 und Touch) ist deine kritische Trefferrate ein <strong>Prozentwert</strong>. Jeder Zauber und jede Waffe hat eine eigene Basis-Kritchance, meist zwischen 5 % und 25 %. Ausrüstung mit +Kritische Treffer addiert ihren Prozentsatz auf diese Basis, und die Summe ist deine Chance, mit diesem Angriff kritisch zu treffen.</p>

<h2>Flinkheit berührt deine Kritrate nicht</h2>
<p>Das ist der große Unterschied zum alten Spiel: im modernen Dofus hat <strong>Flinkheit keinerlei Wirkung auf kritische Treffer</strong>. Deine Rate kommt allein aus der Zauber-Basis und den +Kritische Treffer deiner Ausrüstung. Flinkheit für Kritische zu steigern ist eine Retro-Gewohnheit, die hier nichts bringt.</p>

<h2>Die Deckelung, und der kritische Schaden</h2>
<p>Egal wie viel +Kritische Treffer du stapelst, deine Chance ist pro Angriff bei <strong>50 %</strong> gedeckelt. Ab da ist mehr Kritrate verschwendet. Davon getrennt lässt der Wert Kritischer Schaden (das „+X bei kritischem Treffer" auf Items) deine Kritischen härter treffen, ändert aber <em>nicht</em>, wie oft sie landen. Chance und Schaden sind zwei verschiedene Werte.</p>

<h2>Wann du auf Kritische baust</h2>
<p>Kritische lohnen sich, wenn die kritische Zeile des Zaubers einen echten Bonus gibt und du die Rate hoch genug bringst, um dich darauf zu verlassen. Ein Zauber, der beim Kritischen kaum gewinnt, oder ein Build mit niedriger Rate, fährt oft besser mit festem Schaden oder Kraft. Gewichte in der Fashionista Kritische Treffer, wenn deine Schlüsselzauber es belohnen, und prüfe den Zauber, bevor du dich festlegst.</p>

<p><em>Fragst du dich, ob Kritische zu deinem Build passen? <a href="/setup/">Gewichte sie hier.</a></em></p>
''',
                },
            },
            'retro': {
                'en': {
                    'title': 'Critical hits in Dofus Retro: the 1/X system',
                    'desc': "Dofus Retro (1.29) uses the old crit system: a 1/X fraction, capped at 1/2, and Agility raises your rate. How to build for critical hits.",
                    'lead': "Dofus Retro (1.29) keeps the classic crit system, and it works nothing like modern Dofus. Here is how your critical hit rate really works.",
                    'body': '''
<h2>How critical hits work in Retro</h2>
<p>Dofus Retro (1.29) uses the old system: your critical hit rate is a <strong>fraction, written 1/X</strong>. A weapon or spell listed at 1/30 crits once in thirty hits on average. The lower the X, the more often you crit, and gear and characteristics can push it down.</p>

<h2>Agility is your crit stat</h2>
<p>Here is the key Retro difference: <strong>Agility raises your critical hit rate</strong>. Investing in Agility lowers your crit fraction, so an Agility build crits noticeably more often. This is the opposite of modern Dofus, where Agility does nothing for crits. On Retro, if you want reliable crits, Agility is part of the plan alongside +Critical Hits gear.</p>

<h2>The cap, and crit damage</h2>
<p>Your crit rate cannot go better than <strong>1/2</strong> (a one-in-two chance), no matter how much Agility and gear you stack. Past that, more crit rate is wasted. The critical-damage bonus on gear makes your crits hit harder but does <em>not</em> change how often they land.</p>

<h2>When to build for crits</h2>
<p>On Retro, crits pay off when the extra critical damage is worth the Agility and gear you spend to reach a good rate. Some builds lean fully into Agility for both dodge and crits; others take crits as a bonus on top of a Strength or Chance build. In the Fashionista, weight Critical Hits (and Agility) when your weapon and spells reward the crit, and leave them low when they do not.</p>

<p><em>Building for Retro crits? <a href="/setup/">Set your weights here.</a></em></p>
''',
                },
                'fr': {
                    'title': "Les coups critiques sur Dofus Rétro : le système en 1/X",
                    'desc': "Dofus Rétro (1.29) garde l'ancien système : une fraction 1/X, plafonnée à 1/2, et l'Agilité monte ton taux. Comment build pour les coups critiques.",
                    'lead': "Dofus Rétro (1.29) garde le système de critique classique, et il ne marche pas du tout comme le Dofus moderne. Voici comment ton taux fonctionne vraiment.",
                    'body': '''
<h2>Comment marchent les critiques sur Rétro</h2>
<p>Dofus Rétro (1.29) utilise l'ancien système : ton taux de coup critique est une <strong>fraction, notée 1/X</strong>. Une arme ou un sort à 1/30 critique une fois sur trente en moyenne. Plus le X est petit, plus tu critiques souvent, et le stuff comme les caractéristiques peuvent le faire baisser.</p>

<h2>L'Agilité est ta stat de critique</h2>
<p>Voilà la différence clé du Rétro : <strong>l'Agilité monte ton taux de coup critique</strong>. Investir en Agilité baisse ta fraction de critique, donc un build Agilité critique nettement plus souvent. C'est l'inverse du Dofus moderne, où l'Agilité ne fait rien pour les critiques. Sur Rétro, si tu veux des critiques fiables, l'Agilité fait partie du plan avec le stuff +Coups Critiques.</p>

<h2>Le plafond, et les dommages critiques</h2>
<p>Ton taux de critique ne peut pas dépasser <strong>1/2</strong> (une chance sur deux), peu importe l'Agilité et le stuff que tu empiles. Au-delà, plus de taux est gaspillé. Le bonus de dommages critiques du stuff fait taper tes critiques plus fort mais ne change <em>pas</em> leur fréquence.</p>

<h2>Quand build pour les critiques</h2>
<p>Sur Rétro, les critiques paient quand le surplus de dégâts critiques vaut l'Agilité et le stuff dépensés pour atteindre un bon taux. Certains builds foncent à fond dans l'Agilité pour l'esquive et les critiques ; d'autres prennent les critiques en bonus sur un build Force ou Chance. Dans la Fashionista, pondère les Coups Critiques (et l'Agilité) quand ton arme et tes sorts récompensent le critique, et laisse-les bas sinon.</p>

<p><em>Tu build pour les critiques Rétro ? <a href="/setup/">Règle tes poids ici.</a></em></p>
''',
                },
                'es': {
                    'title': "Los golpes críticos en Dofus Retro: el sistema 1/X",
                    'desc': "Dofus Retro (1.29) mantiene el sistema antiguo: una fracción 1/X, con tope de 1/2, y la Agilidad sube tu tasa. Cómo construir para golpes críticos.",
                    'lead': "Dofus Retro (1.29) mantiene el sistema de crítico clásico, y no funciona para nada como el Dofus moderno. Así funciona de verdad tu tasa de crítico.",
                    'body': '''
<h2>Cómo funcionan los críticos en Retro</h2>
<p>Dofus Retro (1.29) usa el sistema antiguo: tu tasa de golpe crítico es una <strong>fracción, escrita 1/X</strong>. Un arma o un hechizo a 1/30 critica una vez de cada treinta de media. Cuanto más pequeño el X, más a menudo criticas, y tanto el equipo como las características pueden bajarlo.</p>

<h2>La Agilidad es tu estadística de crítico</h2>
<p>Esta es la diferencia clave de Retro: <strong>la Agilidad sube tu tasa de golpe crítico</strong>. Invertir en Agilidad baja tu fracción de crítico, así que un build de Agilidad critica bastante más a menudo. Es lo contrario del Dofus moderno, donde la Agilidad no hace nada por los críticos. En Retro, si quieres críticos fiables, la Agilidad es parte del plan junto al equipo +Golpes Críticos.</p>

<h2>El tope, y el daño crítico</h2>
<p>Tu tasa de crítico no puede pasar de <strong>1/2</strong> (una probabilidad entre dos), por mucha Agilidad y equipo que acumules. Más allá, la tasa de más se desperdicia. El bonus de daño crítico del equipo hace que tus críticos peguen más fuerte pero <em>no</em> cambia su frecuencia.</p>

<h2>Cuándo construir para críticos</h2>
<p>En Retro, los críticos valen la pena cuando el daño crítico extra compensa la Agilidad y el equipo que gastas para alcanzar una buena tasa. Algunos builds se lanzan de lleno a la Agilidad para esquiva y críticos; otros toman los críticos como un extra sobre un build de Fuerza o Suerte. En la Fashionista, pondera los Golpes Críticos (y la Agilidad) cuando tu arma y tus hechizos recompensen el crítico, y déjalos bajos si no.</p>

<p><em>¿Construyes para críticos en Retro? <a href="/setup/">Ajusta tus pesos aquí.</a></em></p>
''',
                },
                'pt': {
                    'title': "Os golpes críticos no Dofus Retro: o sistema 1/X",
                    'desc': "O Dofus Retro (1.29) mantém o sistema antigo: uma fração 1/X, com teto de 1/2, e a Agilidade aumenta sua taxa. Como construir para golpes críticos.",
                    'lead': "O Dofus Retro (1.29) mantém o sistema de crítico clássico, e ele não funciona nada como o Dofus moderno. É assim que sua taxa de crítico funciona de verdade.",
                    'body': '''
<h2>Como os críticos funcionam no Retro</h2>
<p>O Dofus Retro (1.29) usa o sistema antigo: sua taxa de golpe crítico é uma <strong>fração, escrita 1/X</strong>. Uma arma ou feitiço a 1/30 crita uma vez a cada trinta em média. Quanto menor o X, mais você crita, e tanto o equipamento quanto as características podem baixá-lo.</p>

<h2>A Agilidade é o seu atributo de crítico</h2>
<p>Essa é a diferença central do Retro: <strong>a Agilidade aumenta sua taxa de golpe crítico</strong>. Investir em Agilidade baixa sua fração de crítico, então um build de Agilidade crita bem mais vezes. É o contrário do Dofus moderno, onde a Agilidade não faz nada pelos críticos. No Retro, se você quer críticos confiáveis, a Agilidade faz parte do plano junto ao equipamento +Golpes Críticos.</p>

<h2>O teto, e o dano crítico</h2>
<p>Sua taxa de crítico não pode passar de <strong>1/2</strong> (uma chance em duas), não importa quanta Agilidade e equipamento você empilhe. Além disso, a taxa a mais é desperdiçada. O bônus de dano crítico do equipamento faz seus críticos baterem mais forte mas <em>não</em> muda a frequência deles.</p>

<h2>Quando construir para críticos</h2>
<p>No Retro, os críticos valem a pena quando o dano crítico extra compensa a Agilidade e o equipamento que você gasta para alcançar uma boa taxa. Alguns builds vão fundo na Agilidade para esquiva e críticos; outros pegam os críticos como um extra sobre um build de Força ou Sorte. Na Fashionista, pondere os Golpes Críticos (e a Agilidade) quando sua arma e seus feitiços recompensarem o crítico, e deixe baixos caso contrário.</p>

<p><em>Construindo para críticos no Retro? <a href="/setup/">Ajuste seus pesos aqui.</a></em></p>
''',
                },
                'de': {
                    'title': "Kritische Treffer in Dofus Retro: das 1/X-System",
                    'desc': "Dofus Retro (1.29) behält das alte Kritsystem: ein Bruch 1/X, gedeckelt bei 1/2, und Flinkheit hebt deine Rate. So baust du auf kritische Treffer.",
                    'lead': "Dofus Retro (1.29) behält das klassische Kritsystem, und es funktioniert ganz anders als das moderne Dofus. So funktioniert deine Kritrate wirklich.",
                    'body': '''
<h2>Wie kritische Treffer im Retro funktionieren</h2>
<p>Dofus Retro (1.29) nutzt das alte System: deine kritische Trefferrate ist ein <strong>Bruch, geschrieben 1/X</strong>. Eine Waffe oder ein Zauber mit 1/30 trifft im Schnitt einmal in dreißig kritisch. Je kleiner das X, desto öfter kritierst du, und sowohl Ausrüstung als auch Eigenschaften können es senken.</p>

<h2>Flinkheit ist dein Kritwert</h2>
<p>Das ist der zentrale Retro-Unterschied: <strong>Flinkheit hebt deine kritische Trefferrate</strong>. In Flinkheit zu investieren senkt deinen Kritbruch, also kritiert ein Flinkheits-Build deutlich öfter. Das ist das Gegenteil vom modernen Dofus, wo Flinkheit nichts für Kritische tut. Im Retro gehört Flinkheit zum Plan, zusammen mit +Kritische Treffer aus der Ausrüstung, wenn du zuverlässige Kritische willst.</p>

<h2>Die Deckelung, und der kritische Schaden</h2>
<p>Deine Kritrate kann nicht besser als <strong>1/2</strong> werden (eine Chance von zwei), egal wie viel Flinkheit und Ausrüstung du stapelst. Darüber hinaus ist mehr Rate verschwendet. Der kritische Schadensbonus der Ausrüstung lässt deine Kritischen härter treffen, ändert aber <em>nicht</em>, wie oft sie landen.</p>

<h2>Wann du auf Kritische baust</h2>
<p>Im Retro lohnen sich Kritische, wenn der zusätzliche kritische Schaden die Flinkheit und Ausrüstung wert ist, die du für eine gute Rate ausgibst. Manche Builds setzen voll auf Flinkheit für Ausweichen und Kritische; andere nehmen Kritische als Bonus auf einem Stärke- oder Glücks-Build mit. Gewichte in der Fashionista Kritische Treffer (und Flinkheit), wenn deine Waffe und Zauber den Kritischen belohnen, und lass sie sonst niedrig.</p>

<p><em>Baust du auf Retro-Kritische? <a href="/setup/">Stell hier deine Gewichte ein.</a></em></p>
''',
                },
            },
        },
    },

    # ------------------------------------------------------------------ #
    'vitality-and-hp': {
        'published': '2026-07-22',
        'i18n': {
            'en': {
                'title': 'How much Vitality (HP) do you really need?',
                'desc': "Vitality is the cheapest stat and pure HP, but more is not always better. How to think about HP, the tradeoff it hides, and when to stop stacking it.",
                'lead': "Vitality is the cheapest stat in the game and turns straight into HP, but piling it on is a classic trap. Here is how much you actually need.",
                'body': '''
<h2>What Vitality actually gives you</h2>
<p>Vitality is the simplest stat in Dofus: <strong>one point of Vitality is one hit point</strong>, in every version. It is also the cheapest characteristic to raise, so it is easy to pour points and scrolls into it and watch your HP bar balloon. That is exactly why it needs a second look: cheap and simple does not mean free.</p>

<h2>The hidden tradeoff</h2>
<p>Every point you spend on Vitality is a point you did not spend on damage, resistance or your element. A thousand extra HP you never needed is a thousand points of damage you gave up. HP keeps you alive, but it does not help you win faster, and a fight you drag out is a fight where you take more hits. The goal is enough HP to survive the content you run, not the biggest number possible.</p>

<h2>HP is a buffer, resistance is a shield</h2>
<p>Raw HP is a flat buffer: 3000 HP soaks the same damage whether the hit is big or small. Resistance is different: it cuts a percentage off every hit, so it scales with how hard you are being hit. In tough fights and PvP, a point of resistance often protects you more than a point of HP. A healthy build usually wants both, weighted toward resistance when the incoming damage is high, and toward HP when you just need a bigger cushion.</p>

<h2>How much, and how to set it</h2>
<p>For farming and easy PvM, a modest HP pool is plenty; spend the rest on killing speed. For hard dungeons and PvP, you want a real buffer, but paired with resistance, not instead of it. In the Fashionista, the clean way to handle it is a <strong>minimum</strong>: set the HP floor you want and let the optimizer meet it, then weight vitality low so it does not chase HP you never asked for. That way every extra point goes where it actually changes the fight.</p>

<p><em>Not sure where your HP should land? <a href="/setup/">Set a vitality floor here.</a></em></p>
''',
            },
            'fr': {
                'title': 'De combien de Vitalité (PV) as-tu vraiment besoin ?',
                'desc': "La Vitalité est la stat la moins chère et du PV pur, mais plus n'est pas toujours mieux. Comment penser tes PV et quand arrêter d'en empiler.",
                'lead': "La Vitalité est la caractéristique la moins chère du jeu et se transforme directement en PV, mais en empiler à outrance est un piège classique. Voici ce qu'il te faut vraiment.",
                'body': '''
<h2>Ce que donne vraiment la Vitalité</h2>
<p>La Vitalité est la stat la plus simple de Dofus : <strong>un point de Vitalité, c'est un point de vie</strong>, dans toutes les versions. C'est aussi la caractéristique la moins chère à monter, donc c'est facile d'y verser des points et des parchemins et de voir sa barre de PV gonfler. C'est justement pour ça qu'elle mérite un second regard : pas chère et simple ne veut pas dire gratuite.</p>

<h2>Le compromis caché</h2>
<p>Chaque point mis en Vitalité est un point que tu n'as pas mis en dégâts, en résistance ou dans ton élément. Mille PV en trop dont tu n'avais pas besoin, ce sont mille points de dégâts abandonnés. Les PV te gardent en vie, mais ils ne t'aident pas à gagner plus vite, et un combat qui traîne est un combat où tu prends plus de coups. Le but, c'est assez de PV pour survivre au contenu que tu fais, pas le plus gros chiffre possible.</p>

<h2>Les PV sont un tampon, la résistance un bouclier</h2>
<p>Les PV bruts sont un tampon fixe : 3000 PV encaissent la même chose que le coup soit gros ou petit. La résistance, c'est différent : elle retire un pourcentage à chaque coup, donc elle scale avec la force des coups que tu reçois. Dans les combats velus et en PvP, un point de résistance te protège souvent plus qu'un point de PV. Un build sain veut généralement les deux, penché vers la résistance quand les dégâts entrants sont élevés, et vers les PV quand tu as juste besoin d'un plus gros matelas.</p>

<h2>Combien, et comment le régler</h2>
<p>Pour le farm et le PvM tranquille, un réservoir de PV modeste suffit largement ; mets le reste dans la vitesse de kill. Pour les donjons durs et le PvP, tu veux un vrai matelas, mais couplé à de la résistance, pas à la place. Dans la Fashionista, la façon propre de gérer ça, c'est un <strong>minimum</strong> : fixe le plancher de PV que tu veux, laisse l'optimiseur l'atteindre, puis pondère la vitalité bas pour qu'elle ne coure pas après des PV que t'as pas demandés. Comme ça, chaque point en trop va là où il change vraiment le combat.</p>

<p><em>Tu ne sais pas où placer tes PV ? <a href="/setup/">Fixe un plancher de vitalité ici.</a></em></p>
''',
            },
            'es': {
                'title': '¿Cuánta Vitalidad (PdV) necesitas de verdad?',
                'desc': "La Vitalidad es la estadística más barata y PdV puro, pero más no siempre es mejor. Cómo pensar tus PdV, la trampa que esconden, y cuándo dejar de acumularla.",
                'lead': "La Vitalidad es la característica más barata del juego y se convierte directamente en PdV, pero acumularla sin freno es una trampa clásica. Aquí está lo que de verdad necesitas.",
                'body': '''
<h2>Qué te da de verdad la Vitalidad</h2>
<p>La Vitalidad es la estadística más simple de Dofus: <strong>un punto de Vitalidad es un punto de vida</strong>, en todas las versiones. También es la característica más barata de subir, así que es fácil verter puntos y pergaminos en ella y ver tu barra de PdV inflarse. Justo por eso merece una segunda mirada: barata y simple no significa gratis.</p>

<h2>El sacrificio oculto</h2>
<p>Cada punto que pones en Vitalidad es un punto que no pusiste en daño, resistencia o tu elemento. Mil PdV de más que no necesitabas son mil puntos de daño que dejaste ir. Los PdV te mantienen vivo, pero no te ayudan a ganar más rápido, y un combate que se alarga es un combate donde recibes más golpes. El objetivo son suficientes PdV para sobrevivir al contenido que haces, no el número más grande posible.</p>

<h2>Los PdV son un colchón, la resistencia un escudo</h2>
<p>Los PdV puros son un colchón fijo: 3000 PdV aguantan lo mismo sea el golpe grande o pequeño. La resistencia es distinta: quita un porcentaje a cada golpe, así que escala con la fuerza de lo que recibes. En combates duros y en PvP, un punto de resistencia suele protegerte más que un punto de PdV. Un build sano normalmente quiere ambos, inclinado hacia la resistencia cuando el daño entrante es alto, y hacia los PdV cuando solo necesitas un colchón más grande.</p>

<h2>Cuánta, y cómo ajustarla</h2>
<p>Para farmear y PvM tranquilo, una reserva de PdV modesta sobra; pon el resto en velocidad de kill. Para mazmorras duras y PvP, quieres un colchón real, pero junto a resistencia, no en su lugar. En la Fashionista, la forma limpia de manejarlo es un <strong>mínimo</strong>: fija el suelo de PdV que quieres, deja que el optimizador lo alcance, y luego pondera la vitalidad baja para que no persiga PdV que no pediste. Así, cada punto de más va donde de verdad cambia el combate.</p>

<p><em>¿No sabes dónde dejar tus PdV? <a href="/setup/">Fija un suelo de vitalidad aquí.</a></em></p>
''',
            },
            'pt': {
                'title': 'De quanta Vitalidade (PV) você precisa de verdade?',
                'desc': "A Vitalidade é o atributo mais barato e PV puro, mas mais nem sempre é melhor. Como pensar seus PV, a armadilha que eles escondem, e quando parar de acumular.",
                'lead': "A Vitalidade é o atributo mais barato do jogo e vira PV diretamente, mas empilhá-la sem freio é uma armadilha clássica. Aqui está o que você realmente precisa.",
                'body': '''
<h2>O que a Vitalidade realmente dá</h2>
<p>A Vitalidade é o atributo mais simples de Dofus: <strong>um ponto de Vitalidade é um ponto de vida</strong>, em todas as versões. Também é o atributo mais barato de subir, então é fácil despejar pontos e pergaminhos nela e ver sua barra de PV inflar. É justamente por isso que ela merece um segundo olhar: barata e simples não quer dizer de graça.</p>

<h2>A troca escondida</h2>
<p>Cada ponto que você põe em Vitalidade é um ponto que não pôs em dano, resistência ou no seu elemento. Mil PV a mais de que você não precisava são mil pontos de dano que você abriu mão. Os PV te mantêm vivo, mas não te ajudam a ganhar mais rápido, e um combate que se arrasta é um combate onde você toma mais golpes. O objetivo é PV suficiente para sobreviver ao conteúdo que você faz, não o maior número possível.</p>

<h2>PV é um colchão, resistência é um escudo</h2>
<p>PV puro é um colchão fixo: 3000 PV aguentam a mesma coisa seja o golpe grande ou pequeno. A resistência é diferente: tira uma porcentagem de cada golpe, então escala com a força do que você recebe. Em combates difíceis e no PvP, um ponto de resistência costuma te proteger mais que um ponto de PV. Um build saudável geralmente quer os dois, pendendo para a resistência quando o dano recebido é alto, e para os PV quando você só precisa de um colchão maior.</p>

<h2>Quanta, e como ajustar</h2>
<p>Para farm e PvM tranquilo, uma reserva de PV modesta já basta; ponha o resto na velocidade de kill. Para masmorras difíceis e PvP, você quer um colchão de verdade, mas junto com resistência, não no lugar dela. Na Fashionista, o jeito limpo de lidar com isso é um <strong>mínimo</strong>: fixe o piso de PV que você quer, deixe o otimizador alcançá-lo, e depois pondere a vitalidade baixa para que ela não persiga PV que você não pediu. Assim, cada ponto a mais vai onde de fato muda o combate.</p>

<p><em>Não sabe onde deixar seus PV? <a href="/setup/">Fixe um piso de vitalidade aqui.</a></em></p>
''',
            },
            'de': {
                'title': 'Wie viel Vitalität (LP) brauchst du wirklich?',
                'desc': "Vitalität ist der billigste Wert und pure LP, aber mehr ist nicht immer besser. Wie du über LP nachdenkst und wann du aufhörst zu stapeln.",
                'lead': "Vitalität ist der billigste Wert im Spiel und wird direkt zu LP, aber sie hemmungslos zu stapeln ist eine klassische Falle. Hier steht, wie viel du wirklich brauchst.",
                'body': '''
<h2>Was Vitalität dir wirklich gibt</h2>
<p>Vitalität ist der einfachste Wert in Dofus: <strong>ein Punkt Vitalität ist ein Lebenspunkt</strong>, in jeder Version. Sie ist auch die billigste Eigenschaft zum Steigern, also ist es leicht, Punkte und Schriftrollen hineinzukippen und die LP-Leiste anschwellen zu sehen. Genau deshalb lohnt ein zweiter Blick: billig und einfach heißt nicht kostenlos.</p>

<h2>Die versteckte Abwägung</h2>
<p>Jeder Punkt in Vitalität ist ein Punkt, den du nicht in Schaden, Resistenz oder dein Element gesteckt hast. Tausend überschüssige LP, die du nie gebraucht hast, sind tausend Schadenspunkte, die du aufgegeben hast. LP halten dich am Leben, aber sie helfen dir nicht, schneller zu gewinnen, und ein Kampf, der sich zieht, ist ein Kampf, in dem du mehr Treffer kassierst. Das Ziel sind genug LP, um den Content zu überstehen, den du spielst, nicht die größtmögliche Zahl.</p>

<h2>LP sind ein Puffer, Resistenz ist ein Schild</h2>
<p>Rohe LP sind ein fester Puffer: 3000 LP schlucken dasselbe, ob der Treffer groß oder klein ist. Resistenz ist anders: sie nimmt jedem Treffer einen Prozentsatz weg, also skaliert sie damit, wie hart du getroffen wirst. In harten Kämpfen und im PvP schützt dich ein Punkt Resistenz oft mehr als ein Punkt LP. Ein gesunder Build will meist beides, mit Neigung zur Resistenz, wenn der eingehende Schaden hoch ist, und zu LP, wenn du einfach ein größeres Polster brauchst.</p>

<h2>Wie viel, und wie du es einstellst</h2>
<p>Zum Farmen und für lockeres PvM reicht ein bescheidener LP-Vorrat locker; steck den Rest in Tötungsgeschwindigkeit. Für harte Dungeons und PvP willst du ein echtes Polster, aber gepaart mit Resistenz, nicht statt ihr. In der Fashionista ist der saubere Weg ein <strong>Minimum</strong>: leg den LP-Boden fest, den du willst, lass den Optimierer ihn erreichen, und gewichte Vitalität dann niedrig, damit sie keinen LP hinterherjagt, den du nie verlangt hast. So geht jeder zusätzliche Punkt dorthin, wo er den Kampf wirklich verändert.</p>

<p><em>Unsicher, wo deine LP landen sollen? <a href="/setup/">Leg hier einen Vitalitäts-Boden fest.</a></em></p>
''',
            },
        },
    },

    # ------------------------------------------------------------------ #
    'prospecting-and-drops': {
        'published': '2026-07-22',
        'i18n': {
            'en': {
                'title': 'Prospecting and drop rates: how to actually get the loot',
                'desc': "Every drop rate you see is at 100 prospecting. Here is how it scales your real odds, where to get it, and when it is worth building for.",
                'lead': "Every drop rate in the encyclopedia is measured at 100 prospecting. Here is how it scales your real odds, where it comes from, and when to build for it.",
                'body': '''
<h2>What prospecting actually does</h2>
<p>Prospecting (PP) is the stat that decides your chance to drop an item or resource from a monster. Every character starts at <strong>100 prospecting</strong>, and that is the baseline every drop rate is quoted at. When the <a href="/encyclopedia/">encyclopedia</a> says an item drops at 1%, that is the chance at 100 PP. Prospecting also raises the Kamas monsters drop, so it pays for itself while you farm.</p>

<h2>How it scales your real odds</h2>
<p>Drop chance scales linearly with prospecting: <strong>your chance = the base rate times your PP divided by 100</strong>. So 200 PP doubles every drop rate on the page, 300 PP triples it, and so on. A 1% item becomes 2% at 200 PP. That is why dedicated farmers stack prospecting: it multiplies every drop in the fight at once, not just one.</p>

<h2>Where prospecting comes from</h2>
<p>Every character has a base of 100, and the rest comes from gear: rings, cloaks, some sets and Dofus all carry prospecting, and a focused farming set can push well past 1000 PP. In the Fashionista, Prospecting is a stat you can weight like any other: crank it for a farming build, and leave it at zero when you are building to fight so the optimizer spends those slots on damage or survival instead.</p>

<h2>The catches worth knowing</h2>
<p>A few rules shape how much prospecting helps. On modern Dofus, if you and the monster are more than 50 levels apart, prospecting stops counting, so heavily over-leveling a zone throws your farming edge away. In a group, drops are split among the party, so it helps to bring at least one strong prospector along. Temporary boosts like the Almanax, challenges and seasonal events multiply your base rate on top of prospecting. Dofus Retro keeps the classic behavior, without the modern level-gap rule. Whatever the version, the encyclopedia rate is your starting point and your prospecting does the rest.</p>

<p><em>Building a farmer? <a href="/setup/">Weight prospecting here.</a></em></p>
''',
            },
            'fr': {
                'title': 'Prospection et taux de drop : comment vraiment obtenir le butin',
                'desc': "Chaque taux de drop affiché est donné à 100 de prospection. Voici comment elle change tes vraies chances, d'où elle vient, et quand la monter.",
                'lead': "Chaque taux de drop de l'encyclopédie est mesuré à 100 de prospection. Voici comment elle change tes vraies chances, d'où elle vient, et quand la monter.",
                'body': '''
<h2>Ce que fait vraiment la prospection</h2>
<p>La prospection (PP) est la stat qui décide de ta chance de dropper un objet ou une ressource sur un monstre. Chaque personnage démarre à <strong>100 de prospection</strong>, et c'est la base à laquelle tous les taux de drop sont donnés. Quand l'<a href="/encyclopedia/">encyclopédie</a> dit qu'un objet drop à 1%, c'est la chance à 100 PP. La prospection augmente aussi les Kamas lâchés par les monstres, donc elle se rentabilise pendant que tu farmes.</p>

<h2>Comment elle change tes vraies chances</h2>
<p>La chance de drop est linéaire avec la prospection : <strong>ta chance = le taux de base fois ta PP divisée par 100</strong>. Donc 200 PP double tous les taux de la page, 300 PP les triple, et ainsi de suite. Un objet à 1% passe à 2% avec 200 PP. C'est pour ça que les farmeurs dédiés empilent la prospection : elle multiplie tous les drops du combat d'un coup, pas juste un.</p>

<h2>D'où vient la prospection</h2>
<p>Chaque personnage a une base de 100, et le reste vient du stuff : anneaux, capes, certaines panoplies et Dofus portent tous de la prospection, et un set de farm concentré peut dépasser largement 1000 PP. Dans la Fashionista, la Prospection est une stat que tu pondères comme les autres : monte-la à fond pour un build de farm, et laisse-la à zéro quand tu construis pour taper, pour que l'optimiseur dépense ces emplacements en dégâts ou en survie.</p>

<h2>Les pièges à connaître</h2>
<p>Quelques règles encadrent l'effet de la prospection. Sur le Dofus moderne, si toi et le monstre avez plus de 50 niveaux d'écart, la prospection ne compte plus : sur-monter en niveau une zone jette ton avantage de farm à la poubelle. En groupe, les drops se répartissent sur l'équipe, donc ça aide d'emmener au moins un bon prospecteur. Les boosts temporaires comme l'Almanax, les challenges et les événements multiplient ton taux de base par-dessus la prospection. Dofus Rétro garde le comportement classique, sans la règle d'écart de niveau moderne. Peu importe la version, le taux de l'encyclopédie est ton point de départ, et ta prospection fait le reste.</p>

<p><em>Tu montes un farmeur ? <a href="/setup/">Pondère la prospection ici.</a></em></p>
''',
            },
            'es': {
                'title': 'Prospección y tasas de drop: cómo conseguir el botín de verdad',
                'desc': "Cada tasa de drop que ves es a 100 de prospección. Aquí tienes cómo cambia tus probabilidades reales, de dónde sale, y cuándo subirla.",
                'lead': "Cada tasa de drop de la enciclopedia se mide a 100 de prospección. Aquí tienes cómo cambia tus probabilidades reales, de dónde sale, y cuándo subirla.",
                'body': '''
<h2>Qué hace de verdad la prospección</h2>
<p>La prospección (PP) es la estadística que decide tu probabilidad de soltar un objeto o recurso de un monstruo. Cada personaje empieza con <strong>100 de prospección</strong>, y esa es la base a la que se dan todas las tasas de drop. Cuando la <a href="/encyclopedia/">enciclopedia</a> dice que un objeto cae al 1%, esa es la probabilidad a 100 PP. La prospección también sube los Kamas que sueltan los monstruos, así que se rentabiliza mientras farmeas.</p>

<h2>Cómo cambia tus probabilidades reales</h2>
<p>La probabilidad de drop es lineal con la prospección: <strong>tu probabilidad = la tasa base por tu PP dividida entre 100</strong>. Así que 200 PP duplica todas las tasas de la página, 300 PP las triplica, y así. Un objeto al 1% pasa al 2% con 200 PP. Por eso los farmeros dedicados acumulan prospección: multiplica todos los drops del combate a la vez, no solo uno.</p>

<h2>De dónde sale la prospección</h2>
<p>Cada personaje tiene una base de 100, y el resto viene del equipo: anillos, capas, algunos conjuntos y Dofus llevan prospección, y un set de farmeo concentrado puede pasar de largo los 1000 PP. En la Fashionista, la Prospección es una estadística que ponderas como las demás: súbela al máximo para un build de farmeo, y déjala a cero cuando construyes para pegar, para que el optimizador gaste esos huecos en daño o supervivencia.</p>

<h2>Los detalles que conviene saber</h2>
<p>Unas cuantas reglas moldean cuánto ayuda la prospección. En el Dofus moderno, si tú y el monstruo tenéis más de 50 niveles de diferencia, la prospección deja de contar, así que sobrepasar de nivel una zona tira tu ventaja de farmeo. En grupo, los drops se reparten por el equipo, así que ayuda llevar al menos un buen prospector. Los boosts temporales como el Almanax, los retos y los eventos multiplican tu tasa base por encima de la prospección. Dofus Retro mantiene el comportamiento clásico, sin la regla moderna de diferencia de nivel. Sea cual sea la versión, la tasa de la enciclopedia es tu punto de partida, y tu prospección hace el resto.</p>

<p><em>¿Montas un farmero? <a href="/setup/">Pondera la prospección aquí.</a></em></p>
''',
            },
            'pt': {
                'title': 'Prospecção e taxas de drop: como conseguir o loot de verdade',
                'desc': "Cada taxa de drop que você vê é a 100 de prospecção. Aqui está como ela muda suas chances reais, de onde vem, e quando subir.",
                'lead': "Cada taxa de drop da enciclopédia é medida a 100 de prospecção. Aqui está como ela muda suas chances reais, de onde vem, e quando subir.",
                'body': '''
<h2>O que a prospecção faz de verdade</h2>
<p>A prospecção (PP) é o atributo que decide sua chance de dropar um item ou recurso de um monstro. Cada personagem começa com <strong>100 de prospecção</strong>, e essa é a base em que todas as taxas de drop são dadas. Quando a <a href="/encyclopedia/">enciclopédia</a> diz que um item cai a 1%, essa é a chance a 100 PP. A prospecção também aumenta os Kamas que os monstros soltam, então ela se paga enquanto você farma.</p>

<h2>Como ela muda suas chances reais</h2>
<p>A chance de drop é linear com a prospecção: <strong>sua chance = a taxa base vezes sua PP dividida por 100</strong>. Então 200 PP dobra todas as taxas da página, 300 PP triplica, e assim por diante. Um item a 1% vira 2% com 200 PP. É por isso que os farmadores dedicados empilham prospecção: ela multiplica todos os drops do combate de uma vez, não só um.</p>

<h2>De onde vem a prospecção</h2>
<p>Cada personagem tem uma base de 100, e o resto vem do equipamento: anéis, capas, alguns conjuntos e Dofus carregam prospecção, e um set de farm concentrado pode passar bem dos 1000 PP. Na Fashionista, a Prospecção é um atributo que você pondera como os outros: bote no máximo para um build de farm, e deixe em zero quando você constrói para bater, para que o otimizador gaste esses espaços em dano ou sobrevivência.</p>

<h2>As pegadinhas que vale saber</h2>
<p>Algumas regras moldam o quanto a prospecção ajuda. No Dofus moderno, se você e o monstro têm mais de 50 níveis de diferença, a prospecção para de contar, então passar muito do nível de uma zona joga fora sua vantagem de farm. Em grupo, os drops se distribuem pela equipe, então ajuda levar pelo menos um bom prospector. Os boosts temporários como o Almanax, os desafios e os eventos multiplicam sua taxa base por cima da prospecção. O Dofus Retro mantém o comportamento clássico, sem a regra moderna de diferença de nível. Seja qual for a versão, a taxa da enciclopédia é seu ponto de partida, e sua prospecção faz o resto.</p>

<p><em>Montando um farmador? <a href="/setup/">Pondere a prospecção aqui.</a></em></p>
''',
            },
            'de': {
                'title': 'Prospektion und Drop-Raten: wie du die Beute wirklich bekommst',
                'desc': "Jede Drop-Rate, die du siehst, gilt bei 100 Prospektion. Hier steht, wie sie deine echten Chancen skaliert, woher sie kommt und wann sie sich lohnt.",
                'lead': "Jede Drop-Rate in der Enzyklopädie gilt bei 100 Prospektion. Hier steht, wie sie deine echten Chancen skaliert, woher sie kommt und wann sie sich lohnt.",
                'body': '''
<h2>Was Prospektion wirklich macht</h2>
<p>Prospektion (PP) ist der Wert, der deine Chance bestimmt, einen Gegenstand oder eine Ressource von einem Monster zu droppen. Jede Figur startet mit <strong>100 Prospektion</strong>, und das ist die Basis, auf die sich jede Drop-Rate bezieht. Wenn die <a href="/encyclopedia/">Enzyklopädie</a> sagt, ein Gegenstand droppt zu 1%, ist das die Chance bei 100 PP. Prospektion erhöht auch die Kamas, die Monster fallen lassen, also zahlt sie sich beim Farmen von selbst aus.</p>

<h2>Wie sie deine echten Chancen skaliert</h2>
<p>Die Drop-Chance skaliert linear mit der Prospektion: <strong>deine Chance = die Basisrate mal deine PP geteilt durch 100</strong>. Also verdoppelt 200 PP jede Rate auf der Seite, 300 PP verdreifacht sie, und so weiter. Ein Gegenstand mit 1% wird bei 200 PP zu 2%. Deshalb stapeln dedizierte Farmer Prospektion: sie vervielfacht alle Drops des Kampfes auf einmal, nicht nur einen.</p>

<h2>Woher Prospektion kommt</h2>
<p>Jede Figur hat eine Basis von 100, und der Rest kommt von der Ausrüstung: Ringe, Umhänge, manche Sets und Dofus tragen Prospektion, und ein gezieltes Farm-Set kann deutlich über 1000 PP kommen. In der Fashionista ist Prospektion ein Wert, den du wie jeden anderen gewichtest: dreh ihn hoch für einen Farm-Build, und lass ihn bei null, wenn du zum Kämpfen baust, damit der Optimierer diese Plätze in Schaden oder Überleben steckt.</p>

<h2>Die Fallstricke, die du kennen solltest</h2>
<p>Ein paar Regeln bestimmen, wie viel Prospektion bringt. Im modernen Dofus zählt Prospektion nicht mehr, wenn du und das Monster mehr als 50 Stufen auseinander liegt, also wirft starkes Überleveln einer Zone deinen Farm-Vorteil weg. In einer Gruppe verteilen sich die Drops auf das Team, also hilft es, mindestens einen starken Prospektor dabeizuhaben. Zeitweise Boni wie der Almanax, Herausforderungen und saisonale Events vervielfachen deine Basisrate zusätzlich zur Prospektion. Dofus Retro behält das klassische Verhalten, ohne die moderne Stufen-Abstands-Regel. Egal welche Version, die Rate der Enzyklopädie ist dein Startpunkt, und deine Prospektion macht den Rest.</p>

<p><em>Baust du einen Farmer? <a href="/setup/">Gewichte hier die Prospektion.</a></em></p>
''',
            },
        },
    },

    # ------------------------------------------------------------------ #
    'set-bonuses': {
        'published': '2026-07-22',
        'i18n': {
            'en': {
                'title': 'Set bonuses: how panoplies power up your build',
                'desc': "Wear several items from the same set and you unlock bonus stats that grow with each piece. How set bonuses work, and when to chase a full set.",
                'lead': "Wear several items from the same set and you unlock bonus stats that grow with each piece. Here's how they work, and when a full set beats mixing.",
                'body': '''
<h2>What a set bonus actually is</h2>
<p>A set (panoply) is a group of items designed to be worn together. Equip two or more pieces of the same set and the game hands you <strong>bonus stats on top of the items themselves</strong>. Those bonuses are free value: you get them just for wearing pieces that already occupy your slots. It is why sets are the backbone of most builds.</p>

<h2>More pieces, bigger bonus, less freedom</h2>
<p>Set bonuses scale with the number of pieces you wear: two items give a small bonus, and it grows at three, four, five and beyond, usually jumping hard on the last piece or two. The catch is the tradeoff. Every slot you commit to a set is a slot you cannot fill with a better standalone item. A full set can be amazing, or it can force weak pieces just to reach the top bonus. The sweet spot is often a <strong>partial set</strong>: enough pieces for a meaningful bonus, the rest of your slots free for best-in-slot gear.</p>

<h2>Every version has its own sets</h2>
<p>Sets and their bonuses are not the same across Dofus versions. Dofus 3, the beta, Dofus 2, Touch and Retro each have their own sets, their own piece counts and their own bonus values, because each is effectively its own game. The Fashionista loads the correct set data for the version you picked, so a Retro build is judged on Retro sets, not modern ones.</p>

<h2>A few sets take instead of giving</h2>
<p>Not every set bonus is a bonus. A handful of them <strong>cap a stat</strong> rather than raise it, and the ceiling drops the more pieces you wear. Cire Momore's Curse is the famous one: two pieces hold you to 4 MP, 4 range and 4 summons, and the full six take that down to <strong>2 MP</strong>, below the 3 you start the game with. In exchange it hands you enormous power, initiative and resistance. That is a deliberate trade, not a bug, and it is why you sometimes meet a heavily geared character crawling across the map. Retro and Touch have no set like it: the capping sets live in Dofus 3, the beta and Dofus 2, and even between those the exact ceilings differ. The optimizer applies the cap, so if you lock those pieces in you will see the reduced MP in your result instead of a number the game would never hand you.</p>

<h2>Let the tool do the set math</h2>
<p>You almost never have to plan sets by hand. The optimizer already knows every set bonus and weighs it against mixing individual items: if wearing four pieces of a set beats four separate best-in-slot items for your goals, it picks the set; if not, it mixes. Set your stat priorities, run it, and check the result. Want to see the difference a set makes? Build one version, then use the <a href="/choose_compare_sets/">comparator</a> to put a set-heavy build next to a mixed one and see exactly what each stat costs.</p>

<p><em>Curious what sets fit your goals? <a href="/setup/">Build it here.</a></em></p>
''',
            },
            'fr': {
                'title': 'Les bonus de panoplie : comment les sets boostent ton build',
                'desc': "Porte plusieurs items d'une même panoplie et tu débloques des bonus qui grandissent à chaque pièce. Comment ça marche, et quand viser la panoplie complète.",
                'lead': "Porte plusieurs items d'une même panoplie et tu débloques des bonus qui grandissent à chaque pièce. Comment ça marche, et quand la panoplie complète bat le mix.",
                'body': '''
<h2>Un bonus de panoplie, c'est quoi au juste</h2>
<p>Une panoplie (set) est un groupe d'items pensés pour être portés ensemble. Équipe deux pièces ou plus d'une même panoplie et le jeu te file <strong>des stats bonus en plus des items eux-mêmes</strong>. Ces bonus sont de la valeur gratuite : tu les as juste en portant des pièces qui occupent déjà tes emplacements. C'est pour ça que les panoplies sont la colonne vertébrale de la plupart des builds.</p>

<h2>Plus de pièces, plus de bonus, moins de liberté</h2>
<p>Le bonus de panoplie grandit avec le nombre de pièces portées : deux items donnent un petit bonus, et il monte à trois, quatre, cinq et au-delà, avec souvent un gros saut sur la ou les dernières pièces. Le piège, c'est le compromis. Chaque emplacement que tu réserves à une panoplie est un emplacement que tu ne peux pas remplir avec un meilleur item isolé. Une panoplie complète peut être énorme, ou t'imposer des pièces faibles juste pour atteindre le dernier palier. Le bon équilibre est souvent une <strong>panoplie partielle</strong> : assez de pièces pour un bonus qui compte, le reste de tes emplacements libre pour du meilleur item par slot.</p>

<h2>Chaque version a ses propres panoplies</h2>
<p>Les panoplies et leurs bonus ne sont pas les mêmes d'une version de Dofus à l'autre. Dofus 3, la bêta, Dofus 2, Touch et Rétro ont chacun leurs panoplies, leurs nombres de pièces et leurs valeurs de bonus, parce que chacun est en pratique son propre jeu. La Fashionista charge les bonnes données de panoplie pour la version que tu as choisie, donc un build Rétro est jugé sur les panoplies Rétro, pas les modernes.</p>

<h2>Certaines panoplies prennent au lieu de donner</h2>
<p>Tous les bonus de panoplie n'en sont pas. Quelques-unes <strong>plafonnent</strong> une stat au lieu de l'augmenter, et le plafond baisse à mesure que tu ajoutes des pièces. La Malédiction de Cire Momore est la plus connue : deux pièces te bloquent à 4 PM, 4 de portée et 4 invocations, et les six te font tomber à <strong>2 PM</strong>, sous les 3 avec lesquels tu commences le jeu. En échange, elle donne une puissance, une initiative et des résistances énormes. C'est un choix assumé, pas un bug, et c'est pour ça qu'on croise parfois un personnage très équipé qui rampe sur la map. Retro et Touch n'ont aucune panoplie de ce genre : celles qui plafonnent sont sur Dofus 3, la beta et Dofus 2, et même entre ces trois-là les plafonds exacts diffèrent. L'optimiseur applique la règle, donc si tu verrouilles ces pièces tu verras les PM réduits dans ton résultat plutôt qu'un chiffre que le jeu ne te donnerait jamais.</p>

<h2>Laisse l'outil faire le calcul des panoplies</h2>
<p>Tu n'as presque jamais à planifier les panoplies à la main. L'optimiseur connaît déjà chaque bonus de panoplie et l'arbitre contre le mix d'items isolés : si porter quatre pièces d'une panoplie bat quatre meilleurs items séparés pour tes objectifs, il prend la panoplie ; sinon, il mixe. Règle tes priorités de stats, lance, et regarde le résultat. Tu veux voir la différence qu'apporte une panoplie ? Construis une version, puis utilise le <a href="/choose_compare_sets/">comparateur</a> pour mettre un build à grosse panoplie à côté d'un build mixé et voir exactement ce que coûte chaque stat.</p>

<p><em>Curieux de savoir quelles panoplies collent à tes objectifs ? <a href="/setup/">Construis-le ici.</a></em></p>
''',
            },
            'es': {
                'title': 'Los bonus de conjunto: cómo las panoplias potencian tu build',
                'desc': "Lleva varios objetos de un mismo conjunto y desbloqueas bonus que crecen con cada pieza. Cómo funcionan, y cuándo vale la pena el conjunto completo.",
                'lead': "Lleva varios objetos de un mismo conjunto y desbloqueas bonus que crecen con cada pieza. Cómo funcionan, y cuándo el conjunto completo gana al mix.",
                'body': '''
<h2>Qué es de verdad un bonus de conjunto</h2>
<p>Un conjunto (panoplia) es un grupo de objetos pensados para llevarse juntos. Equipa dos piezas o más del mismo conjunto y el juego te da <strong>estadísticas extra además de los propios objetos</strong>. Esos bonus son valor gratis: los tienes solo por llevar piezas que ya ocupan tus espacios. Por eso los conjuntos son la columna vertebral de casi todos los builds.</p>

<h2>Más piezas, más bonus, menos libertad</h2>
<p>El bonus de conjunto crece con el número de piezas que llevas: dos objetos dan un bonus pequeño, y sube en tres, cuatro, cinco y más, normalmente con un gran salto en la última pieza o dos. La trampa es el compromiso. Cada espacio que reservas a un conjunto es un espacio que no puedes llenar con un mejor objeto suelto. Un conjunto completo puede ser brutal, o forzarte piezas flojas solo para llegar al último escalón. El punto justo suele ser un <strong>conjunto parcial</strong>: suficientes piezas para un bonus que importe, y el resto de tus espacios libres para lo mejor por casilla.</p>

<h2>Cada versión tiene sus propios conjuntos</h2>
<p>Los conjuntos y sus bonus no son iguales de una versión de Dofus a otra. Dofus 3, la beta, Dofus 2, Touch y Retro tienen cada uno sus conjuntos, sus números de piezas y sus valores de bonus, porque cada uno es en la práctica su propio juego. La Fashionista carga los datos de conjunto correctos para la versión que elegiste, así que un build Retro se juzga con conjuntos Retro, no modernos.</p>

<h2>Algunos conjuntos quitan en vez de dar</h2>
<p>No todos los bonus de conjunto son un bonus. Unos cuantos <strong>limitan</strong> una característica en lugar de subirla, y el tope baja cuantas más piezas llevas. La Maldición de Cire Momore es la más conocida: con dos piezas te quedas en 4 PM, 4 de alcance y 4 invocaciones, y con las seis bajas a <strong>2 PM</strong>, por debajo de los 3 con los que empiezas el juego. A cambio te da una potencia, una iniciativa y unas resistencias enormes. Es un intercambio buscado, no un fallo, y por eso a veces te cruzas con un personaje muy equipado arrastrándose por el mapa. Retro y Touch no tienen ningún conjunto así: los que limitan están en Dofus 3, la beta y Dofus 2, y hasta entre esos tres los topes exactos cambian. El optimizador aplica el límite, así que si bloqueas esas piezas verás los PM reducidos en tu resultado y no una cifra que el juego nunca te daría.</p>

<h2>Deja que la herramienta haga las cuentas</h2>
<p>Casi nunca tienes que planear los conjuntos a mano. El optimizador ya conoce cada bonus de conjunto y lo compara con mezclar objetos sueltos: si llevar cuatro piezas de un conjunto gana a cuatro mejores objetos por separado para tus objetivos, elige el conjunto; si no, mezcla. Ajusta tus prioridades de estadísticas, ejecútalo y mira el resultado. ¿Quieres ver la diferencia que hace un conjunto? Construye una versión y luego usa el <a href="/choose_compare_sets/">comparador</a> para poner un build con mucho conjunto al lado de uno mixto y ver exactamente lo que cuesta cada estadística.</p>

<p><em>¿Con curiosidad por qué conjuntos encajan con tus objetivos? <a href="/setup/">Constrúyelo aquí.</a></em></p>
''',
            },
            'pt': {
                'title': 'Os bônus de conjunto: como as panóplias turbinam seu build',
                'desc': "Use vários itens de um mesmo conjunto e você desbloqueia bônus que crescem a cada peça. Como funcionam, e quando vale a pena o conjunto completo.",
                'lead': "Use vários itens de um mesmo conjunto e você desbloqueia bônus que crescem a cada peça. Como funcionam, e quando o conjunto completo ganha do mix.",
                'body': '''
<h2>O que é de verdade um bônus de conjunto</h2>
<p>Um conjunto (panóplia) é um grupo de itens pensados para serem usados juntos. Equipe duas peças ou mais do mesmo conjunto e o jogo te dá <strong>atributos extras além dos próprios itens</strong>. Esses bônus são valor de graça: você os tem só por usar peças que já ocupam seus espaços. É por isso que os conjuntos são a espinha dorsal da maioria dos builds.</p>

<h2>Mais peças, mais bônus, menos liberdade</h2>
<p>O bônus de conjunto cresce com o número de peças que você usa: dois itens dão um bônus pequeno, e ele sobe em três, quatro, cinco e além, geralmente com um grande salto na última peça ou duas. A pegadinha é o compromisso. Cada espaço que você reserva para um conjunto é um espaço que não pode preencher com um item avulso melhor. Um conjunto completo pode ser incrível, ou te forçar peças fracas só para chegar ao último degrau. O ponto ideal costuma ser um <strong>conjunto parcial</strong>: peças suficientes para um bônus que importe, e o resto dos seus espaços livre para o melhor por casa.</p>

<h2>Cada versão tem seus próprios conjuntos</h2>
<p>Os conjuntos e seus bônus não são iguais de uma versão de Dofus para outra. Dofus 3, o beta, Dofus 2, Touch e Retro têm cada um seus conjuntos, seus números de peças e seus valores de bônus, porque cada um é na prática seu próprio jogo. A Fashionista carrega os dados de conjunto certos para a versão que você escolheu, então um build Retro é avaliado com conjuntos Retro, não modernos.</p>

<h2>Alguns conjuntos tiram em vez de dar</h2>
<p>Nem todo bônus de conjunto é um bônus. Alguns <strong>limitam</strong> um atributo em vez de aumentá-lo, e o teto cai quanto mais peças você usa. A Maldição de Cire Momore é a mais famosa: com duas peças você fica em 4 PM, 4 de alcance e 4 invocações, e com as seis cai para <strong>2 PM</strong>, abaixo dos 3 com que você começa o jogo. Em troca, ela entrega poder, iniciativa e resistências enormes. É uma troca proposital, não um bug, e é por isso que às vezes você encontra um personagem muito equipado se arrastando pelo mapa. Retro e Touch não têm nenhum conjunto assim: os que limitam estão no Dofus 3, no beta e no Dofus 2, e mesmo entre esses três os tetos exatos mudam. O otimizador aplica o limite, então se você travar essas peças vai ver os PM reduzidos no seu resultado, e não um número que o jogo nunca daria.</p>

<h2>Deixe a ferramenta fazer a conta dos conjuntos</h2>
<p>Você quase nunca precisa planejar os conjuntos na mão. O otimizador já conhece cada bônus de conjunto e o compara com misturar itens avulsos: se usar quatro peças de um conjunto ganha de quatro melhores itens separados para os seus objetivos, ele escolhe o conjunto; se não, mistura. Ajuste suas prioridades de atributos, rode e veja o resultado. Quer ver a diferença que um conjunto faz? Monte uma versão e use o <a href="/choose_compare_sets/">comparador</a> para colocar um build cheio de conjunto ao lado de um misto e ver exatamente o que cada atributo custa.</p>

<p><em>Curioso sobre quais conjuntos combinam com seus objetivos? <a href="/setup/">Monte aqui.</a></em></p>
''',
            },
            'de': {
                'title': 'Set-Boni: wie Panoplien deinen Build stärker machen',
                'desc': "Trage mehrere Items eines Sets und du schaltest Boni frei, die mit jedem Teil wachsen. Wie Set-Boni funktionieren und wann sich ein volles Set lohnt.",
                'lead': "Trage mehrere Items eines Sets und du schaltest Boni frei, die mit jedem Teil wachsen. Wie sie funktionieren, und wann ein volles Set das Mischen schlägt.",
                'body': '''
<h2>Was ein Set-Bonus wirklich ist</h2>
<p>Ein Set (Panoplie) ist eine Gruppe von Items, die zum gemeinsamen Tragen gedacht sind. Lege zwei oder mehr Teile desselben Sets an, und das Spiel gibt dir <strong>Bonuswerte zusätzlich zu den Items selbst</strong>. Diese Boni sind geschenkter Wert: du bekommst sie einfach dafür, dass du Teile trägst, die deine Plätze ohnehin belegen. Deshalb sind Sets das Rückgrat der meisten Builds.</p>

<h2>Mehr Teile, größerer Bonus, weniger Freiheit</h2>
<p>Der Set-Bonus wächst mit der Zahl der getragenen Teile: zwei Items geben einen kleinen Bonus, und er steigt bei drei, vier, fünf und mehr, oft mit einem großen Sprung beim letzten Teil oder den letzten beiden. Der Haken ist der Kompromiss. Jeder Platz, den du einem Set widmest, ist ein Platz, den du nicht mit einem besseren Einzelitem füllen kannst. Ein volles Set kann grandios sein oder dir schwache Teile aufzwingen, nur um die oberste Stufe zu erreichen. Der Sweet Spot ist oft ein <strong>Teil-Set</strong>: genug Teile für einen spürbaren Bonus, der Rest deiner Plätze frei für das beste Item pro Slot.</p>

<h2>Jede Version hat ihre eigenen Sets</h2>
<p>Sets und ihre Boni sind nicht über die Dofus-Versionen hinweg gleich. Dofus 3, die Beta, Dofus 2, Touch und Retro haben jeweils eigene Sets, eigene Teilezahlen und eigene Bonuswerte, weil jede praktisch ihr eigenes Spiel ist. Die Fashionista lädt die richtigen Set-Daten für die Version, die du gewählt hast, sodass ein Retro-Build an Retro-Sets gemessen wird, nicht an modernen.</p>

<h2>Manche Sets nehmen, statt zu geben</h2>
<p>Nicht jeder Set-Bonus ist ein Bonus. Ein paar <strong>deckeln</strong> einen Wert, statt ihn zu erhöhen, und die Grenze sinkt mit jedem weiteren Teil. Der Fluch von Cire Momore ist der bekannteste: mit zwei Teilen bleibst du bei 4 BP, 4 Reichweite und 4 Beschwörungen, mit allen sechs fällst du auf <strong>2 BP</strong>, unter die 3, mit denen du ins Spiel startest. Dafür bekommst du enorme Stärke, Initiative und Widerstände. Das ist ein bewusster Tausch, kein Fehler, und deshalb siehst du manchmal einen top ausgerüsteten Charakter über die Karte kriechen. Retro und Touch haben kein solches Set: die deckelnden Sets stecken in Dofus 3, im Beta und in Dofus 2, und selbst zwischen diesen dreien unterscheiden sich die genauen Grenzen. Der Optimierer hält sich an die Grenze, wenn du diese Teile also festsetzt, siehst du die reduzierten BP in deinem Ergebnis statt einer Zahl, die das Spiel dir nie geben würde.</p>

<h2>Lass das Tool die Set-Rechnung machen</h2>
<p>Du musst Sets fast nie von Hand planen. Der Optimierer kennt jeden Set-Bonus bereits und wägt ihn gegen das Mischen einzelner Items ab: wenn vier Teile eines Sets für deine Ziele vier separate Top-Items schlagen, wählt er das Set; wenn nicht, mischt er. Stelle deine Wert-Prioritäten ein, lass ihn laufen und schau dir das Ergebnis an. Willst du den Unterschied sehen, den ein Set macht? Bau eine Version und stelle mit dem <a href="/choose_compare_sets/">Vergleicher</a> einen Set-lastigen Build neben einen gemischten, um genau zu sehen, was jeder Wert kostet.</p>

<p><em>Neugierig, welche Sets zu deinen Zielen passen? <a href="/setup/">Bau es hier.</a></em></p>
''',
            },
        },
    },

    # ------------------------------------------------------------------ #
    'ap-mp-range-caps': {
        'published': '2026-07-22',
        'i18n': {
            'en': {
                'title': 'AP, MP and range: the caps that shape every build',
                'desc': "Modern Dofus caps you at 12 AP, 6 MP and 6 range, but Retro doesn't. What the limits are, why exos count once, and how to build around them.",
                'lead': "Modern Dofus hard-caps your AP, MP and range; Dofus Retro doesn't. Here's what the limits actually are, and how to build around them.",
                'body': '''
<h2>Why these three stats rule everything</h2>
<p>AP (action points), MP (movement points) and range decide what your character can physically do on a turn. One more AP is often a whole extra spell; one more MP is the difference between reaching the enemy and eating a wasted turn; range lets you hit before you get hit. That's why every build fights over them, and why gear that gives them is expensive.</p>

<h2>The modern caps: 12 AP, 6 MP, 6 range</h2>
<p>In modern Dofus (Dofus 3, the beta, Dofus 2 and Touch) a character is hard-capped at <strong>12 AP, 6 MP and 6 range</strong>, no matter how much gear you pile on. Anything above that simply is not counted: the item still equips, the extra points just do nothing. Ankama added this "PA/PM/PO limitation" back in Dofus 2 to stop stat inflation, and every modern version inherited it. You start with 6 AP and 3 MP, so in practice you are shopping for +6 AP, +3 MP and up to +6 range from your equipment.</p>

<h2>Exotic bonuses only count once</h2>
<p>Overmaging an item with an "exotic" AP, MP or range bonus (one the item never had) is powerful, but the game counts only <strong>one</strong> exo AP, one exo MP and one exo range across your whole set. You can wear three +1 AP exo rings; only one of them counts. Plan around a single exo per stat, not a stack.</p>

<h2>Retro plays by the old rules</h2>
<p>Dofus Retro (1.29) never got the limitation, so there is <strong>no 12/6/6 ceiling</strong> there. Exotic AP and MP stack for real, which is exactly why iconic Retro builds reach 17 AP or 7 MP. If you are theorycrafting on Retro, do not assume the modern caps: the Fashionista lets you require more than 12 AP on a Retro build precisely because the game does.</p>

<h2>Putting it to work in the tool</h2>
<p>Because these stats are capped and scarce, you usually <strong>lock them to a target</strong> instead of weighting them: set a minimum of, say, 11 AP and 6 MP, then let the optimizer spend everything else on damage or resistance. Decide the breakpoints your spell combo needs, lock them, and you will never waste gear overshooting a number the game would ignore anyway.</p>

<p><em>Know your caps? <a href="/setup/">Build around them here.</a></em></p>
''',
            },
            'fr': {
                'title': 'PA, PM et portée : les plafonds qui façonnent chaque build',
                'desc': "Le Dofus moderne te plafonne à 12 PA, 6 PM et 6 de portée, pas le Rétro. Les limites réelles, pourquoi les exos comptent une fois, et comment faire avec.",
                'lead': "Le Dofus moderne plafonne dur tes PA, PM et portée ; le Rétro non. Voilà ce que valent vraiment les limites, et comment construire autour.",
                'body': '''
<h2>Pourquoi ces trois stats commandent tout</h2>
<p>Les PA (points d'action), les PM (points de mouvement) et la portée décident de ce que ton perso peut physiquement faire dans un tour. Un PA de plus, c'est souvent un sort entier en rab ; un PM de plus, c'est atteindre l'ennemi au lieu de perdre ton tour ; la portée te laisse taper avant de te faire taper. C'est pour ça que tous les builds se les arrachent, et que le stuff qui en donne coûte cher.</p>

<h2>Les plafonds modernes : 12 PA, 6 PM, 6 de portée</h2>
<p>Sur le Dofus moderne (Dofus 3, la bêta, Dofus 2 et Touch), un personnage est plafonné dur à <strong>12 PA, 6 PM et 6 de portée</strong>, peu importe la montagne de stuff que tu empiles. Tout ce qui dépasse n'est tout simplement pas compté : l'objet s'équipe quand même, les points en trop ne servent à rien. Ankama a ajouté cette "limitation PA/PM/PO" dès Dofus 2 pour stopper l'inflation des stats, et toutes les versions modernes en ont hérité. Tu démarres avec 6 PA et 3 PM, donc en vrai tu cherches +6 PA, +3 PM et jusqu'à +6 de portée sur ton équipement.</p>

<h2>Les bonus exotiques ne comptent qu'une fois</h2>
<p>Sur-forger un objet avec un bonus "exotique" de PA, PM ou portée (un bonus que l'objet n'avait pas à l'origine), c'est puissant, mais le jeu ne compte qu'<strong>un seul</strong> PA exo, un seul PM exo et une seule portée exo sur tout ton équipement. Tu peux porter trois anneaux exo +1 PA ; un seul comptera. Prévois un exo unique par stat, pas une pile.</p>

<h2>Le Rétro joue avec les vieilles règles</h2>
<p>Dofus Rétro (1.29) n'a jamais eu la limitation, donc là il n'y a <strong>aucun plafond 12/6/6</strong>. Les PA et PM exotiques s'empilent pour de vrai, et c'est exactement pour ça que les builds Rétro cultes montent à 17 PA ou 7 PM. Si tu theorycraftes sur Rétro, oublie les plafonds modernes : la Fashionista te laisse exiger plus de 12 PA sur un build Rétro, justement parce que le jeu le permet.</p>

<h2>S'en servir dans l'outil</h2>
<p>Comme ces stats sont plafonnées et rares, tu les <strong>verrouilles à un objectif</strong> plutôt que de les pondérer : mets un minimum de, disons, 11 PA et 6 PM, puis laisse l'optimiseur dépenser tout le reste en dégâts ou en résistance. Décide les paliers dont ton combo de sorts a besoin, verrouille-les, et tu ne gaspilleras jamais de stuff à dépasser un nombre que le jeu ignorerait de toute façon.</p>

<p><em>Tu connais tes plafonds ? <a href="/setup/">Construis autour ici.</a></em></p>
''',
            },
            'es': {
                'title': 'PA, PM y alcance: los topes que moldean cada build',
                'desc': "El Dofus moderno te limita a 12 PA, 6 PM y 6 de alcance, el Retro no. Qué valen los límites, por qué los exo cuentan una vez, y cómo construir con eso.",
                'lead': "El Dofus moderno limita a fondo tus PA, PM y alcance; el Dofus Retro no. Esto es lo que valen de verdad los límites, y cómo construir con ellos.",
                'body': '''
<h2>Por qué estas tres estadísticas mandan sobre todo</h2>
<p>Los PA (puntos de acción), los PM (puntos de movimiento) y el alcance deciden lo que tu personaje puede hacer físicamente en un turno. Un PA más suele ser un hechizo entero extra; un PM más es llegar al enemigo en vez de perder el turno; el alcance te deja pegar antes de que te peguen. Por eso todos los builds se pelean por ellos, y el equipo que los da cuesta caro.</p>

<h2>Los topes modernos: 12 PA, 6 PM, 6 de alcance</h2>
<p>En el Dofus moderno (Dofus 3, la beta, Dofus 2 y Touch) un personaje está limitado a <strong>12 PA, 6 PM y 6 de alcance</strong>, por mucho equipo que amontones. Todo lo que pase de ahí simplemente no se cuenta: el objeto se equipa igual, los puntos de más no hacen nada. Ankama añadió esta "limitación PA/PM/PO" ya en Dofus 2 para frenar la inflación de estadísticas, y todas las versiones modernas la heredaron. Empiezas con 6 PA y 3 PM, así que en realidad buscas +6 PA, +3 PM y hasta +6 de alcance en tu equipo.</p>

<h2>Los bonus exóticos cuentan solo una vez</h2>
<p>Sobreforjar un objeto con un bonus "exótico" de PA, PM o alcance (uno que el objeto no tenía de origen) es potente, pero el juego cuenta solo <strong>un</strong> PA exótico, un PM exótico y un alcance exótico en todo tu equipo. Puedes llevar tres anillos exo de +1 PA; solo contará uno. Planifica un único exo por estadística, no una pila.</p>

<h2>El Retro juega con las reglas viejas</h2>
<p>Dofus Retro (1.29) nunca tuvo la limitación, así que ahí no hay <strong>ningún tope 12/6/6</strong>. Los PA y PM exóticos se acumulan de verdad, y por eso los builds Retro míticos llegan a 17 PA o 7 PM. Si haces theorycraft en Retro, olvida los topes modernos: la Fashionista te deja exigir más de 12 PA en un build Retro, precisamente porque el juego lo permite.</p>

<h2>Aprovecharlo en la herramienta</h2>
<p>Como estas estadísticas están limitadas y son escasas, normalmente las <strong>bloqueas a un objetivo</strong> en vez de ponderarlas: pon un mínimo de, digamos, 11 PA y 6 PM, y deja que el optimizador gaste todo lo demás en daño o resistencia. Decide los umbrales que tu combo de hechizos necesita, bloquéalos, y nunca malgastarás equipo pasándote de un número que el juego ignoraría igualmente.</p>

<p><em>¿Conoces tus topes? <a href="/setup/">Construye en torno a ellos aquí.</a></em></p>
''',
            },
            'pt': {
                'title': 'PA, PM e alcance: os limites que moldam cada build',
                'desc': "O Dofus moderno te limita a 12 PA, 6 PM e 6 de alcance, mas o Retro não. O que valem os limites, por que os exo contam uma vez, e como construir com isso.",
                'lead': "O Dofus moderno limita a fundo seus PA, PM e alcance; o Dofus Retro não. Aqui está o que os limites valem de verdade, e como construir em torno deles.",
                'body': '''
<h2>Por que essas três estatísticas mandam em tudo</h2>
<p>Os PA (pontos de ação), os PM (pontos de movimento) e o alcance decidem o que seu personagem consegue fazer fisicamente num turno. Um PA a mais costuma ser um feitiço inteiro extra; um PM a mais é alcançar o inimigo em vez de perder o turno; o alcance deixa você bater antes de apanhar. É por isso que todo build briga por eles, e o equipamento que os dá custa caro.</p>

<h2>Os limites modernos: 12 PA, 6 PM, 6 de alcance</h2>
<p>No Dofus moderno (Dofus 3, o beta, Dofus 2 e Touch) um personagem é limitado a <strong>12 PA, 6 PM e 6 de alcance</strong>, não importa quanto equipamento você empilhe. Tudo acima disso simplesmente não é contado: o item ainda equipa, os pontos a mais não fazem nada. A Ankama adicionou essa "limitação PA/PM/PO" já no Dofus 2 para frear a inflação de estatísticas, e todas as versões modernas herdaram. Você começa com 6 PA e 3 PM, então na prática você procura +6 PA, +3 PM e até +6 de alcance no seu equipamento.</p>

<h2>Os bônus exóticos contam só uma vez</h2>
<p>Sobreforjar um item com um bônus "exótico" de PA, PM ou alcance (um que o item não tinha de origem) é forte, mas o jogo conta só <strong>um</strong> PA exótico, um PM exótico e um alcance exótico em todo o seu equipamento. Você pode usar três anéis exo de +1 PA; só um vai contar. Planeje um único exo por estatística, não uma pilha.</p>

<h2>O Retro joga com as regras antigas</h2>
<p>Dofus Retro (1.29) nunca teve a limitação, então ali não existe <strong>nenhum limite 12/6/6</strong>. Os PA e PM exóticos se acumulam de verdade, e é exatamente por isso que os builds Retro clássicos chegam a 17 PA ou 7 PM. Se você faz theorycraft no Retro, esqueça os limites modernos: a Fashionista deixa você exigir mais de 12 PA num build Retro, justamente porque o jogo permite.</p>

<h2>Usando isso na ferramenta</h2>
<p>Como essas estatísticas são limitadas e escassas, você normalmente as <strong>trava num objetivo</strong> em vez de ponderá-las: coloque um mínimo de, digamos, 11 PA e 6 PM, e deixe o otimizador gastar todo o resto em dano ou resistência. Decida os limiares que seu combo de feitiços precisa, trave-os, e você nunca vai desperdiçar equipamento passando de um número que o jogo ignoraria de qualquer forma.</p>

<p><em>Conhece seus limites? <a href="/setup/">Construa em torno deles aqui.</a></em></p>
''',
            },
            'de': {
                'title': 'AP, MP und Reichweite: die Grenzen, die jeden Build prägen',
                'desc': "Das moderne Dofus deckelt dich bei 12 AP, 6 MP und 6 Reichweite, Retro nicht. Was die Grenzen bedeuten und wie du sinnvoll drumherum baust.",
                'lead': "Das moderne Dofus deckelt deine AP, MP und Reichweite hart; Dofus Retro nicht. Hier steht, was die Grenzen wirklich bedeuten und wie du drumherum baust.",
                'body': '''
<h2>Warum diese drei Werte über alles bestimmen</h2>
<p>AP (Aktionspunkte), MP (Bewegungspunkte) und Reichweite entscheiden, was deine Figur in einer Runde überhaupt tun kann. Ein AP mehr ist oft ein ganzer zusätzlicher Zauber; ein MP mehr heißt, den Gegner zu erreichen, statt die Runde zu verlieren; Reichweite lässt dich treffen, bevor du getroffen wirst. Deshalb kämpft jeder Build um sie, und Ausrüstung, die sie gibt, ist teuer.</p>

<h2>Die modernen Grenzen: 12 AP, 6 MP, 6 Reichweite</h2>
<p>Im modernen Dofus (Dofus 3, die Beta, Dofus 2 und Touch) ist eine Figur hart bei <strong>12 AP, 6 MP und 6 Reichweite</strong> gedeckelt, egal wie viel Ausrüstung du stapelst. Alles darüber wird schlicht nicht gezählt: der Gegenstand lässt sich trotzdem anlegen, die überschüssigen Punkte bringen nichts. Ankama hat diese "PA/PM/PO-Begrenzung" schon in Dofus 2 eingeführt, um die Werte-Inflation zu bremsen, und jede moderne Version hat sie geerbt. Du startest mit 6 AP und 3 MP, suchst also in Wahrheit +6 AP, +3 MP und bis zu +6 Reichweite auf deiner Ausrüstung.</p>

<h2>Exotische Boni zählen nur einmal</h2>
<p>Einen Gegenstand mit einem "exotischen" AP-, MP- oder Reichweiten-Bonus zu übermagen (einen, den der Gegenstand nie hatte), ist stark, aber das Spiel zählt über deine gesamte Ausrüstung nur <strong>einen</strong> Exo-AP, einen Exo-MP und eine Exo-Reichweite. Du kannst drei Exo-Ringe mit +1 AP tragen; nur einer zählt. Plane mit einem einzigen Exo pro Wert, nicht mit einem Stapel.</p>

<h2>Retro spielt nach den alten Regeln</h2>
<p>Dofus Retro (1.29) hat die Begrenzung nie bekommen, also gibt es dort <strong>keine 12/6/6-Decke</strong>. Exotische AP und MP stapeln sich wirklich, und genau deshalb erreichen legendäre Retro-Builds 17 AP oder 7 MP. Wenn du auf Retro theorycraftest, vergiss die modernen Grenzen: die Fashionista lässt dich auf einem Retro-Build mehr als 12 AP verlangen, gerade weil das Spiel es erlaubt.</p>

<h2>So nutzt du das im Tool</h2>
<p>Weil diese Werte gedeckelt und knapp sind, <strong>legst du sie meist auf ein Ziel fest</strong>, statt sie zu gewichten: setze ein Minimum von etwa 11 AP und 6 MP und lass den Optimierer alles Übrige in Schaden oder Resistenz stecken. Entscheide die Schwellen, die dein Zauber-Combo braucht, lege sie fest, und du verschwendest nie Ausrüstung dafür, eine Zahl zu überschreiten, die das Spiel ohnehin ignorieren würde.</p>

<p><em>Kennst du deine Grenzen? <a href="/setup/">Bau hier darum herum.</a></em></p>
''',
            },
        },
    },

    # ------------------------------------------------------------------ #
    'getting-started': {
        'published': '2026-06-30',
        'i18n': {
            'en': {
                'title': 'Your first Dofus build, step by step',
                'desc': "You picked a class, you're staring at a wall of items with no clue which belt fits. Here's how to go from nothing to a full optimized set in minutes.",
                'lead': "You picked a class, you're staring at a wall of items, and you have no clue which belt actually fits. That's exactly what the Fashionista is for.",
                'body': '''
<h2>1. Start a project</h2>
<p>Hit <a href="/setup/">Create a project</a>, pick your class, your level and the Dofus version you play. That's the whole setup. If you'd rather not fiddle with anything, two shortcuts get you a build almost instantly:</p>
<ul>
<li><a href="/quickstart/">Quick start</a>: answer three quick questions and you get a set.</li>
<li><a href="/smartbuild/">Smart build</a>: literally describe what you want in plain words ("agility Sram level 200, 11 AP, max range") and it sets things up for you.</li>
</ul>

<h2>2. Tell it what you actually want</h2>
<p>This is where most people overthink it. The wizard gives you sliders: AP, MP, range, the element you hit with, vitality, and so on. You're not entering numbers item by item, you're telling the tool how much each stat is <strong>worth to you</strong>. Want a glass cannon? Crank damage and element, leave vitality low. Playing competitive PvP? Push resistance and lock your AP/MP. You can always come back and nudge a slider later.</p>

<h2>3. Read the suggestion (and push back on it)</h2>
<p>The tool spits out a full set: weapon, armor, rings, cloak, dofus, the lot. It won't always be what you pictured, and that's fine. Three things you'll use constantly:</p>
<ul>
<li><strong>Forbid</strong> an item you can't afford or don't have, it'll find the next best thing.</li>
<li><strong>Lock</strong> an item you already own so the build is built around it.</li>
<li><strong>Tailor a new set</strong> after any change to re-run the optimization.</li>
</ul>

<h2>4. Save it, share it, compare it</h2>
<p>Make a free account to keep your projects. Every build gets a share link you can drop in your guild chat, and you can throw two or more builds into the <a href="/choose_compare_sets/">comparison</a> to see them side by side. Simple as that, you're done.</p>

<p><em>New here? The fastest way to learn is to just <a href="/quickstart/">make one build</a> and tweak it.</em></p>
''',
            },
            'fr': {
                'title': 'Ton premier stuff Dofus, étape par étape',
                'desc': "T'as choisi ta classe, une montagne d'items devant les yeux, aucune idée de quoi mettre. Passer de zéro à un stuff complet et optimisé en quelques minutes.",
                'lead': "T'as choisi ta classe, t'as une montagne d'items devant les yeux et aucune idée de quelle ceinture coller. C'est exactement à ça que sert la Fashionista.",
                'body': '''
<h2>1. Crée un projet</h2>
<p>Clique sur <a href="/setup/">Créer un projet</a>, choisis ta classe, ton niveau et la version de Dofus que tu joues. C'est toute la config. Et si t'as la flemme de régler quoi que ce soit, deux raccourcis te sortent un stuff quasi instantanément :</p>
<ul>
<li><a href="/quickstart/">Démarrage rapide</a> : trois questions et t'as un set.</li>
<li><a href="/smartbuild/">Build intelligent</a> : tu décris littéralement ce que tu veux en français ("Sram agi niveau 200, 11 PA, portée max") et il te prépare tout.</li>
</ul>

<h2>2. Dis-lui vraiment ce que tu veux</h2>
<p>C'est là que la plupart des gens se prennent la tête pour rien. L'assistant te donne des curseurs : PA, PM, portée, l'élément avec lequel tu tapes, la vita, etc. Tu ne rentres pas les items un par un, tu dis à l'outil combien chaque carac <strong>vaut pour toi</strong>. Tu veux un build full dégâts ? Monte les dégâts et l'élément, laisse la vita en bas. Tu fais du PvP compétitif ? Pousse la résistance et verrouille tes PA/PM. Tu pourras toujours revenir bouger un curseur après.</p>

<h2>3. Lis la proposition (et conteste-la)</h2>
<p>L'outil te sort un stuff complet : arme, panoplie, anneaux, cape, dofus, tout. Ça ne sera pas toujours ce que t'avais en tête, et c'est normal. Trois trucs que tu vas utiliser non-stop :</p>
<ul>
<li><strong>Interdire</strong> un item que tu peux pas te payer ou que t'as pas, il te trouvera le suivant.</li>
<li><strong>Verrouiller</strong> un item que t'as déjà pour construire le build autour.</li>
<li><strong>Tailler un nouveau set</strong> après chaque changement pour relancer l'opti.</li>
</ul>

<h2>4. Sauvegarde, partage, compare</h2>
<p>Crée un compte gratuit pour garder tes projets. Chaque build a un lien de partage que tu peux balancer dans le tchat de guilde, et tu peux mettre deux builds (ou plus) dans le <a href="/choose_compare_sets/">comparateur</a> pour les voir côte à côte. Voilà, c'est plié.</p>

<p><em>Nouveau ici ? Le plus rapide pour piger, c'est juste de <a href="/quickstart/">faire un build</a> et de le bidouiller.</em></p>
''',
            },
            'es': {
                'title': 'Tu primer build de Dofus, paso a paso',
                'desc': "Elegiste clase, tienes un muro de ítems delante y ni idea de qué cinturón encaja. Así pasas de cero a un set completo y optimizado en unos minutos.",
                'lead': "Elegiste clase, tienes un muro de ítems delante y ni idea de qué cinturón encaja de verdad. Para eso está la Fashionista.",
                'body': '''
<h2>1. Crea un proyecto</h2>
<p>Dale a <a href="/setup/">Crear un proyecto</a>, elige tu clase, tu nivel y la versión de Dofus que juegas. Esa es toda la configuración. Y si te da pereza tocar nada, dos atajos te sacan un build casi al instante:</p>
<ul>
<li><a href="/quickstart/">Inicio rápido</a>: tres preguntas y tienes un set.</li>
<li><a href="/smartbuild/">Build inteligente</a>: describe lo que quieres con tus palabras ("Sram de agilidad nivel 200, 11 PA, alcance máximo") y te lo prepara solo.</li>
</ul>

<h2>2. Dile lo que quieres de verdad</h2>
<p>Aquí es donde la mayoría se complica sin necesidad. El asistente te da deslizadores: PA, PM, alcance, el elemento con el que pegas, vitalidad y demás. No metes los ítems uno a uno: le dices a la herramienta cuánto <strong>vale para ti</strong> cada característica. ¿Quieres un build de cristal? Sube daño y elemento, deja la vita baja. ¿Haces PvP competitivo? Sube la resistencia y bloquea tus PA/PM. Siempre puedes volver y mover un deslizador después.</p>

<h2>3. Lee la sugerencia (y llévale la contraria)</h2>
<p>La herramienta te saca un set completo: arma, panoplia, anillos, capa, dofus, todo. No siempre será lo que imaginabas, y no pasa nada. Tres cosas que vas a usar todo el rato:</p>
<ul>
<li><strong>Prohibir</strong> un ítem que no te puedes pagar o no tienes, te buscará el siguiente mejor.</li>
<li><strong>Bloquear</strong> un ítem que ya tienes para montar el build a su alrededor.</li>
<li><strong>Crear un set nuevo</strong> tras cada cambio para volver a optimizar.</li>
</ul>

<h2>4. Guárdalo, compártelo, compáralo</h2>
<p>Hazte una cuenta gratis para conservar tus proyectos. Cada build tiene un enlace para compartir que puedes soltar en el chat del gremio, y puedes meter dos builds (o más) en el <a href="/choose_compare_sets/">comparador</a> para verlos lado a lado. Y ya está.</p>

<p><em>¿Primera vez? Lo más rápido para entenderlo es <a href="/quickstart/">montar un build</a> y trastear con él.</em></p>
''',
            },
            'pt': {
                'title': 'Seu primeiro build de Dofus, passo a passo',
                'desc': "Você escolheu a classe, tem uma parede de itens na frente e nenhuma ideia de qual cinto usar. Veja como sair do zero a um set completo e otimizado em minutos.",
                'lead': "Você escolheu a classe, tem uma parede de itens na frente e nenhuma ideia de qual cinto encaixa de verdade. É exatamente para isso que a Fashionista serve.",
                'body': '''
<h2>1. Crie um projeto</h2>
<p>Clique em <a href="/setup/">Criar um projeto</a>, escolha sua classe, seu nível e a versão de Dofus que você joga. É toda a configuração. E se você estiver com preguiça de ajustar qualquer coisa, dois atalhos entregam um build quase na hora:</p>
<ul>
<li><a href="/quickstart/">Início rápido</a>: três perguntas e você tem um set.</li>
<li><a href="/smartbuild/">Build inteligente</a>: descreva o que você quer com suas palavras ("Sram de agilidade nível 200, 11 PA, alcance máximo") e ele monta tudo pra você.</li>
</ul>

<h2>2. Diga o que você realmente quer</h2>
<p>É aqui que a maioria complica à toa. O assistente te dá controles deslizantes: PA, PM, alcance, o elemento com que você bate, vitalidade e por aí vai. Você não coloca os itens um por um, você diz pra ferramenta quanto cada atributo <strong>vale pra você</strong>. Quer um build de vidro? Aumenta dano e elemento, deixa a vita lá embaixo. Joga PvP competitivo? Sobe a resistência e trava seus PA/PM. Dá sempre pra voltar e mexer num controle depois.</p>

<h2>3. Leia a sugestão (e discorde dela)</h2>
<p>A ferramenta solta um set completo: arma, conjunto, anéis, capa, dofus, tudo. Nem sempre vai ser o que você imaginou, e tudo bem. Três coisas que você vai usar o tempo todo:</p>
<ul>
<li><strong>Proibir</strong> um item que você não pode pagar ou não tem, ela acha o próximo melhor.</li>
<li><strong>Travar</strong> um item que você já tem pra montar o build em volta dele.</li>
<li><strong>Criar um set novo</strong> depois de cada mudança pra otimizar de novo.</li>
</ul>

<h2>4. Salve, compartilhe, compare</h2>
<p>Faça uma conta grátis pra guardar seus projetos. Todo build ganha um link de compartilhamento que dá pra jogar no chat da guilda, e você pode colocar dois builds (ou mais) no <a href="/choose_compare_sets/">comparador</a> pra ver lado a lado. Pronto, é isso.</p>

<p><em>Primeira vez? O jeito mais rápido de entender é <a href="/quickstart/">montar um build</a> e mexer nele.</em></p>
''',
            },
            'de': {
                'title': 'Dein erstes Dofus-Build, Schritt für Schritt',
                'desc': "Klasse gewählt, eine Wand voller Items vor dir, keine Ahnung, welcher Gürtel passt. So kommst du in Minuten von null zum fertigen, optimierten Set.",
                'lead': "Klasse gewählt, eine Wand voller Items vor dir, und keine Ahnung, welcher Gürtel eigentlich passt. Genau dafür ist die Fashionista da.",
                'body': '''
<h2>1. Leg ein Projekt an</h2>
<p>Klick auf <a href="/setup/">Projekt erstellen</a>, wähl deine Klasse, dein Level und die Dofus-Version, die du spielst. Mehr Einrichtung gibt's nicht. Und wenn du gar nichts einstellen willst, bringen dich zwei Abkürzungen fast sofort zum Build:</p>
<ul>
<li><a href="/quickstart/">Schnellstart</a>: drei Fragen, fertig ist das Set.</li>
<li><a href="/smartbuild/">Smart Build</a>: beschreib einfach in Worten, was du willst ("Agi-Sram Level 200, 11 AP, maximale Reichweite") und es richtet alles für dich ein.</li>
</ul>

<h2>2. Sag ihm, was du wirklich willst</h2>
<p>Hier machen es sich die meisten unnötig kompliziert. Der Assistent gibt dir Regler: AP, BP, Reichweite, das Element, mit dem du haust, Vitalität und so weiter. Du trägst nicht Item für Item Zahlen ein, du sagst dem Tool, wie viel dir jeder Wert <strong>wert ist</strong>. Glaskanone? Schadens- und Element-Regler hoch, Vita niedrig lassen. Kompetitives PvP? Resistenz hoch und AP/BP fixieren. Du kannst jederzeit zurück und einen Regler nachjustieren.</p>

<h2>3. Lies den Vorschlag (und widersprich ihm)</h2>
<p>Das Tool wirft ein komplettes Set aus: Waffe, Rüstung, Ringe, Umhang, Dofus, alles. Es wird nicht immer das sein, was du dir vorgestellt hast, und das ist okay. Drei Sachen, die du ständig brauchst:</p>
<ul>
<li>Ein Item <strong>verbieten</strong>, das du dir nicht leisten kannst oder nicht hast, es findet das nächstbeste.</li>
<li>Ein Item <strong>sperren</strong>, das du schon besitzt, damit das Build drumherum gebaut wird.</li>
<li><strong>Neues Set schneidern</strong> nach jeder Änderung, um neu zu optimieren.</li>
</ul>

<h2>4. Speichern, teilen, vergleichen</h2>
<p>Mach dir einen kostenlosen Account, um deine Projekte zu behalten. Jedes Build bekommt einen Teil-Link, den du in den Gildenchat werfen kannst, und du kannst zwei Builds (oder mehr) in den <a href="/choose_compare_sets/">Vergleich</a> packen, um sie nebeneinander zu sehen. Das war's.</p>

<p><em>Neu hier? Am schnellsten verstehst du es, wenn du einfach <a href="/quickstart/">ein Build baust</a> und daran herumschraubst.</em></p>
''',
            },
        },
    },

    # ------------------------------------------------------------------ #
    'how-it-works': {
        'published': '2026-06-30',
        'i18n': {
            'en': {
                'title': 'How the optimizer actually works',
                'desc': "Most build sites are a spreadsheet: you drag in items, they total the stats. The Fashionista works backwards, you say what you want and it finds the items.",
                'lead': "Most build sites are a fancy spreadsheet: you drag items in, they add up the stats. The Fashionista works the other way round, you say what you want, it finds the items.",
                'body': '''
<h2>It's an optimization problem, not a list</h2>
<p>When you set your sliders, you're handing the tool a <strong>score</strong> for every stat. Behind the scenes it then searches through thousands of legal item combinations and picks the one that racks up the highest total score, while respecting the hard rules of the game. That's a genuine mathematical optimization, the same family of math used for scheduling planes or packing trucks, just pointed at your Iop instead.</p>

<h2>Why weighting beats raw stats</h2>
<p>Say intelligence is worth 1 point to you and vitality 0.2. An item with +40 int and +100 vita scores 40 + 20 = 60. An item with +60 int and +30 vita scores 60 + 6 = 66, so it wins, even though it has less vita. Multiply that across twelve slots, set bonuses and dofus, and you get combinations no human bothers to check by hand. That's the whole point: you set the priorities, it does the boring part.</p>

<h2>The rules it never breaks</h2>
<p>Optimizing freely would be easy; optimizing <em>legally</em> is the hard bit. The solver keeps your build inside the lines:</p>
<ul>
<li>AP, MP and range targets you locked.</li>
<li>One item per slot, two different rings, real set bonuses.</li>
<li>Minimum stats you demanded (say "at least 3000 HP").</li>
<li>Items you forbade or locked, and conditions like level or class restrictions.</li>
</ul>

<h2>Why the result sometimes surprises you</h2>
<p>If the suggestion looks weird, it's usually telling you something: your weights are pulling against each other, or there simply isn't gear that hits everything at once. Drop a slider, raise another, forbid that one item you'll never farm, and re-run. After a couple of passes you'll have a set that's genuinely tuned to you, not a copy-paste meta build everyone else is wearing.</p>

<p><em>Want to see it happen? <a href="/setup/">Start a project</a> and watch it solve.</em></p>
''',
            },
            'fr': {
                'title': "Comment l'optimiseur fonctionne vraiment",
                'desc': "La plupart des sites de build sont un tableur : tu glisses, ça additionne. La Fashionista fait l'inverse : dis ce que tu veux, elle trouve les items.",
                'lead': "La plupart des sites de build, c'est un tableur déguisé : tu glisses des items, ça additionne les stats. La Fashionista fait l'inverse, tu dis ce que tu veux, elle trouve les items.",
                'body': '''
<h2>C'est un problème d'optimisation, pas une liste</h2>
<p>Quand tu règles tes curseurs, tu donnes en fait un <strong>score</strong> à chaque carac. En coulisses, l'outil parcourt des milliers de combinaisons d'items valides et garde celle qui cumule le plus gros score total, tout en respectant les règles dures du jeu. C'est de la vraie optimisation mathématique, la même famille de maths qui sert à planifier des avions ou à remplir des camions, juste braquée sur ton Iop.</p>

<h2>Pourquoi pondérer bat les stats brutes</h2>
<p>Mettons que l'intelligence vaut 1 point pour toi et la vita 0,2. Un item +40 intel et +100 vita marque 40 + 20 = 60. Un item +60 intel et +30 vita marque 60 + 6 = 66, donc il gagne, alors qu'il a moins de vita. Multiplie ça sur douze emplacements, les bonus de panoplie et les dofus, et tu obtiens des combinaisons que personne ne s'amuse à vérifier à la main. C'est tout l'intérêt : tu poses les priorités, lui fait la partie chiante.</p>

<h2>Les règles qu'il ne casse jamais</h2>
<p>Optimiser librement, c'est facile ; optimiser <em>légalement</em>, c'est le vrai boulot. Le solveur garde ton build dans les clous :</p>
<ul>
<li>Les objectifs de PA, PM et portée que t'as verrouillés.</li>
<li>Un item par emplacement, deux anneaux différents, les vrais bonus de panoplie.</li>
<li>Les stats minimales que t'as exigées (genre "au moins 3000 PV").</li>
<li>Les items interdits ou verrouillés, et les conditions type niveau ou restriction de classe.</li>
</ul>

<h2>Pourquoi le résultat te surprend parfois</h2>
<p>Si la proposition a l'air bizarre, en général elle te dit quelque chose : tes poids se tirent dessus, ou il n'existe tout simplement pas de stuff qui coche tout d'un coup. Baisse un curseur, monte un autre, interdis cet item que tu farmeras jamais, et relance. Au bout de deux-trois passes, t'as un set vraiment réglé pour toi, pas un build meta copié-collé que tout le monde porte.</p>

<p><em>Envie de voir ça en vrai ? <a href="/setup/">Lance un projet</a> et regarde-le résoudre.</em></p>
''',
            },
            'es': {
                'title': 'Cómo funciona de verdad el optimizador',
                'desc': "La mayoría de las webs de builds son una hoja de cálculo: arrastras ítems y suman. La Fashionista hace lo contrario: dices qué quieres y encuentra los ítems.",
                'lead': "La mayoría de las webs de builds son una hoja de cálculo con maquillaje: arrastras ítems y suman las estadísticas. La Fashionista hace lo contrario, tú dices qué quieres y ella encuentra los ítems.",
                'body': '''
<h2>Es un problema de optimización, no una lista</h2>
<p>Cuando ajustas los deslizadores, en realidad le das una <strong>puntuación</strong> a cada característica. Por detrás, la herramienta recorre miles de combinaciones de ítems válidas y se queda con la que más puntúa en total, respetando las reglas duras del juego. Es optimización matemática de verdad, la misma familia de mates que sirve para planificar aviones o llenar camiones, solo que apuntando a tu Yopuka.</p>

<h2>Por qué ponderar gana a las estadísticas en bruto</h2>
<p>Pongamos que la inteligencia vale 1 punto para ti y la vitalidad 0,2. Un ítem con +40 inteligencia y +100 vita puntúa 40 + 20 = 60. Uno con +60 inteligencia y +30 vita puntúa 60 + 6 = 66, así que gana, aunque tenga menos vita. Multiplica eso por doce ranuras, bonus de panoplia y dofus, y salen combinaciones que nadie se pone a comprobar a mano. Esa es la gracia: tú pones las prioridades, ella hace lo aburrido.</p>

<h2>Las reglas que nunca rompe</h2>
<p>Optimizar libremente es fácil; optimizar <em>de forma legal</em> es lo difícil. El solucionador mantiene tu build dentro de las líneas:</p>
<ul>
<li>Los objetivos de PA, PM y alcance que bloqueaste.</li>
<li>Un ítem por ranura, dos anillos distintos, bonus de panoplia reales.</li>
<li>Las estadísticas mínimas que exigiste (por ejemplo "al menos 3000 PV").</li>
<li>Los ítems que prohibiste o bloqueaste, y condiciones como nivel o restricción de clase.</li>
</ul>

<h2>Por qué el resultado a veces sorprende</h2>
<p>Si la sugerencia parece rara, normalmente te está diciendo algo: tus pesos tiran unos contra otros, o simplemente no existe equipo que lo cumpla todo a la vez. Baja un deslizador, sube otro, prohíbe ese ítem que no vas a farmear nunca, y vuelve a lanzar. Tras un par de pasadas tendrás un set afinado para ti de verdad, no un build meta copiado que lleva todo el mundo.</p>

<p><em>¿Quieres verlo en acción? <a href="/setup/">Empieza un proyecto</a> y míralo resolver.</em></p>
''',
            },
            'pt': {
                'title': 'Como o otimizador funciona de verdade',
                'desc': "A maioria dos sites de build é uma planilha: você arrasta itens e ela soma. A Fashionista faz o contrário, você diz o que quer e ela acha os itens.",
                'lead': "A maioria dos sites de build é uma planilha disfarçada: você arrasta itens e ela soma os atributos. A Fashionista faz o contrário, você diz o que quer e ela acha os itens.",
                'body': '''
<h2>É um problema de otimização, não uma lista</h2>
<p>Quando você ajusta os controles, na real você dá uma <strong>pontuação</strong> pra cada atributo. Por trás, a ferramenta percorre milhares de combinações de itens válidas e fica com a que soma a maior pontuação total, respeitando as regras duras do jogo. É otimização matemática de verdade, a mesma família de matemática que serve pra planejar voos ou encher caminhões, só que apontada pro seu Iop.</p>

<h2>Por que ponderar ganha dos atributos crus</h2>
<p>Digamos que inteligência vale 1 ponto pra você e vitalidade 0,2. Um item com +40 inteligência e +100 vita pontua 40 + 20 = 60. Um com +60 inteligência e +30 vita pontua 60 + 6 = 66, então ganha, mesmo tendo menos vita. Multiplica isso por doze slots, bônus de conjunto e dofus, e saem combinações que ninguém fica conferindo na mão. É essa a sacada: você define as prioridades, ela faz a parte chata.</p>

<h2>As regras que ela nunca quebra</h2>
<p>Otimizar livremente é fácil; otimizar <em>de forma válida</em> é a parte difícil. O solucionador mantém seu build dentro das linhas:</p>
<ul>
<li>As metas de PA, PM e alcance que você travou.</li>
<li>Um item por slot, dois anéis diferentes, bônus de conjunto reais.</li>
<li>Os atributos mínimos que você exigiu (tipo "pelo menos 3000 PV").</li>
<li>Os itens que você proibiu ou travou, e condições como nível ou restrição de classe.</li>
</ul>

<h2>Por que o resultado às vezes surpreende</h2>
<p>Se a sugestão parece estranha, geralmente ela está te dizendo algo: seus pesos estão puxando um contra o outro, ou simplesmente não existe equipamento que cumpra tudo de uma vez. Abaixa um controle, sobe outro, proíbe aquele item que você nunca vai farmar, e roda de novo. Depois de duas ou três passadas você tem um set realmente ajustado pra você, não um build meta copiado que todo mundo usa.</p>

<p><em>Quer ver acontecer? <a href="/setup/">Comece um projeto</a> e veja ele resolver.</em></p>
''',
            },
            'de': {
                'title': 'Wie der Optimierer wirklich arbeitet',
                'desc': "Die meisten Build-Seiten sind eine Tabelle: Du ziehst Items rein, sie addiert. Die Fashionista macht es andersrum, du sagst was du willst, sie findet die Items.",
                'lead': "Die meisten Build-Seiten sind eine hübsche Tabelle: Du ziehst Items rein, sie addiert die Werte. Die Fashionista macht es andersrum, du sagst, was du willst, sie findet die Items.",
                'body': '''
<h2>Es ist ein Optimierungsproblem, keine Liste</h2>
<p>Wenn du deine Regler einstellst, gibst du dem Tool im Grunde eine <strong>Punktzahl</strong> für jeden Wert. Im Hintergrund durchsucht es dann tausende erlaubte Item-Kombinationen und nimmt die mit der höchsten Gesamtpunktzahl, und hält sich dabei an die harten Regeln des Spiels. Das ist echte mathematische Optimierung, dieselbe Sorte Mathe, mit der man Flüge plant oder Lkw belädt, nur eben auf deinen Iop gerichtet.</p>

<h2>Warum Gewichten besser ist als rohe Werte</h2>
<p>Sagen wir, Intelligenz ist dir 1 Punkt wert und Vitalität 0,2. Ein Item mit +40 Int und +100 Vita kommt auf 40 + 20 = 60. Eins mit +60 Int und +30 Vita kommt auf 60 + 6 = 66, also gewinnt es, obwohl es weniger Vita hat. Rechne das über zwölf Plätze, Set-Boni und Dofus hoch, und du bekommst Kombinationen, die kein Mensch von Hand durchprobiert. Genau das ist der Punkt: Du setzt die Prioritäten, es macht den langweiligen Teil.</p>

<h2>Die Regeln, die es nie bricht</h2>
<p>Frei zu optimieren ist leicht; <em>regelkonform</em> zu optimieren ist die Kunst. Der Solver hält dein Build in der Spur:</p>
<ul>
<li>Die AP-, BP- und Reichweiten-Ziele, die du fixiert hast.</li>
<li>Ein Item pro Platz, zwei verschiedene Ringe, echte Set-Boni.</li>
<li>Die Mindestwerte, die du verlangt hast (etwa "mindestens 3000 LP").</li>
<li>Items, die du verboten oder gesperrt hast, und Bedingungen wie Level oder Klassenbeschränkung.</li>
</ul>

<h2>Warum dich das Ergebnis manchmal überrascht</h2>
<p>Wenn der Vorschlag seltsam aussieht, sagt er dir meistens etwas: Deine Gewichte ziehen gegeneinander, oder es gibt schlicht keine Ausrüstung, die alles auf einmal trifft. Regler runter, anderen hoch, das Item verbieten, das du eh nie farmst, und neu rechnen. Nach zwei, drei Durchläufen hast du ein Set, das wirklich auf dich abgestimmt ist, kein kopiertes Meta-Build, das alle anderen tragen.</p>

<p><em>Willst du es live sehen? <a href="/setup/">Starte ein Projekt</a> und schau ihm beim Lösen zu.</em></p>
''',
            },
        },
    },

    # ------------------------------------------------------------------ #
    'stats-explained': {
        'published': '2026-06-30',
        'i18n': {
            'en': {
                'title': 'Dofus stats, and how much each one is worth',
                'desc': "AP, range, damage, vitality, crits… Dofus throws a lot of numbers at you. A no-nonsense rundown of what actually matters and how to weight it.",
                'lead': "AP, range, damage, vitality, crits… Dofus throws a lot of numbers at you. Here's a no-nonsense rundown of what actually matters and how to weight it.",
                'body': '''
<h2>The kingmakers: AP, MP and range</h2>
<p>These three decide what your character can even do on a turn. One more AP can mean a whole extra spell; one more MP is positioning and kiting; range makes or breaks half the classes in the game. They're scarce, every build fights over them, so in the tool you usually <strong>lock them to a target</strong> rather than weight them: "give me exactly 11 AP and 6 MP, then optimize the rest."</p>

<h2>Your damage element</h2>
<p>Your damage comes from one (or more) of Strength, Intelligence, Agility and Chance, each powering the element that matches it. Pick the element your main spells scale with and lean into it: a focused mono-element build almost always out-damages a smeared multi-element one. Your damage element is the engine of any offensive build, so it deserves a high slider.</p>

<h2>Staying alive</h2>
<p>Vitality is raw HP and it's cheap to stack, but more isn't always better: 1000 extra HP you didn't need is a damage stat you threw away. Resistance (flat and %) is what actually keeps you up in PvP and tough fights. For competitive PvP, weight resistance seriously; for mobbing PvM, you can often get away with less.</p>

<h2>The multipliers: Power, Damage, Crit</h2>
<p>Power boosts all your elemental damage at once and is almost always worth a high weight. Flat Damage (+dmg) is strongest on multi-hit, low-base spells; % damage scales with big hits. The percent-damage stats are a Dofus 2-era feature, so they show up on Dofus 3, the beta and Dofus 2 but not on Touch or Retro, where you lean on Power and flat damage instead. Critical hit rate is great <em>if</em> your crits actually add a meaningful bonus: check the spell before you chase it, and note that <a href="/guides/critical-hits/">how critical hits work depends on your version</a>.</p>

<h2>The quiet ones: Wisdom, Prospecting, Initiative, Pods</h2>
<p>Not every build is about damage. Wisdom = XP and resistance to AP/MP loss; Prospecting = drop rate, gold for farmers; Initiative decides turn order; Pods are pure convenience. Give them a small weight when they matter to you and zero when they don't: the optimizer will only chase them if there's no real cost.</p>

<h2>The one rule</h2>
<p>Don't max everything. If every slider is at the top, you've told the tool that nothing matters, which is the same as telling it nothing. Pick your two or three real priorities, weight those high, and let the rest fall where it lands.</p>

<p><em>Ready to put numbers on it? <a href="/setup/">Build it here.</a></em></p>
''',
            },
            'fr': {
                'title': 'Les stats de Dofus, et combien chacune vaut',
                'desc': "PA, portée, dégâts, vitalité, critiques… Dofus te balance un paquet de chiffres. Un topo sans blabla sur ce qui compte vraiment et comment le pondérer.",
                'lead': "PA, portée, dégâts, vitalité, coups critiques… Dofus te balance un paquet de chiffres. Voilà un topo sans blabla sur ce qui compte vraiment et comment le pondérer.",
                'body': '''
<h2>Les rois : PA, PM et portée</h2>
<p>Ces trois-là décident de ce que ton perso peut faire dans un tour, point. Un PA de plus, c'est parfois un sort entier en rab ; un PM de plus, c'est du placement et du kite ; la portée fait ou défait la moitié des classes du jeu. C'est rare, tous les builds se les arrachent, donc dans l'outil tu les <strong>verrouilles à un objectif</strong> plutôt que de les pondérer : "donne-moi exactement 11 PA et 6 PM, puis optimise le reste".</p>

<h2>Ton élément de dégâts</h2>
<p>Tes dégâts viennent d'un (ou plusieurs) parmi Force, Intelligence, Agilité et Chance, chacune alimentant l'élément qui lui correspond. Choisis l'élément sur lequel scalent tes sorts principaux et fonce dessus : un build mono-élément concentré tape presque toujours plus fort qu'un build multi-élément dilué. Ton élément de dégâts est le moteur de tout build offensif, donc il mérite un gros curseur.</p>

<h2>Rester en vie</h2>
<p>La vitalité, c'est des PV bruts et ça s'empile pas cher, mais plus n'est pas toujours mieux : 1000 PV en trop dont t'avais pas besoin, c'est une stat de dégâts jetée à la poubelle. La résistance (fixe et %) c'est ce qui te garde debout en PvP et dans les combats velus. Pour le PvP compétitif, pondère la résistance sérieusement ; en PvM de mob, tu peux souvent t'en passer un peu.</p>

<h2>Les multiplicateurs : Puissance, Dommages, Critique</h2>
<p>La Puissance booste tous tes dégâts élémentaires d'un coup et mérite presque toujours un gros poids. Les Dommages fixes (+dom) sont rois sur les sorts multi-coups à faible base ; les dégâts en % scalent avec les gros coups. Les stats de dégâts en % sont une nouveauté Dofus 2 : on les trouve sur Dofus 3, la bêta et Dofus 2, mais pas sur Touch ni Rétro, où tu comptes plutôt sur la Puissance et les dégâts fixes. Le taux de critique est top <em>si</em> tes crits ajoutent vraiment un bonus qui compte : vérifie le sort avant de courir après, et sache que <a href="/guides/critical-hits/">le fonctionnement des coups critiques dépend de ta version</a>.</p>

<h2>Les discrètes : Sagesse, Prospection, Initiative, Pods</h2>
<p>Tous les builds ne tournent pas autour des dégâts. Sagesse = XP et résistance à la perte de PA/PM ; Prospection = taux de drop, kamas pour les farmeurs ; l'Initiative décide de l'ordre des tours ; les Pods, c'est du confort pur. Mets-leur un petit poids quand ça t'importe et zéro sinon : l'optimiseur ne les chassera que si ça ne coûte rien.</p>

<h2>La seule règle</h2>
<p>Ne monte pas tout à fond. Si tous les curseurs sont au max, t'as dit à l'outil que rien ne compte, ce qui revient à ne rien lui dire. Choisis tes deux-trois vraies priorités, pondère-les haut, et laisse le reste tomber où il tombe.</p>

<p><em>Prêt à mettre des chiffres dessus ? <a href="/setup/">Construis-le ici.</a></em></p>
''',
            },
            'es': {
                'title': 'Las estadísticas de Dofus y cuánto vale cada una',
                'desc': "PA, alcance, daño, vitalidad, críticos… Dofus te tira un montón de números. Un repaso sin rodeos de lo que importa de verdad y cómo ponderarlo.",
                'lead': "PA, alcance, daño, vitalidad, críticos… Dofus te tira un montón de números. Aquí va un repaso sin rodeos de lo que importa de verdad y cómo ponderarlo.",
                'body': '''
<h2>Los que mandan: PA, PM y alcance</h2>
<p>Estos tres deciden lo que tu personaje puede hacer en un turno, y punto. Un PA más a veces es un hechizo entero extra; un PM más es colocación y kiteo; el alcance hace o deshace a la mitad de las clases del juego. Son escasos, todos los builds se pelean por ellos, así que en la herramienta normalmente los <strong>bloqueas a un objetivo</strong> en vez de ponderarlos: "dame exactamente 11 PA y 6 PM, y luego optimiza el resto".</p>

<h2>Tu elemento de daño</h2>
<p>Tu daño sale de uno (o varios) entre Fuerza, Inteligencia, Agilidad y Suerte, y cada una alimenta el elemento que le corresponde. Elige el elemento con el que escalan tus hechizos principales y ve a por él: un build monoelemento concentrado casi siempre pega más que uno multielemento diluido. Tu elemento de daño es el motor de cualquier build ofensivo, así que merece un deslizador alto.</p>

<h2>Seguir vivo</h2>
<p>La vitalidad son PV en bruto y apilarla es barato, pero más no siempre es mejor: 1000 PV de más que no necesitabas es una estadística de daño tirada a la basura. La resistencia (fija y %) es lo que de verdad te mantiene en pie en PvP y en peleas duras. Para el PvP competitivo, pondera la resistencia en serio; en PvM de mobeo, muchas veces puedes ir con menos.</p>

<h2>Los multiplicadores: Potencia, Daños, Crítico</h2>
<p>La Potencia sube todo tu daño elemental de golpe y casi siempre merece un peso alto. Los Daños fijos (+daño) brillan en hechizos multigolpe de base baja; el daño en % escala con los golpazos. Las estadísticas de daño en % son una novedad de Dofus 2: aparecen en Dofus 3, la beta y Dofus 2, pero no en Touch ni Retro, donde te apoyas en la Potencia y el daño fijo. La tasa de crítico es genial <em>si</em> tus críticos suman un bonus que de verdad cuenta: mira el hechizo antes de ir a por ella, y ten en cuenta que <a href="/guides/critical-hits/">cómo funcionan los golpes críticos depende de tu versión</a>.</p>

<h2>Las calladas: Sabiduría, Prospección, Iniciativa, Pods</h2>
<p>No todos los builds van de daño. Sabiduría = XP y resistencia a la pérdida de PA/PM; Prospección = tasa de drop, kamas para farmers; la Iniciativa decide el orden de turnos; los Pods son comodidad pura. Dales un peso pequeño cuando te importan y cero cuando no: el optimizador solo irá a por ellos si no cuesta nada.</p>

<h2>La única regla</h2>
<p>No lo subas todo al máximo. Si todos los deslizadores están arriba, le has dicho a la herramienta que nada importa, que es lo mismo que no decirle nada. Elige tus dos o tres prioridades reales, ponderalas alto, y deja que el resto caiga donde caiga.</p>

<p><em>¿Listo para ponerle números? <a href="/setup/">Constrúyelo aquí.</a></em></p>
''',
            },
            'pt': {
                'title': 'Os atributos de Dofus e quanto cada um vale',
                'desc': "PA, alcance, dano, vitalidade, críticos… Dofus joga um monte de números em você. Um resumo sem enrolação do que importa e como ponderar.",
                'lead': "PA, alcance, dano, vitalidade, críticos… Dofus joga um monte de números em você. Aqui vai um resumo sem enrolação do que importa de verdade e como ponderar.",
                'body': '''
<h2>Os que mandam: PA, PM e alcance</h2>
<p>Esses três decidem o que seu personagem consegue fazer num turno, ponto. Um PA a mais às vezes é um feitiço inteiro extra; um PM a mais é posicionamento e kite; o alcance faz ou quebra metade das classes do jogo. São escassos, todo build briga por eles, então na ferramenta você geralmente os <strong>trava num objetivo</strong> em vez de ponderar: "me dá exatamente 11 PA e 6 PM, e depois otimiza o resto".</p>

<h2>Seu elemento de dano</h2>
<p>Seu dano vem de um (ou mais) entre Força, Inteligência, Agilidade e Sorte, e cada uma alimenta o elemento que lhe corresponde. Escolha o elemento com que seus feitiços principais escalam e vá fundo nele: um build mono-elemento concentrado quase sempre bate mais que um multi-elemento diluído. Seu elemento de dano é o motor de qualquer build ofensivo, então merece um controle alto.</p>

<h2>Continuar vivo</h2>
<p>Vitalidade é PV cru e empilhar é barato, mas mais nem sempre é melhor: 1000 PV a mais de que você não precisava é um atributo de dano jogado fora. Resistência (fixa e %) é o que de fato te mantém em pé no PvP e em lutas pesadas. Pro PvP competitivo, pondere resistência a sério; em PvM de mob, muitas vezes dá pra ir com menos.</p>

<h2>Os multiplicadores: Potência, Danos, Crítico</h2>
<p>A Potência aumenta todo o seu dano elemental de uma vez e quase sempre merece um peso alto. Danos fixos (+dano) brilham em feitiços multi-golpe de base baixa; dano em % escala com golpes grandes. As estatísticas de dano em % são uma novidade do Dofus 2: aparecem no Dofus 3, no beta e no Dofus 2, mas não no Touch nem no Retro, onde você conta com a Potência e o dano fixo. A taxa de crítico é ótima <em>se</em> seus críticos somam um bônus que conta de verdade: confira o feitiço antes de correr atrás, e saiba que <a href="/guides/critical-hits/">como os golpes críticos funcionam depende da sua versão</a>.</p>

<h2>Os quietos: Sabedoria, Prospecção, Iniciativa, Pods</h2>
<p>Nem todo build é sobre dano. Sabedoria = XP e resistência à perda de PA/PM; Prospecção = taxa de drop, kamas pros farmers; a Iniciativa decide a ordem dos turnos; os Pods são puro conforto. Dê um peso pequeno quando importam e zero quando não: o otimizador só vai atrás deles se não custar nada.</p>

<h2>A única regra</h2>
<p>Não suba tudo no máximo. Se todos os controles estão no topo, você disse pra ferramenta que nada importa, o que é o mesmo que não dizer nada. Escolha suas duas ou três prioridades reais, pondere alto, e deixe o resto cair onde cair.</p>

<p><em>Pronto pra colocar números nisso? <a href="/setup/">Monte aqui.</a></em></p>
''',
            },
            'de': {
                'title': 'Dofus-Werte und wie viel jeder wert ist',
                'desc': "AP, Reichweite, Schaden, Vitalität, Kritische… Dofus wirft dir viele Zahlen hin. Ein klarer Überblick, was wirklich zählt und wie du es gewichtest.",
                'lead': "AP, Reichweite, Schaden, Vitalität, Kritische… Dofus wirft dir eine Menge Zahlen hin. Hier ist ein klarer Überblick, was wirklich zählt und wie du es gewichtest.",
                'body': '''
<h2>Die Königsmacher: AP, BP und Reichweite</h2>
<p>Diese drei entscheiden, was deine Figur in einer Runde überhaupt tun kann. Ein AP mehr ist manchmal ein ganzer zusätzlicher Zauber; ein BP mehr ist Positionierung und Kiten; Reichweite macht oder bricht die Hälfte der Klassen im Spiel. Sie sind knapp, jedes Build kämpft darum, deshalb <strong>fixierst</strong> du sie im Tool meist auf ein Ziel, statt sie zu gewichten: "gib mir genau 11 AP und 6 BP, dann optimiere den Rest".</p>

<h2>Dein Schadenselement</h2>
<p>Dein Schaden kommt aus einem (oder mehreren) von Stärke, Intelligenz, Flinkheit und Glück, und jede treibt das Element an, das zu ihr passt. Wähl das Element, mit dem deine Hauptzauber skalieren, und zieh es durch: ein fokussiertes Mono-Element-Build macht fast immer mehr Schaden als ein verwässertes Multi-Element-Build. Dein Schadenselement ist der Motor jedes Angriffs-Builds, also verdient es einen hohen Regler.</p>

<h2>Am Leben bleiben</h2>
<p>Vitalität ist rohes LP und billig zu stapeln, aber mehr ist nicht immer besser: 1000 LP zu viel, die du nicht gebraucht hast, sind ein weggeworfener Schadenswert. Resistenz (fix und %) ist das, was dich in PvP und harten Kämpfen wirklich oben hält. Für kompetitives PvP gewichte Resistenz ernsthaft; beim Mob-PvM kommst du oft mit weniger aus.</p>

<h2>Die Multiplikatoren: Stärke (Power), Schaden, Kritisch</h2>
<p>Power hebt deinen gesamten Elementarschaden auf einmal und verdient fast immer ein hohes Gewicht. Fixer Schaden (+Schaden) ist am stärksten bei Multi-Treffer-Zaubern mit niedriger Basis; %-Schaden skaliert mit großen Treffern. Die Prozent-Schadenswerte sind eine Dofus-2-Neuerung: sie tauchen auf Dofus 3, der Beta und Dofus 2 auf, aber nicht auf Touch oder Retro, wo du stattdessen auf Power und festen Schaden setzt. Kritische Trefferrate ist super, <em>wenn</em> deine Kritischen wirklich einen spürbaren Bonus draufpacken: schau den Zauber an, bevor du ihr hinterherjagst, und beachte, dass <a href="/guides/critical-hits/">wie kritische Treffer funktionieren, von deiner Version abhängt</a>.</p>

<h2>Die Leisen: Weisheit, Prospektion, Initiative, Trageleistung</h2>
<p>Nicht jedes Build dreht sich um Schaden. Weisheit = EP und Widerstand gegen AP/BP-Verlust; Prospektion = Drop-Rate, Kamas für Farmer; Initiative entscheidet die Zugreihenfolge; Trageleistung ist purer Komfort. Gib ihnen ein kleines Gewicht, wenn sie dir wichtig sind, und null, wenn nicht: der Optimierer jagt ihnen nur nach, wenn es nichts kostet.</p>

<h2>Die eine Regel</h2>
<p>Stell nicht alles auf Maximum. Wenn jeder Regler oben ist, hast du dem Tool gesagt, dass nichts zählt, und das ist dasselbe, wie ihm gar nichts zu sagen. Wähl deine zwei, drei echten Prioritäten, gewichte die hoch, und lass den Rest fallen, wo er fällt.</p>

<p><em>Bereit, Zahlen draufzulegen? <a href="/setup/">Bau es hier.</a></em></p>
''',
            },
        },
    },

    # ------------------------------------------------------------------ #
    'versions-explained': {
        'published': '2026-06-30',
        'i18n': {
            'en': {
                'title': "Dofus 3, Beta, Dofus 2, Retro, Touch: which do you play?",
                'desc': "One thing that sets the Fashionista apart: it covers five flavors of Dofus, not just the live one. Here's what each is, who plays it, and how to switch.",
                'lead': "One thing that sets the Fashionista apart: it covers five flavors of Dofus, not just the live one. Here's the quick map so you optimize on the right data.",
                'body': '''
<h2>Why this even matters</h2>
<p>Item stats, recipes and spells are different across versions. A build that's perfect on the live game can be nonsense on Retro, where half the items don't exist and the rules are old-school. So the first thing to get right is: which version are you actually playing? Pick it when you create a project, or switch any time with the version selector at the top of the page.</p>

<h2>Dofus 3 (live)</h2>
<p>The current game. This is the default, kept up to date with the latest patch, including the 3.6 characteristic rework and the newest items. If you just play Dofus on a regular server, this is you.</p>

<h2>Beta</h2>
<p>The test server, where Ankama trials upcoming changes before they go live. Handy if you want to plan a build around what's coming. Just remember the data moves around and can change overnight: it's a preview, not gospel.</p>

<h2>Dofus 2</h2>
<p>The classic 2.x era many players still think of as "real" Dofus. Different item pool and balance from Dofus 3, so it gets its own dataset.</p>

<h2>Retro (1.29)</h2>
<p>Dofus Retro: the old-school 1.29 servers. Way fewer items, no elemental damage runes, simpler everything. The optimizer knows the 1.29 rules, so it won't suggest gear or stats that didn't exist back then.</p>

<h2>Touch</h2>
<p>Dofus Touch, the mobile version, which sits on its own balance and item list (some trophies, for instance, cap set bonuses differently). Its own dataset too, so your mobile builds are accurate.</p>

<p><em>On the right version? <a href="/setup/">Create your project</a> and the tool only shows what exists there.</em></p>
''',
            },
            'fr': {
                'title': "Dofus 3, Bêta, Dofus 2, Retro, Touch : ta version ?",
                'desc': "Un truc qui distingue la Fashionista : elle couvre cinq versions de Dofus, pas juste la live. Voilà ce qu'est chacune, qui y joue, et comment switcher.",
                'lead': "Un truc qui distingue la Fashionista : elle couvre cinq versions de Dofus, pas juste la live. Voilà la carte rapide pour optimiser sur les bonnes données.",
                'body': '''
<h2>Pourquoi ça compte</h2>
<p>Les stats des items, les recettes et les sorts changent d'une version à l'autre. Un build parfait sur la live peut être n'importe quoi sur Retro, où la moitié des items n'existe pas et où les règles sont à l'ancienne. Donc le premier truc à caler, c'est : tu joues à quelle version, vraiment ? Choisis-la en créant ton projet, ou change quand tu veux avec le sélecteur de version en haut de la page.</p>

<h2>Dofus 3 (live)</h2>
<p>Le jeu actuel. C'est le défaut, tenu à jour avec le dernier patch, refonte des caracs 3.6 et derniers items inclus. Si tu joues juste à Dofus sur un serveur classique, c'est toi.</p>

<h2>Bêta</h2>
<p>Le serveur de test, là où Ankama essaie les changements à venir avant qu'ils passent en live. Pratique pour préparer un build autour de ce qui arrive. Garde juste en tête que la donnée bouge et peut changer du jour au lendemain : c'est un aperçu, pas parole d'évangile.</p>

<h2>Dofus 2</h2>
<p>L'ère classique 2.x que beaucoup considèrent encore comme le "vrai" Dofus. Pool d'items et équilibrage différents de Dofus 3, donc elle a son propre jeu de données.</p>

<h2>Retro (1.29)</h2>
<p>Dofus Retro : les serveurs 1.29 à l'ancienne. Beaucoup moins d'items, pas de runes de dégâts élémentaires, tout plus simple. L'optimiseur connaît les règles 1.29, donc il ne te proposera pas un stuff ou des stats qui n'existaient pas à l'époque.</p>

<h2>Touch</h2>
<p>Dofus Touch, la version mobile, avec son propre équilibrage et sa propre liste d'items (certains trophées, par exemple, plafonnent les bonus de panoplie différemment). Son propre jeu de données aussi, pour que tes builds mobile soient justes.</p>

<p><em>Sur la bonne version ? <a href="/setup/">Crée ton projet</a> et l'outil n'affiche que ce qui existe là-bas.</em></p>
''',
            },
            'es': {
                'title': 'Dofus 3, Beta, Dofus 2, Retro, Touch: ¿en cuál juegas?',
                'desc': "Algo que distingue a la Fashionista: cubre cinco versiones de Dofus, no solo la live. Aquí tienes qué es cada una, quién la juega y cómo cambiar.",
                'lead': "Algo que distingue a la Fashionista: cubre cinco versiones de Dofus, no solo la live. Aquí va el mapa rápido para que optimices con los datos correctos.",
                'body': '''
<h2>Por qué importa</h2>
<p>Las estadísticas de los ítems, las recetas y los hechizos cambian entre versiones. Un build perfecto en la live puede ser un disparate en Retro, donde la mitad de los ítems no existe y las reglas son a la antigua. Así que lo primero que hay que acertar es: ¿en qué versión juegas de verdad? Elígela al crear el proyecto, o cámbiala cuando quieras con el selector de versión arriba.</p>

<h2>Dofus 3 (live)</h2>
<p>El juego actual. Es la opción por defecto, al día con el último parche, incluido el rework de características de 3.6 y los ítems más nuevos. Si juegas a Dofus en un servidor normal, esta eres tú.</p>

<h2>Beta</h2>
<p>El servidor de pruebas, donde Ankama ensaya los cambios que vienen antes de que lleguen a la live. Útil para planear un build alrededor de lo que viene. Solo recuerda que los datos se mueven y pueden cambiar de un día para otro: es un adelanto, no una verdad absoluta.</p>

<h2>Dofus 2</h2>
<p>La era clásica 2.x que muchos siguen considerando el "Dofus de verdad". Conjunto de ítems y balance distintos de Dofus 3, así que tiene su propio set de datos.</p>

<h2>Retro (1.29)</h2>
<p>Dofus Retro: los servidores 1.29 de la vieja escuela. Muchos menos ítems, sin runas de daño elemental, todo más simple. El optimizador conoce las reglas de 1.29, así que no te sugerirá equipo ni estadísticas que no existían entonces.</p>

<h2>Touch</h2>
<p>Dofus Touch, la versión móvil, con su propio balance y lista de ítems (algunos trofeos, por ejemplo, limitan los bonus de panoplia de otra forma). También con su propio set de datos, para que tus builds de móvil sean exactos.</p>

<p><em>¿En la versión correcta? <a href="/setup/">Crea tu proyecto</a> y la herramienta solo mostrará lo que existe ahí.</em></p>
''',
            },
            'pt': {
                'title': 'Dofus 3, Beta, Dofus 2, Retro, Touch: em qual você joga?',
                'desc': "Uma coisa que diferencia a Fashionista: ela cobre cinco versões de Dofus, não só a live. Veja o que é cada uma, quem joga e como trocar.",
                'lead': "Uma coisa que diferencia a Fashionista: ela cobre cinco versões de Dofus, não só a live. Aqui vai o mapa rápido pra você otimizar com os dados certos.",
                'body': '''
<h2>Por que isso importa</h2>
<p>Os atributos dos itens, as receitas e os feitiços mudam de uma versão pra outra. Um build perfeito na live pode ser uma furada no Retro, onde metade dos itens não existe e as regras são old-school. Então a primeira coisa a acertar é: em qual versão você joga de verdade? Escolha ao criar o projeto, ou troque quando quiser no seletor de versão no topo da página.</p>

<h2>Dofus 3 (live)</h2>
<p>O jogo atual. É o padrão, mantido em dia com o último patch, incluindo a reformulação de características da 3.6 e os itens mais novos. Se você joga Dofus num servidor normal, é você.</p>

<h2>Beta</h2>
<p>O servidor de testes, onde a Ankama experimenta as mudanças que vêm aí antes de irem pra live. Útil pra planejar um build em torno do que está chegando. Só lembre que os dados mudam e podem virar de uma hora pra outra: é uma prévia, não verdade absoluta.</p>

<h2>Dofus 2</h2>
<p>A era clássica 2.x que muita gente ainda considera o "Dofus de verdade". Conjunto de itens e balanceamento diferentes da Dofus 3, então tem seu próprio conjunto de dados.</p>

<h2>Retro (1.29)</h2>
<p>Dofus Retro: os servidores 1.29 da velha escola. Muito menos itens, sem runas de dano elemental, tudo mais simples. O otimizador conhece as regras da 1.29, então não vai sugerir equipamento nem atributos que não existiam na época.</p>

<h2>Touch</h2>
<p>Dofus Touch, a versão mobile, com seu próprio balanceamento e lista de itens (alguns troféus, por exemplo, limitam os bônus de conjunto de outro jeito). Também com seu próprio conjunto de dados, pra seus builds de celular saírem certos.</p>

<p><em>Na versão certa? <a href="/setup/">Crie seu projeto</a> e a ferramenta só mostra o que existe ali.</em></p>
''',
            },
            'de': {
                'title': 'Dofus 3, Beta, Dofus 2, Retro, Touch: welches spielst du?',
                'desc': "Eine Sache hebt die Fashionista ab: Sie deckt fünf Dofus-Varianten ab, nicht nur die Live-Version. Was jede ist, wer sie spielt und wie du umschaltest.",
                'lead': "Eine Sache hebt die Fashionista ab: Sie deckt fünf Spielarten von Dofus ab, nicht nur die Live-Version. Hier ist die schnelle Übersicht, damit du mit den richtigen Daten optimierst.",
                'body': '''
<h2>Warum das überhaupt wichtig ist</h2>
<p>Item-Werte, Rezepte und Zauber unterscheiden sich zwischen den Versionen. Ein Build, das auf dem Live-Spiel perfekt ist, kann auf Retro Unsinn sein, wo die Hälfte der Items nicht existiert und die Regeln altmodisch sind. Das Erste, was du richtig setzen musst, ist also: Welche Version spielst du eigentlich? Wähl sie beim Anlegen eines Projekts, oder wechsle jederzeit mit der Versionsauswahl oben auf der Seite.</p>

<h2>Dofus 3 (live)</h2>
<p>Das aktuelle Spiel. Das ist die Voreinstellung, auf dem neuesten Patch gehalten, inklusive Charakterwerte-Rework der 3.6 und der neuesten Items. Wenn du einfach Dofus auf einem normalen Server spielst, bist das du.</p>

<h2>Beta</h2>
<p>Der Testserver, auf dem Ankama kommende Änderungen ausprobiert, bevor sie live gehen. Praktisch, um ein Build um das zu planen, was kommt. Denk nur dran, dass sich die Daten verschieben und über Nacht ändern können: es ist eine Vorschau, kein Evangelium.</p>

<h2>Dofus 2</h2>
<p>Die klassische 2.x-Ära, die viele immer noch als das "echte" Dofus sehen. Anderer Item-Pool und Balance als Dofus 3, also bekommt es seinen eigenen Datensatz.</p>

<h2>Retro (1.29)</h2>
<p>Dofus Retro: die altmodischen 1.29-Server. Viel weniger Items, keine Elementarschaden-Runen, alles simpler. Der Optimierer kennt die 1.29-Regeln und schlägt dir daher keine Ausrüstung oder Werte vor, die es damals nicht gab.</p>

<h2>Touch</h2>
<p>Dofus Touch, die mobile Version, mit eigener Balance und Item-Liste (manche Trophäen deckeln zum Beispiel Set-Boni anders). Ebenfalls mit eigenem Datensatz, damit deine Mobile-Builds stimmen.</p>

<p><em>Auf der richtigen Version? <a href="/setup/">Erstell dein Projekt</a> und das Tool zeigt nur, was es dort gibt.</em></p>
''',
            },
        },
    },

    # Kolossium (ranked PvP) exists on modern Dofus (Dofus 3, beta, Dofus 2,
    # Touch) but NOT on Dofus Retro (1.29), so this guide serves a Retro variant
    # framed around its two real poles, PvM and PvP, with the same weighting
    # advice. Retro 1.29 also has no alliances/prisms (a Dofus 2.x feature), so
    # the Retro copy avoids naming any mode that does not exist there.
    # ------------------------------------------------------------------ #
    'game-modes': {
        'published': '2026-07-01',
        'version_groups': {'retro': 'retro'},
        'i18n_by_group': {
            'modern': {
            'en': {
                'title': "Building for PvM, PvP and Kolossium",
                'desc': "The same character needs a different build for farming dungeons, dueling, or grinding Kolossium. How to weight each one without rebuilding from scratch.",
                'lead': "The same character needs a different build depending on whether you're farming dungeons, dueling, or grinding Kolossium. Same items, different priorities: here's how to weight each.",
                'body': '''
<h2>Why one build isn't enough</h2>
<p>Your gear doesn't change, but what you ask of it does. A PvM farm set wants to delete monsters before they matter; a Kolossium set wants to still be standing on turn ten. Pour the same items into both and you'll be mediocre at each. The trick isn't owning three stuffs, it's telling the optimizer what <strong>this</strong> set is for and saving it as its own project.</p>

<h2>PvM: kill fast, survive enough</h2>
<p>Against monsters you usually know the fight, so you can lean into offense. Weight your element and Power high, push flat and percent damage, and keep just enough vitality and resistance to clear the dungeon you actually run. No opponent is reading your build, so dumping defensive stats for raw damage is often correct. Lock your AP, MP and range to hit your spell combo, then let the tool pour everything else into killing power.</p>

<h2>PvP and Kolossium: resistance wins games</h2>
<p>Now someone is actively trying to ruin your turn. Flat and percent resistance jump to the top of your weights: surviving a burst is worth more than a slightly bigger hit you might not land. Wisdom matters too: it cuts how much AP and MP an enemy can strip from you, and getting locked out of your kit loses fights. Keep your damage element, but balance it against staying alive, and value range and MP for the positioning game.</p>

<h2>The three you always lock</h2>
<p>Whatever the mode, AP, MP and range are targets, not sliders. Decide the breakpoints your spells need (say 11 AP, 6 MP, 4 range) and lock them. The optimizer then spends every remaining stat point on what changes between modes, instead of wasting gear hitting an AP number you never asked for.</p>

<h2>Do it in the tool</h2>
<p>Make one project per mode. Start from your PvM set, duplicate it, drag resistance and Wisdom up, drag a little damage down, and re-tailor, you've got a Kolossium variant in under a minute. Then throw both into the <a href="/choose_compare_sets/">comparison</a> to see exactly what you trade. That side-by-side is the fastest way to understand your own build.</p>

<p><em>Pick a mode and tune it: <a href="/setup/">start a project.</a></em></p>
''',
            },
            'fr': {
                'title': "Optimiser son stuff pour le PvM, le PvP et le Kolizéum",
                'desc': "Le même perso a besoin d'un build différent pour farmer du donjon, dueller ou grind le Kolizéum. Comment pondérer chacun sans tout refaire de zéro.",
                'lead': "Le même perso a besoin d'un build différent selon que tu farmes du donjon, que tu duelles ou que tu grind le Kolizéum. Mêmes items, priorités différentes : voilà comment pondérer chacun.",
                'body': '''
<h2>Pourquoi un seul build ne suffit pas</h2>
<p>Ton stuff ne change pas, mais ce que tu lui demandes, si. Un set de farm PvM veut effacer les monstres avant qu'ils comptent ; un set Kolizéum veut être encore debout au tour dix. Mets les mêmes items dans les deux et tu seras moyen partout. L'astuce, c'est pas d'avoir trois stuffs, c'est de dire à l'optimiseur à quoi sert <strong>ce</strong> set-là et de le sauvegarder comme projet à part.</p>

<h2>PvM : tuer vite, survivre assez</h2>
<p>Contre les monstres tu connais souvent le combat, donc tu peux miser sur l'attaque. Pondère ton élément et la Puissance haut, pousse les dommages fixes et en %, et garde juste assez de vita et de résistance pour clean le donjon que tu fais vraiment. Personne ne lit ton build en face, donc sacrifier du défensif pour du dégât brut est souvent le bon choix. Verrouille tes PA, PM et portée pour sortir ton combo, puis laisse l'outil tout mettre dans la puissance de frappe.</p>

<h2>PvP et Kolizéum : la résistance gagne les matchs</h2>
<p>Là, quelqu'un essaie activement de pourrir ton tour. La résistance fixe et en % grimpe en haut de tes poids : encaisser un burst vaut plus qu'un coup à peine plus gros que tu vas peut-être rater. La Sagesse compte aussi : elle réduit les PA et PM qu'un ennemi peut te retirer, et se faire lock hors de son kit, ça perd des combats. Garde ton élément de dégâts, mais équilibre-le avec la survie, et valorise la portée et les PM pour le jeu de placement.</p>

<h2>Les trois que tu verrouilles toujours</h2>
<p>Peu importe le mode, PA, PM et portée sont des objectifs, pas des curseurs. Décide les paliers dont tes sorts ont besoin (genre 11 PA, 6 PM, 4 de portée) et verrouille-les. L'optimiseur dépense alors chaque point de stat restant sur ce qui change entre les modes, au lieu de gaspiller du stuff à atteindre un nombre de PA que t'as pas demandé.</p>

<h2>Fais-le dans l'outil</h2>
<p>Crée un projet par mode. Pars de ton set PvM, duplique-le, monte la résistance et la Sagesse, baisse un peu les dégâts, et retaille, t'as une variante Kolizéum en moins d'une minute. Puis balance les deux dans le <a href="/choose_compare_sets/">comparateur</a> pour voir exactement ce que tu échanges. Ce côte-à-côte, c'est le moyen le plus rapide de comprendre ton propre build.</p>

<p><em>Choisis un mode et règle-le : <a href="/setup/">lance un projet.</a></em></p>
''',
            },
            'es': {
                'title': "Optimizar tu build para PvM, PvP y Koliseo",
                'desc': "El mismo personaje necesita un build distinto para farmear mazmorras, duelear o grindear Koliseo. Cómo ponderar cada uno sin rehacerlo todo de cero.",
                'lead': "El mismo personaje necesita un build distinto según si farmeas mazmorras, dueleas o grindeas Koliseo. Mismos ítems, prioridades distintas: aquí tienes cómo ponderar cada uno.",
                'body': '''
<h2>Por qué un solo build no basta</h2>
<p>Tu equipo no cambia, pero lo que le pides sí. Un set de farmeo PvM quiere borrar a los monstruos antes de que importen; un set de Koliseo quiere seguir en pie en el turno diez. Mete los mismos ítems en ambos y serás mediocre en los dos. El truco no es tener tres sets, es decirle al optimizador para qué sirve <strong>este</strong> set y guardarlo como su propio proyecto.</p>

<h2>PvM: matar rápido, sobrevivir lo justo</h2>
<p>Contra monstruos sueles conocer la pelea, así que puedes apostar por el ataque. Pondera tu elemento y la Potencia alto, sube el daño fijo y en %, y guarda solo la vita y resistencia que necesites para limpiar la mazmorra que de verdad haces. Nadie lee tu build enfrente, así que sacrificar defensa por daño bruto suele ser lo correcto. Bloquea tus PA, PM y alcance para sacar tu combo, y deja que la herramienta lo meta todo en poder de daño.</p>

<h2>PvP y Koliseo: la resistencia gana partidas</h2>
<p>Ahora alguien intenta activamente arruinarte el turno. La resistencia fija y en % sube a lo más alto de tus pesos: aguantar un burst vale más que un golpe algo mayor que quizá falles. La Sabiduría también cuenta: reduce los PA y PM que un enemigo puede quitarte, y quedarte bloqueado fuera de tu kit pierde combates. Mantén tu elemento de daño, pero equilíbralo con sobrevivir, y valora el alcance y los PM para el juego de posición.</p>

<h2>Los tres que siempre bloqueas</h2>
<p>Da igual el modo, PA, PM y alcance son objetivos, no deslizadores. Decide los umbrales que tus hechizos necesitan (pongamos 11 PA, 6 PM, 4 de alcance) y bloquéalos. El optimizador gasta entonces cada punto restante en lo que cambia entre modos, en vez de malgastar equipo llegando a un número de PA que no pediste.</p>

<h2>Hazlo en la herramienta</h2>
<p>Haz un proyecto por modo. Parte de tu set PvM, duplícalo, sube resistencia y Sabiduría, baja un poco el daño, y vuelve a crear el set, tienes una variante de Koliseo en menos de un minuto. Luego mete ambos en el <a href="/choose_compare_sets/">comparador</a> para ver exactamente qué cambias. Ese lado a lado es la forma más rápida de entender tu propio build.</p>

<p><em>Elige un modo y ajústalo: <a href="/setup/">empieza un proyecto.</a></em></p>
''',
            },
            'pt': {
                'title': "Otimizar seu build para PvM, PvP e Koliseu",
                'desc': "O mesmo personagem precisa de um build diferente conforme você farma masmorra, duela ou grinda Koliseu. Veja como ponderar cada um sem refazer tudo do zero.",
                'lead': "O mesmo personagem precisa de um build diferente conforme você farma masmorra, duela ou grinda Koliseu. Mesmos itens, prioridades diferentes: veja como ponderar cada um.",
                'body': '''
<h2>Por que um build só não basta</h2>
<p>Seu equipamento não muda, mas o que você pede dele muda. Um set de farm PvM quer apagar os monstros antes que eles importem; um set de Koliseu quer continuar de pé no turno dez. Coloque os mesmos itens nos dois e você fica mediano em ambos. O truque não é ter três sets, é dizer ao otimizador pra que serve <strong>este</strong> set e salvá-lo como um projeto próprio.</p>

<h2>PvM: matar rápido, sobreviver o suficiente</h2>
<p>Contra monstros você costuma conhecer a luta, então dá pra apostar no ataque. Pondere seu elemento e a Potência alto, suba o dano fixo e em %, e mantenha só a vita e resistência que precisa pra limpar a masmorra que você realmente faz. Ninguém lê seu build do outro lado, então sacrificar defesa por dano bruto costuma ser o certo. Trave seus PA, PM e alcance pra sair seu combo, e deixe a ferramenta jogar todo o resto em poder de dano.</p>

<h2>PvP e Koliseu: resistência ganha partidas</h2>
<p>Agora alguém está tentando ativamente estragar seu turno. Resistência fixa e em % sobe pro topo dos seus pesos: aguentar um burst vale mais que um golpe um pouco maior que você talvez erre. Sabedoria também conta: ela reduz os PA e PM que um inimigo pode te tirar, e ficar travado fora do seu kit perde lutas. Mantenha seu elemento de dano, mas equilibre com sobreviver, e valorize alcance e PM pro jogo de posição.</p>

<h2>Os três que você sempre trava</h2>
<p>Não importa o modo, PA, PM e alcance são metas, não controles. Decida os limiares que seus feitiços precisam (digamos 11 PA, 6 PM, 4 de alcance) e trave. O otimizador então gasta cada ponto restante no que muda entre os modos, em vez de desperdiçar equipamento batendo num número de PA que você não pediu.</p>

<h2>Faça na ferramenta</h2>
<p>Faça um projeto por modo. Comece do seu set PvM, duplique, suba resistência e Sabedoria, abaixe um pouco o dano, e refaça o set, você tem uma variante de Koliseu em menos de um minuto. Depois jogue os dois no <a href="/choose_compare_sets/">comparador</a> pra ver exatamente o que você troca. Esse lado a lado é o jeito mais rápido de entender seu próprio build.</p>

<p><em>Escolha um modo e ajuste: <a href="/setup/">comece um projeto.</a></em></p>
''',
            },
            'de': {
                'title': "Builds für PvM, PvP und Kolosseum",
                'desc': "Derselbe Charakter braucht je nach Modus ein anderes Build: Dungeons farmen, duellieren oder Kolosseum grinden. So gewichtest du jeden, ohne alles neu zu bauen.",
                'lead': "Derselbe Charakter braucht je nach dem ein anderes Build, ob du Dungeons farmst, duellierst oder Kolosseum grindest. Gleiche Items, andere Prioritäten: so gewichtest du jeden.",
                'body': '''
<h2>Warum ein Build nicht reicht</h2>
<p>Deine Ausrüstung ändert sich nicht, aber was du von ihr verlangst, schon. Ein PvM-Farmset will Monster löschen, bevor sie zählen; ein Kolosseum-Set will in Runde zehn noch stehen. Steck dieselben Items in beide und du bist überall mittelmäßig. Der Trick ist nicht, drei Sets zu besitzen, sondern dem Optimierer zu sagen, wofür <strong>dieses</strong> Set ist, und es als eigenes Projekt zu speichern.</p>

<h2>PvM: schnell töten, genug überleben</h2>
<p>Gegen Monster kennst du den Kampf meist, also kannst du auf Angriff setzen. Gewichte dein Element und Power hoch, drück fixen und prozentualen Schaden, und behalte nur so viel Vita und Resistenz, wie du für den Dungeon brauchst, den du wirklich läufst. Niemand liest gegenüber dein Build, also ist es oft richtig, Defensive für rohen Schaden zu opfern. Fixier deine AP, BP und Reichweite für dein Combo, und lass das Tool alles andere in Schlagkraft stecken.</p>

<h2>PvP und Kolosseum: Resistenz gewinnt Partien</h2>
<p>Jetzt versucht jemand aktiv, dir die Runde zu ruinieren. Fixe und prozentuale Resistenz springen an die Spitze deiner Gewichte: einen Burst zu überleben ist mehr wert als ein etwas größerer Treffer, den du vielleicht nicht landest. Weisheit zählt auch: Sie senkt, wie viel AP und BP ein Gegner dir abziehen kann, und aus dem eigenen Kit gesperrt zu werden, verliert Kämpfe. Behalte dein Schadenselement, aber wäge es gegen Überleben ab, und schätze Reichweite und BP fürs Positionsspiel.</p>

<h2>Die drei, die du immer fixierst</h2>
<p>Egal welcher Modus, AP, BP und Reichweite sind Ziele, keine Regler. Leg die Schwellen fest, die deine Zauber brauchen (sagen wir 11 AP, 6 BP, 4 Reichweite) und fixier sie. Der Optimierer gibt dann jeden übrigen Statpunkt für das aus, was sich zwischen den Modi ändert, statt Ausrüstung zu verschwenden, um eine AP-Zahl zu treffen, die du nie verlangt hast.</p>

<h2>Mach es im Tool</h2>
<p>Leg pro Modus ein Projekt an. Starte von deinem PvM-Set, dupliziere es, zieh Resistenz und Weisheit hoch, etwas Schaden runter, und schneider neu, du hast in unter einer Minute eine Kolosseum-Variante. Wirf dann beide in den <a href="/choose_compare_sets/">Vergleich</a>, um genau zu sehen, was du eintauschst. Dieses Nebeneinander ist der schnellste Weg, dein eigenes Build zu verstehen.</p>

<p><em>Wähl einen Modus und stell ihn ein: <a href="/setup/">starte ein Projekt.</a></em></p>
''',
            },
            },
            'retro': {
                'en': {
                    'title': "Building for PvM and PvP",
                    'desc': "The same character needs a different build for farming dungeons or fighting other players. How to weight each one without rebuilding from scratch.",
                    'lead': "The same character needs a different build depending on whether you're farming dungeons or fighting other players. Same items, different priorities: here's how to weight each.",
                    'body': '''
<h2>Why one build isn't enough</h2>
<p>Your gear doesn't change, but what you ask of it does. A PvM farm set wants to delete monsters before they matter; a PvP set wants to still be standing on turn ten. Pour the same items into both and you'll be mediocre at each. The trick isn't owning several stuffs, it's telling the optimizer what <strong>this</strong> set is for and saving it as its own project.</p>

<h2>PvM: kill fast, survive enough</h2>
<p>Against monsters you usually know the fight, so you can lean into offense. Weight your element and Power high, push flat and percent damage, and keep just enough vitality and resistance to clear the dungeon you actually run. No opponent is reading your build, so dumping defensive stats for raw damage is often correct. Lock your AP, MP and range to hit your spell combo, then let the tool pour everything else into killing power.</p>

<h2>PvP: resistance wins fights</h2>
<p>Now someone is actively trying to ruin your turn. Flat and percent resistance jump to the top of your weights: surviving a burst is worth more than a slightly bigger hit you might not land. Wisdom matters too: it cuts how much AP and MP an enemy can strip from you, and getting locked out of your kit loses fights. Keep your damage element, but balance it against staying alive, and value range and MP for the positioning game.</p>

<h2>The three you always lock</h2>
<p>Whatever the mode, AP, MP and range are targets, not sliders. Decide the breakpoints your spells need (say 11 AP, 6 MP, 4 range) and lock them. The optimizer then spends every remaining stat point on what changes between modes, instead of wasting gear hitting an AP number you never asked for.</p>

<h2>Do it in the tool</h2>
<p>Make one project per mode. Start from your PvM set, duplicate it, drag resistance and Wisdom up, drag a little damage down, and re-tailor, you've got a PvP variant in under a minute. Then throw both into the <a href="/choose_compare_sets/">comparison</a> to see exactly what you trade. That side-by-side is the fastest way to understand your own build.</p>

<p><em>Pick a mode and tune it: <a href="/setup/">start a project.</a></em></p>
''',
                },
                'fr': {
                    'title': "Optimiser son stuff pour le PvM et le PvP",
                    'desc': "Le même perso a besoin d'un build différent pour farmer du donjon ou affronter d'autres joueurs. Comment pondérer chacun sans tout refaire de zéro.",
                    'lead': "Le même perso a besoin d'un build différent selon que tu farmes du donjon ou que tu affrontes d'autres joueurs. Mêmes items, priorités différentes : voilà comment pondérer chacun.",
                    'body': '''
<h2>Pourquoi un seul build ne suffit pas</h2>
<p>Ton stuff ne change pas, mais ce que tu lui demandes, si. Un set de farm PvM veut effacer les monstres avant qu'ils comptent ; un set PvP veut être encore debout au tour dix. Mets les mêmes items dans les deux et tu seras moyen partout. L'astuce, c'est pas d'avoir plusieurs stuffs, c'est de dire à l'optimiseur à quoi sert <strong>ce</strong> set-là et de le sauvegarder comme projet à part.</p>

<h2>PvM : tuer vite, survivre assez</h2>
<p>Contre les monstres tu connais souvent le combat, donc tu peux miser sur l'attaque. Pondère ton élément et la Puissance haut, pousse les dommages fixes et en %, et garde juste assez de vita et de résistance pour clean le donjon que tu fais vraiment. Personne ne lit ton build en face, donc sacrifier du défensif pour du dégât brut est souvent le bon choix. Verrouille tes PA, PM et portée pour sortir ton combo, puis laisse l'outil tout mettre dans la puissance de frappe.</p>

<h2>PvP : la résistance gagne les matchs</h2>
<p>Là, quelqu'un essaie activement de pourrir ton tour. La résistance fixe et en % grimpe en haut de tes poids : encaisser un burst vaut plus qu'un coup à peine plus gros que tu vas peut-être rater. La Sagesse compte aussi : elle réduit les PA et PM qu'un ennemi peut te retirer, et se faire lock hors de son kit, ça perd des combats. Garde ton élément de dégâts, mais équilibre-le avec la survie, et valorise la portée et les PM pour le jeu de placement.</p>

<h2>Les trois que tu verrouilles toujours</h2>
<p>Peu importe le mode, PA, PM et portée sont des objectifs, pas des curseurs. Décide les paliers dont tes sorts ont besoin (genre 11 PA, 6 PM, 4 de portée) et verrouille-les. L'optimiseur dépense alors chaque point de stat restant sur ce qui change entre les modes, au lieu de gaspiller du stuff à atteindre un nombre de PA que t'as pas demandé.</p>

<h2>Fais-le dans l'outil</h2>
<p>Crée un projet par mode. Pars de ton set PvM, duplique-le, monte la résistance et la Sagesse, baisse un peu les dégâts, et retaille, t'as une variante PvP en moins d'une minute. Puis balance les deux dans le <a href="/choose_compare_sets/">comparateur</a> pour voir exactement ce que tu échanges. Ce côte-à-côte, c'est le moyen le plus rapide de comprendre ton propre build.</p>

<p><em>Choisis un mode et règle-le : <a href="/setup/">lance un projet.</a></em></p>
''',
                },
                'es': {
                    'title': "Optimizar tu build para PvM y PvP",
                    'desc': "El mismo personaje necesita un build distinto para farmear mazmorras o enfrentarte a otros jugadores. Cómo ponderar cada uno sin rehacerlo todo de cero.",
                    'lead': "El mismo personaje necesita un build distinto según si farmeas mazmorras o te enfrentas a otros jugadores. Mismos ítems, prioridades distintas: aquí tienes cómo ponderar cada uno.",
                    'body': '''
<h2>Por qué un solo build no basta</h2>
<p>Tu equipo no cambia, pero lo que le pides sí. Un set de farmeo PvM quiere borrar a los monstruos antes de que importen; un set de PvP quiere seguir en pie en el turno diez. Mete los mismos ítems en ambos y serás mediocre en los dos. El truco no es tener varios sets, es decirle al optimizador para qué sirve <strong>este</strong> set y guardarlo como su propio proyecto.</p>

<h2>PvM: matar rápido, sobrevivir lo justo</h2>
<p>Contra monstruos sueles conocer la pelea, así que puedes apostar por el ataque. Pondera tu elemento y la Potencia alto, sube el daño fijo y en %, y guarda solo la vita y resistencia que necesites para limpiar la mazmorra que de verdad haces. Nadie lee tu build enfrente, así que sacrificar defensa por daño bruto suele ser lo correcto. Bloquea tus PA, PM y alcance para sacar tu combo, y deja que la herramienta lo meta todo en poder de daño.</p>

<h2>PvP: la resistencia gana partidas</h2>
<p>Ahora alguien intenta activamente arruinarte el turno. La resistencia fija y en % sube a lo más alto de tus pesos: aguantar un burst vale más que un golpe algo mayor que quizá falles. La Sabiduría también cuenta: reduce los PA y PM que un enemigo puede quitarte, y quedarte bloqueado fuera de tu kit pierde combates. Mantén tu elemento de daño, pero equilíbralo con sobrevivir, y valora el alcance y los PM para el juego de posición.</p>

<h2>Los tres que siempre bloqueas</h2>
<p>Da igual el modo, PA, PM y alcance son objetivos, no deslizadores. Decide los umbrales que tus hechizos necesitan (pongamos 11 PA, 6 PM, 4 de alcance) y bloquéalos. El optimizador gasta entonces cada punto restante en lo que cambia entre modos, en vez de malgastar equipo llegando a un número de PA que no pediste.</p>

<h2>Hazlo en la herramienta</h2>
<p>Haz un proyecto por modo. Parte de tu set PvM, duplícalo, sube resistencia y Sabiduría, baja un poco el daño, y vuelve a crear el set, tienes una variante de PvP en menos de un minuto. Luego mete ambos en el <a href="/choose_compare_sets/">comparador</a> para ver exactamente qué cambias. Ese lado a lado es la forma más rápida de entender tu propio build.</p>

<p><em>Elige un modo y ajústalo: <a href="/setup/">empieza un proyecto.</a></em></p>
''',
                },
                'pt': {
                    'title': "Otimizar seu build para PvM e PvP",
                    'desc': "O mesmo personagem precisa de um build diferente conforme você farma masmorra ou enfrenta outros jogadores. Veja como ponderar cada um sem refazer tudo do zero.",
                    'lead': "O mesmo personagem precisa de um build diferente conforme você farma masmorra ou enfrenta outros jogadores. Mesmos itens, prioridades diferentes: veja como ponderar cada um.",
                    'body': '''
<h2>Por que um build só não basta</h2>
<p>Seu equipamento não muda, mas o que você pede dele muda. Um set de farm PvM quer apagar os monstros antes que eles importem; um set de PvP quer continuar de pé no turno dez. Coloque os mesmos itens nos dois e você fica mediano em ambos. O truque não é ter vários sets, é dizer ao otimizador pra que serve <strong>este</strong> set e salvá-lo como um projeto próprio.</p>

<h2>PvM: matar rápido, sobreviver o suficiente</h2>
<p>Contra monstros você costuma conhecer a luta, então dá pra apostar no ataque. Pondere seu elemento e a Potência alto, suba o dano fixo e em %, e mantenha só a vita e resistência que precisa pra limpar a masmorra que você realmente faz. Ninguém lê seu build do outro lado, então sacrificar defesa por dano bruto costuma ser o certo. Trave seus PA, PM e alcance pra sair seu combo, e deixe a ferramenta jogar todo o resto em poder de dano.</p>

<h2>PvP: resistência ganha partidas</h2>
<p>Agora alguém está tentando ativamente estragar seu turno. Resistência fixa e em % sobe pro topo dos seus pesos: aguentar um burst vale mais que um golpe um pouco maior que você talvez erre. Sabedoria também conta: ela reduz os PA e PM que um inimigo pode te tirar, e ficar travado fora do seu kit perde lutas. Mantenha seu elemento de dano, mas equilibre com sobreviver, e valorize alcance e PM pro jogo de posição.</p>

<h2>Os três que você sempre trava</h2>
<p>Não importa o modo, PA, PM e alcance são metas, não controles. Decida os limiares que seus feitiços precisam (digamos 11 PA, 6 PM, 4 de alcance) e trave. O otimizador então gasta cada ponto restante no que muda entre os modos, em vez de desperdiçar equipamento batendo num número de PA que você não pediu.</p>

<h2>Faça na ferramenta</h2>
<p>Faça um projeto por modo. Comece do seu set PvM, duplique, suba resistência e Sabedoria, abaixe um pouco o dano, e refaça o set, você tem uma variante de PvP em menos de um minuto. Depois jogue os dois no <a href="/choose_compare_sets/">comparador</a> pra ver exatamente o que você troca. Esse lado a lado é o jeito mais rápido de entender seu próprio build.</p>

<p><em>Escolha um modo e ajuste: <a href="/setup/">comece um projeto.</a></em></p>
''',
                },
                'de': {
                    'title': "Builds für PvM und PvP",
                    'desc': "Derselbe Charakter braucht je nach Modus ein anderes Build: Dungeons farmen oder gegen andere Spieler kämpfen. So gewichtest du jeden, ohne alles neu zu bauen.",
                    'lead': "Derselbe Charakter braucht je nach dem ein anderes Build, ob du Dungeons farmst oder gegen andere Spieler kämpfst. Gleiche Items, andere Prioritäten: so gewichtest du jeden.",
                    'body': '''
<h2>Warum ein Build nicht reicht</h2>
<p>Deine Ausrüstung ändert sich nicht, aber was du von ihr verlangst, schon. Ein PvM-Farmset will Monster löschen, bevor sie zählen; ein PvP-Set will in Runde zehn noch stehen. Steck dieselben Items in beide und du bist überall mittelmäßig. Der Trick ist nicht, mehrere Sets zu besitzen, sondern dem Optimierer zu sagen, wofür <strong>dieses</strong> Set ist, und es als eigenes Projekt zu speichern.</p>

<h2>PvM: schnell töten, genug überleben</h2>
<p>Gegen Monster kennst du den Kampf meist, also kannst du auf Angriff setzen. Gewichte dein Element und Power hoch, drück fixen und prozentualen Schaden, und behalte nur so viel Vita und Resistenz, wie du für den Dungeon brauchst, den du wirklich läufst. Niemand liest gegenüber dein Build, also ist es oft richtig, Defensive für rohen Schaden zu opfern. Fixier deine AP, BP und Reichweite für dein Combo, und lass das Tool alles andere in Schlagkraft stecken.</p>

<h2>PvP: Resistenz gewinnt Partien</h2>
<p>Jetzt versucht jemand aktiv, dir die Runde zu ruinieren. Fixe und prozentuale Resistenz springen an die Spitze deiner Gewichte: einen Burst zu überleben ist mehr wert als ein etwas größerer Treffer, den du vielleicht nicht landest. Weisheit zählt auch: Sie senkt, wie viel AP und BP ein Gegner dir abziehen kann, und aus dem eigenen Kit gesperrt zu werden, verliert Kämpfe. Behalte dein Schadenselement, aber wäge es gegen Überleben ab, und schätze Reichweite und BP fürs Positionsspiel.</p>

<h2>Die drei, die du immer fixierst</h2>
<p>Egal welcher Modus, AP, BP und Reichweite sind Ziele, keine Regler. Leg die Schwellen fest, die deine Zauber brauchen (sagen wir 11 AP, 6 BP, 4 Reichweite) und fixier sie. Der Optimierer gibt dann jeden übrigen Statpunkt für das aus, was sich zwischen den Modi ändert, statt Ausrüstung zu verschwenden, um eine AP-Zahl zu treffen, die du nie verlangt hast.</p>

<h2>Mach es im Tool</h2>
<p>Leg pro Modus ein Projekt an. Starte von deinem PvM-Set, dupliziere es, zieh Resistenz und Weisheit hoch, etwas Schaden runter, und schneider neu, du hast in unter einer Minute eine PvP-Variante. Wirf dann beide in den <a href="/choose_compare_sets/">Vergleich</a>, um genau zu sehen, was du eintauschst. Dieses Nebeneinander ist der schnellste Weg, dein eigenes Build zu verstehen.</p>

<p><em>Wähl einen Modus und stell ihn ein: <a href="/setup/">starte ein Projekt.</a></em></p>
''',
                },
            },
        },
    },

    # ------------------------------------------------------------------ #
    'reading-an-item': {
        'published': '2026-07-01',
        'i18n': {
            'en': {
                'title': "How to read a Dofus item (without getting fooled)",
                'desc': "Two items with the same headline stat can differ wildly once you read the fine print: rolls, conditions, set bonuses. Learn to size up gear like the tool does.",
                'lead': "Two items with the same headline stat can be wildly different once you read the fine print. Here's how to size up a piece of gear the way the optimizer does.",
                'body': '''
<h2>The stat lines (and their hidden range)</h2>
<p>Every item rolls its stats inside a min-max range. Two copies of the same belt aren't identical: one might be +40 intelligence, another +25. When you browse the <a href="/encyclopedia/">encyclopedia</a>, the numbers you see are the item's potential; the one you actually own depends on its roll. The tool optimizes on the item's stats, so a well-rolled piece is genuinely worth more than a bad one, worth checking before you buy.</p>

<h2>Conditions: why an item won't equip</h2>
<p>Plenty of gear comes with strings attached. Level requirements are obvious; the sneaky ones are stat conditions: "only if AP ≤ 11", a class restriction, or a trophy that won't stack with other set bonuses. These are exactly the rules the optimizer respects so it never hands you an illegal set. If a piece you wanted got skipped, a condition is usually why. (On Dofus Touch, for instance, some trophies cap how many set bonuses you can run at once.)</p>

<h2>Set bonuses: the stats you don't see on the item</h2>
<p>A set (panoply) gives extra stats once you wear two, three, four or more pieces of it. That bonus can be huge: sometimes a mediocre item earns its slot purely because it completes a set. The optimizer accounts for this automatically: it doesn't just add up individual items, it weighs the set bonuses you'd unlock by combining them. That's why it sometimes picks an item that looks weak on its own.</p>

<h2>Exos and overmage, at a glance</h2>
<p>An extra line beyond the item's normal stats (an exo) is a big deal, especially an exo AP or MP. The tool lets you declare whether you'll have exos rather than pinning them to a specific item, because you know best where they're cheap to mage on your server. Just tell it the truth, or it may hand you an AP-conditioned item that breaks once you add that exo.</p>

<h2>Let the tool do the reading</h2>
<p>You don't have to memorize any of this. Browse an item in the <a href="/encyclopedia/">encyclopedia</a> to see its full stat lines, conditions and set, and when you <a href="/setup/">build a set</a>, the solution page lays out every bonus and every condition for you.</p>

<p><em>See it on a real item: <a href="/encyclopedia/">open the encyclopedia.</a></em></p>
''',
            },
            'fr': {
                'title': "Comment lire un item Dofus (sans se faire avoir)",
                'desc': "Deux items avec la même stat en titre peuvent tout changer une fois lues les petites lignes : jets, conditions, bonus de panoplie. Apprends à jauger ton stuff.",
                'lead': "Deux items avec la même stat en titre peuvent être complètement différents une fois les petites lignes lues. Voilà comment jauger un équipement comme le fait l'optimiseur.",
                'body': '''
<h2>Les lignes de stats (et leur fourchette cachée)</h2>
<p>Chaque item tire ses stats dans une fourchette min-max. Deux exemplaires de la même ceinture ne sont pas identiques : l'un peut être +40 intelligence, l'autre +25. Quand tu parcours l'<a href="/encyclopedia/">encyclopédie</a>, les chiffres affichés sont le potentiel de l'item ; celui que tu possèdes dépend de son jet. L'outil optimise sur les stats de l'item, donc une pièce bien jetée vaut vraiment plus qu'une mauvaise, à vérifier avant d'acheter.</p>

<h2>Les conditions : pourquoi un item ne s'équipe pas</h2>
<p>Plein d'équipements ont des contraintes. Les conditions de niveau sont évidentes ; les sournoises sont les conditions de stats : "seulement si PA ≤ 11", une restriction de classe, ou un trophée qui ne s'empile pas avec d'autres bonus de panoplie. Ce sont exactement les règles que l'optimiseur respecte pour ne jamais te filer un set illégal. Si une pièce que tu voulais a été zappée, c'est en général à cause d'une condition. (Sur Dofus Touch, par exemple, certains trophées plafonnent le nombre de bonus de panoplie que tu peux cumuler.)</p>

<h2>Les bonus de panoplie : les stats que tu ne vois pas sur l'item</h2>
<p>Une panoplie donne des stats en plus dès que tu portes deux, trois, quatre pièces ou plus. Ce bonus peut être énorme : parfois un item médiocre mérite sa place juste parce qu'il complète une panoplie. L'optimiseur en tient compte tout seul : il n'additionne pas que les items individuels, il pondère les bonus de panoplie que tu débloquerais en les combinant. C'est pour ça qu'il choisit parfois un item qui a l'air faible tout seul.</p>

<h2>Exos et surmage, en un coup d'œil</h2>
<p>Une ligne en plus des stats normales de l'item (un exo) c'est gros, surtout un exo PA ou PM. L'outil te laisse déclarer si tu auras des exos plutôt que de les coller à un item précis, parce que tu sais mieux où c'est pas cher à maginer sur ton serveur. Dis-lui juste la vérité, sinon il peut te filer un item à condition de PA qui casse dès que tu ajoutes cet exo.</p>

<h2>Laisse l'outil lire à ta place</h2>
<p>T'as pas à mémoriser tout ça. Ouvre un item dans l'<a href="/encyclopedia/">encyclopédie</a> pour voir toutes ses lignes de stats, ses conditions et sa panoplie, et quand tu <a href="/setup/">construis un set</a>, la page de solution te détaille chaque bonus et chaque condition.</p>

<p><em>Vois-le sur un vrai item : <a href="/encyclopedia/">ouvre l'encyclopédie.</a></em></p>
''',
            },
            'es': {
                'title': "Cómo leer un ítem de Dofus (sin que te engañen)",
                'desc': "Dos ítems con la misma estadística en el titular pueden ser muy distintos al leer la letra pequeña: tiradas, condiciones, bonus. Aprende a evaluar tu equipo.",
                'lead': "Dos ítems con la misma estadística en el titular pueden ser totalmente distintos al leer la letra pequeña. Aquí tienes cómo evaluar un equipo como lo hace el optimizador.",
                'body': '''
<h2>Las líneas de estadísticas (y su rango oculto)</h2>
<p>Cada ítem tira sus estadísticas dentro de un rango mín-máx. Dos copias del mismo cinturón no son idénticas: una puede ser +40 inteligencia y otra +25. Cuando navegas por la <a href="/encyclopedia/">enciclopedia</a>, los números que ves son el potencial del ítem; el que tienes depende de su tirada. La herramienta optimiza sobre las estadísticas del ítem, así que una pieza bien tirada vale de verdad más que una mala, conviene mirarlo antes de comprar.</p>

<h2>Las condiciones: por qué un ítem no se equipa</h2>
<p>Mucho equipo viene con condiciones. Las de nivel son obvias; las traicioneras son las de estadística: "solo si PA ≤ 11", una restricción de clase, o un trofeo que no se acumula con otros bonus de panoplia. Son justo las reglas que el optimizador respeta para no darte nunca un set ilegal. Si una pieza que querías quedó descartada, suele ser por una condición. (En Dofus Touch, por ejemplo, algunos trofeos limitan cuántos bonus de panoplia puedes llevar a la vez.)</p>

<h2>Bonus de panoplia: las estadísticas que no ves en el ítem</h2>
<p>Una panoplia da estadísticas extra en cuanto llevas dos, tres, cuatro piezas o más. Ese bonus puede ser enorme: a veces un ítem mediocre se gana su hueco solo porque completa una panoplia. El optimizador lo tiene en cuenta solo: no suma únicamente los ítems individuales, sino que pondera los bonus de panoplia que desbloquearías al combinarlos. Por eso a veces elige un ítem que parece flojo por sí solo.</p>

<h2>Exos y sobreforja, de un vistazo</h2>
<p>Una línea de más sobre las estadísticas normales del ítem (un exo) es importante, sobre todo un exo PA o PM. La herramienta te deja declarar si tendrás exos en vez de fijarlos a un ítem concreto, porque tú sabes mejor dónde es barato forjarlos en tu servidor. Dile la verdad, o puede darte un ítem con condición de PA que se rompe en cuanto añades ese exo.</p>

<h2>Deja que la herramienta lea por ti</h2>
<p>No tienes que memorizar nada de esto. Abre un ítem en la <a href="/encyclopedia/">enciclopedia</a> para ver todas sus líneas de estadísticas, condiciones y panoplia, y cuando <a href="/setup/">montas un set</a>, la página de solución te detalla cada bonus y cada condición.</p>

<p><em>Míralo en un ítem real: <a href="/encyclopedia/">abre la enciclopedia.</a></em></p>
''',
            },
            'pt': {
                'title': "Como ler um item de Dofus (sem cair em pegadinha)",
                'desc': "Dois itens com o mesmo atributo no título podem ser bem diferentes ao ler as letras miúdas: rolagens, condições, bônus. Aprenda a avaliar seu equipamento.",
                'lead': "Dois itens com o mesmo atributo no título podem ser totalmente diferentes depois de ler as letras miúdas. Veja como avaliar um equipamento como o otimizador faz.",
                'body': '''
<h2>As linhas de atributos (e seu intervalo escondido)</h2>
<p>Todo item rola seus atributos dentro de um intervalo mín-máx. Duas cópias do mesmo cinto não são idênticas: uma pode ser +40 inteligência e outra +25. Quando você navega na <a href="/encyclopedia/">enciclopédia</a>, os números que aparecem são o potencial do item; o que você tem depende da rolagem dele. A ferramenta otimiza sobre os atributos do item, então uma peça bem rolada vale mesmo mais que uma ruim, vale conferir antes de comprar.</p>

<h2>Condições: por que um item não equipa</h2>
<p>Muito equipamento vem com amarras. As de nível são óbvias; as traiçoeiras são as de atributo: "só se PA ≤ 11", uma restrição de classe, ou um troféu que não acumula com outros bônus de conjunto. São exatamente as regras que o otimizador respeita pra nunca te dar um set ilegal. Se uma peça que você queria foi pulada, normalmente é por causa de uma condição. (No Dofus Touch, por exemplo, alguns troféus limitam quantos bônus de conjunto você pode usar de uma vez.)</p>

<h2>Bônus de conjunto: os atributos que você não vê no item</h2>
<p>Um conjunto dá atributos extras assim que você usa duas, três, quatro peças ou mais. Esse bônus pode ser enorme: às vezes um item mediano ganha o lugar só porque completa um conjunto. O otimizador considera isso sozinho: ele não soma só os itens individuais, ele pondera os bônus de conjunto que você desbloquearia ao combiná-los. É por isso que ele às vezes escolhe um item que parece fraco sozinho.</p>

<h2>Exos e sobreforja, num relance</h2>
<p>Uma linha além dos atributos normais do item (um exo) é importante, ainda mais um exo PA ou PM. A ferramenta deixa você declarar se vai ter exos em vez de prendê-los a um item específico, porque você sabe melhor onde é barato forjar no seu servidor. Só fale a verdade, ou ela pode te dar um item com condição de PA que quebra assim que você adiciona esse exo.</p>

<h2>Deixe a ferramenta ler por você</h2>
<p>Você não precisa decorar nada disso. Abra um item na <a href="/encyclopedia/">enciclopédia</a> pra ver todas as linhas de atributos, condições e conjunto, e quando você <a href="/setup/">monta um set</a>, a página de solução detalha cada bônus e cada condição.</p>

<p><em>Veja num item real: <a href="/encyclopedia/">abra a enciclopédia.</a></em></p>
''',
            },
            'de': {
                'title': "Wie man ein Dofus-Item liest (ohne reinzufallen)",
                'desc': "Zwei Items mit demselben Wert in der Überschrift können völlig verschieden sein, sobald man das Kleingedruckte liest: Würfe, Bedingungen, Set-Boni.",
                'lead': "Zwei Items mit demselben Wert in der Überschrift können völlig verschieden sein, sobald man das Kleingedruckte liest. So schätzt du ein Ausrüstungsteil ein, wie es der Optimierer tut.",
                'body': '''
<h2>Die Wertzeilen (und ihre versteckte Spanne)</h2>
<p>Jedes Item würfelt seine Werte innerhalb einer Min-Max-Spanne. Zwei Exemplare desselben Gürtels sind nicht identisch: das eine ist vielleicht +40 Intelligenz, das andere +25. Wenn du die <a href="/encyclopedia/">Enzyklopädie</a> durchstöberst, sind die angezeigten Zahlen das Potenzial des Items; das, das du besitzt, hängt von seinem Wurf ab. Das Tool optimiert auf die Werte des Items, also ist ein gut gewürfeltes Teil wirklich mehr wert als ein schlechtes, vor dem Kauf einen Blick wert.</p>

<h2>Bedingungen: warum sich ein Item nicht anlegen lässt</h2>
<p>Viel Ausrüstung hat Auflagen. Levelbedingungen sind offensichtlich; die heimtückischen sind Wertbedingungen: "nur wenn AP ≤ 11", eine Klassenbeschränkung, oder eine Trophäe, die sich nicht mit anderen Set-Boni stapelt. Genau diese Regeln befolgt der Optimierer, damit er dir nie ein illegales Set gibt. Wenn ein Teil, das du wolltest, übersprungen wurde, liegt es meist an einer Bedingung. (Auf Dofus Touch deckeln manche Trophäen zum Beispiel, wie viele Set-Boni du gleichzeitig fahren kannst.)</p>

<h2>Set-Boni: die Werte, die du nicht am Item siehst</h2>
<p>Eine Set (Panoplie) gibt zusätzliche Werte, sobald du zwei, drei, vier oder mehr Teile davon trägst. Dieser Bonus kann riesig sein: manchmal verdient sich ein mittelmäßiges Item seinen Platz nur, weil es ein Set vervollständigt. Der Optimierer berücksichtigt das automatisch: Er addiert nicht nur einzelne Items, sondern gewichtet die Set-Boni, die du durchs Kombinieren freischalten würdest. Deshalb wählt er manchmal ein Item, das für sich allein schwach aussieht.</p>

<h2>Exos und Übermagie, auf einen Blick</h2>
<p>Eine zusätzliche Zeile über den normalen Werten des Items (ein Exo) ist eine große Sache, besonders ein Exo-AP oder -BP. Das Tool lässt dich angeben, ob du Exos haben wirst, statt sie an ein bestimmtes Item zu binden, weil du am besten weißt, wo sie auf deinem Server billig zu magen sind. Sag ihm einfach die Wahrheit, sonst gibt es dir vielleicht ein AP-bedingtes Item, das kaputtgeht, sobald du dieses Exo hinzufügst.</p>

<h2>Lass das Tool lesen</h2>
<p>Du musst dir nichts davon merken. Öffne ein Item in der <a href="/encyclopedia/">Enzyklopädie</a>, um alle Wertzeilen, Bedingungen und das Set zu sehen, und wenn du <a href="/setup/">ein Set baust</a>, legt dir die Lösungsseite jeden Bonus und jede Bedingung offen.</p>

<p><em>Sieh es an einem echten Item: <a href="/encyclopedia/">öffne die Enzyklopädie.</a></em></p>
''',
            },
        },
    },

    # ------------------------------------------------------------------ #
    'mono-vs-multi-element': {
        'published': '2026-07-01',
        'i18n': {
            'en': {
                'title': "Mono-element or multi-element? Pick one and hit harder",
                'desc': "Spreading damage across two elements feels safe, but usually hits softer than committing to one. Why mono almost always wins, and the few times it doesn't.",
                'lead': "Spreading your damage across two elements feels safe, but it usually hits softer than committing to one. Here's why focusing pays off, and when it doesn't.",
                'body': '''
<h2>Why one element usually wins</h2>
<p>Your damage scales with the element you commit to: the characteristic behind it (Strength for earth, Intelligence for fire, Agility for air, Chance for water) and the gear that pushes that element. Split your gear across two elements and every point only helps half your hits; pour it all into one and every point counts every time. Concentration compounds: a focused mono-element set almost always out-damages a smeared two-element one of the same level.</p>

<h2>It's really just your sliders</h2>
<p>In the tool, mono-vs-multi isn't a separate setting: it's how you weight your elements. Crank one element and its characteristic, leave the others low, and the optimizer builds you a focused hitter. Weight two elements equally and it'll happily split your gear between them. So if your build came out spread when you wanted focused, your weights are the place to look.</p>

<h2>When multi-element is actually right</h2>
<p>It's not always wrong. A few cases genuinely want two elements:</p>
<ul>
<li>Spells that hit in two elements, or a kit that mixes them, your damage really does scale on both.</li>
<li>A set bonus or a key item that pushes a second element for free, so taking it costs you nothing.</li>
<li>Utility over raw damage: a secondary element for a specific spell's effect rather than its hit.</li>
</ul>
<p>Outside those, splitting is usually just leaving damage on the table.</p>

<h2>Pick the element your spells love</h2>
<p>Choose the element your main damage spells scale on (check them on the spells page if you're not sure) and weight that one and its characteristic high. Let the optimizer do the rest. One clean element beats two half-hearted ones nearly every time.</p>

<p><em>Try both and compare: <a href="/setup/">build a set</a> and see the damage for yourself.</em></p>
''',
            },
            'fr': {
                'title': "Mono ou multi-élément ? Choisis-en un et tape plus fort",
                'desc': "Répartir tes dégâts sur deux éléments rassure, mais tape moins fort que tout miser sur un. Pourquoi le mono gagne presque toujours, et les rares exceptions.",
                'lead': "Répartir tes dégâts sur deux éléments rassure, mais ça tape souvent moins fort que de tout miser sur un seul. Voilà pourquoi se concentrer paie, et quand ça ne paie pas.",
                'body': '''
<h2>Pourquoi un seul élément gagne d'habitude</h2>
<p>Tes dégâts scalent avec l'élément que tu choisis : la caractéristique derrière (Force pour la terre, Intelligence pour le feu, Agilité pour l'air, Chance pour l'eau) et le stuff qui pousse cet élément. Répartis ton stuff sur deux éléments et chaque point n'aide que la moitié de tes coups ; mets tout sur un seul et chaque point compte à chaque fois. La concentration se cumule : un set mono-élément concentré tape presque toujours plus fort qu'un set bi-élément dilué du même niveau.</p>

<h2>En vrai, c'est juste tes curseurs</h2>
<p>Dans l'outil, le mono-vs-multi n'est pas un réglage à part : c'est la façon dont tu pondères tes éléments. Monte un élément et sa caractéristique, laisse les autres bas, et l'optimiseur te construit un frappeur concentré. Pondère deux éléments à égalité et il répartira ton stuff entre les deux sans souci. Donc si ton build est sorti dilué alors que tu le voulais concentré, c'est tes poids qu'il faut regarder.</p>

<h2>Quand le multi-élément a vraiment du sens</h2>
<p>C'est pas toujours un tort. Quelques cas veulent vraiment deux éléments :</p>
<ul>
<li>Des sorts qui tapent en deux éléments, ou un kit qui les mélange, tes dégâts scalent vraiment sur les deux.</li>
<li>Un bonus de panoplie ou un item clé qui pousse un second élément gratuitement, donc le prendre ne te coûte rien.</li>
<li>L'utilité plutôt que le dégât brut : un second élément pour l'effet d'un sort précis, pas pour son coup.</li>
</ul>
<p>En dehors de ça, répartir, c'est en général laisser du dégât sur la table.</p>

<h2>Choisis l'élément que tes sorts préfèrent</h2>
<p>Prends l'élément sur lequel scalent tes sorts de dégâts principaux (vérifie-les sur la page des sorts si tu hésites) et pondère celui-là et sa caractéristique haut. Laisse l'optimiseur faire le reste. Un élément propre bat deux éléments à moitié presque à chaque fois.</p>

<p><em>Teste les deux et compare : <a href="/setup/">construis un set</a> et regarde les dégâts toi-même.</em></p>
''',
            },
            'es': {
                'title': "¿Monoelemento o multielemento? Elige uno y pega más fuerte",
                'desc': "Repartir tu daño en dos elementos da seguridad, pero pega más flojo que apostar por uno. Por qué el mono casi siempre gana, y las pocas veces que no.",
                'lead': "Repartir tu daño entre dos elementos da sensación de seguridad, pero suele pegar más flojo que apostar por uno solo. Aquí tienes por qué concentrarse compensa, y cuándo no.",
                'body': '''
<h2>Por qué un solo elemento suele ganar</h2>
<p>Tu daño escala con el elemento que eliges: la característica detrás (Fuerza para tierra, Inteligencia para fuego, Agilidad para aire, Suerte para agua) y el equipo que empuja ese elemento. Reparte tu equipo entre dos elementos y cada punto solo ayuda a la mitad de tus golpes; mételo todo en uno y cada punto cuenta siempre. La concentración se acumula: un set monoelemento concentrado casi siempre pega más que uno bielemento diluido del mismo nivel.</p>

<h2>En realidad son tus deslizadores</h2>
<p>En la herramienta, mono-vs-multi no es un ajuste aparte: es cómo ponderas tus elementos. Sube un elemento y su característica, deja los demás bajos, y el optimizador te monta un pegador concentrado. Pondera dos elementos por igual y repartirá tu equipo entre ambos sin problema. Así que si tu build salió repartido cuando lo querías concentrado, mira tus pesos.</p>

<h2>Cuándo el multielemento sí tiene sentido</h2>
<p>No siempre está mal. Algunos casos quieren de verdad dos elementos:</p>
<ul>
<li>Hechizos que pegan en dos elementos, o un kit que los mezcla, tu daño escala de verdad en ambos.</li>
<li>Un bonus de panoplia o un ítem clave que empuja un segundo elemento gratis, así que cogerlo no te cuesta nada.</li>
<li>Utilidad antes que daño bruto: un segundo elemento por el efecto de un hechizo concreto, no por su golpe.</li>
</ul>
<p>Fuera de eso, repartir suele ser dejar daño sin aprovechar.</p>

<h2>Elige el elemento que aman tus hechizos</h2>
<p>Coge el elemento con el que escalan tus hechizos de daño principales (míralos en la página de hechizos si dudas) y pondera ese y su característica alto. Deja que el optimizador haga el resto. Un elemento limpio gana a dos a medias casi siempre.</p>

<p><em>Prueba ambos y compara: <a href="/setup/">monta un set</a> y mira el daño tú mismo.</em></p>
''',
            },
            'pt': {
                'title': "Mono ou multi-elemento? Escolha um e bata mais forte",
                'desc': "Espalhar seu dano em dois elementos passa segurança, mas costuma bater mais fraco que apostar em um só. Por que o mono quase sempre ganha, e as exceções.",
                'lead': "Espalhar seu dano em dois elementos passa segurança, mas costuma bater mais fraco do que apostar em um só. Veja por que se concentrar compensa, e quando não.",
                'body': '''
<h2>Por que um só elemento costuma ganhar</h2>
<p>Seu dano escala com o elemento que você escolhe: a característica por trás (Força para terra, Inteligência para fogo, Agilidade para ar, Sorte para água) e o equipamento que empurra esse elemento. Espalhe seu equipamento entre dois elementos e cada ponto só ajuda metade dos seus golpes; jogue tudo em um e cada ponto conta sempre. A concentração acumula: um set mono-elemento concentrado quase sempre bate mais que um bi-elemento diluído do mesmo nível.</p>

<h2>Na real, são seus controles</h2>
<p>Na ferramenta, mono-vs-multi não é um ajuste à parte: é como você pondera seus elementos. Suba um elemento e sua característica, deixe os outros baixos, e o otimizador monta um batedor concentrado. Pondere dois elementos igual e ele espalha seu equipamento entre os dois numa boa. Então se seu build saiu espalhado quando você queria concentrado, olhe seus pesos.</p>

<h2>Quando o multi-elemento faz sentido mesmo</h2>
<p>Nem sempre é errado. Alguns casos querem de verdade dois elementos:</p>
<ul>
<li>Feitiços que batem em dois elementos, ou um kit que os mistura, seu dano escala de verdade nos dois.</li>
<li>Um bônus de conjunto ou um item-chave que empurra um segundo elemento de graça, então pegar não te custa nada.</li>
<li>Utilidade em vez de dano bruto: um segundo elemento pelo efeito de um feitiço específico, não pelo golpe.</li>
</ul>
<p>Fora isso, espalhar costuma ser deixar dano na mesa.</p>

<h2>Escolha o elemento que seus feitiços amam</h2>
<p>Pegue o elemento com que seus feitiços de dano principais escalam (confira na página de feitiços se tiver dúvida) e pondere ele e sua característica alto. Deixe o otimizador fazer o resto. Um elemento limpo ganha de dois pela metade quase sempre.</p>

<p><em>Teste os dois e compare: <a href="/setup/">monte um set</a> e veja o dano você mesmo.</em></p>
''',
            },
            'de': {
                'title': "Mono oder Multi-Element? Nimm eins und hau härter zu",
                'desc': "Den Schaden auf zwei Elemente zu verteilen fühlt sich sicher an, haut aber weicher zu als eins zu wählen. Warum Mono fast immer gewinnt, und die Ausnahmen.",
                'lead': "Den Schaden auf zwei Elemente zu verteilen fühlt sich sicher an, haut aber meist weicher zu als sich auf eins festzulegen. Hier ist, warum Fokus sich lohnt, und wann nicht.",
                'body': '''
<h2>Warum ein Element meist gewinnt</h2>
<p>Dein Schaden skaliert mit dem Element, auf das du dich festlegst: dem Wert dahinter (Stärke für Erde, Intelligenz für Feuer, Flinkheit für Luft, Glück für Wasser) und der Ausrüstung, die dieses Element pusht. Verteil deine Ausrüstung auf zwei Elemente, und jeder Punkt hilft nur der Hälfte deiner Treffer; steck alles in eins, und jeder Punkt zählt jedes Mal. Fokus summiert sich: Ein konzentriertes Mono-Element-Set macht fast immer mehr Schaden als ein verwässertes Zwei-Element-Set desselben Levels.</p>

<h2>Es sind eigentlich nur deine Regler</h2>
<p>Im Tool ist Mono-vs-Multi keine eigene Einstellung: es ist, wie du deine Elemente gewichtest. Dreh ein Element und seinen Wert hoch, lass die anderen niedrig, und der Optimierer baut dir einen fokussierten Schläger. Gewichte zwei Elemente gleich, und er verteilt deine Ausrüstung gern auf beide. Wenn dein Build also verstreut rauskam, obwohl du Fokus wolltest, schau bei deinen Gewichten.</p>

<h2>Wann Multi-Element wirklich richtig ist</h2>
<p>Es ist nicht immer falsch. Ein paar Fälle wollen echt zwei Elemente:</p>
<ul>
<li>Zauber, die in zwei Elementen treffen, oder ein Kit, das sie mischt, dein Schaden skaliert wirklich auf beiden.</li>
<li>Ein Set-Bonus oder ein Schlüssel-Item, das ein zweites Element gratis mitbringt, sodass es dich nichts kostet.</li>
<li>Nutzen statt rohem Schaden: ein zweites Element für den Effekt eines bestimmten Zaubers, nicht für seinen Treffer.</li>
</ul>
<p>Außerhalb davon lässt Verteilen meist Schaden liegen.</p>

<h2>Wähl das Element, das deine Zauber lieben</h2>
<p>Nimm das Element, auf dem deine Hauptschadenszauber skalieren (schau sie auf der Zauberseite an, wenn du unsicher bist) und gewichte dieses und seinen Wert hoch. Den Rest macht der Optimierer. Ein sauberes Element schlägt zwei halbe fast jedes Mal.</p>

<p><em>Probier beide und vergleiche: <a href="/setup/">bau ein Set</a> und sieh dir den Schaden selbst an.</em></p>
''',
            },
        },
    },

    # ------------------------------------------------------------------ #
    'gearing-up': {
        'published': '2026-07-01',
        'i18n': {
            'en': {
                'title': "You've got the build: now how do you get the gear?",
                'desc': "The optimizer hands you a perfect set, then reality hits: you own none of it. How to get each item (drop, craft, or buy) and where to start.",
                'lead': "The optimizer hands you a perfect set, then reality hits: you don't own a single piece. Here's how to actually get the gear, without going broke.",
                'body': '''
<h2>Three ways to get any item</h2>
<p>Every piece in your build comes from one of three places: a monster drops it, someone crafts it, or you buy it off the market. Most items can be gotten more than one way, and the cheapest route changes from server to server. The trick is knowing which fight to run, which profession to level, or when to just pay up.</p>

<h2>Dropping it yourself</h2>
<p>Many pieces drop from a specific monster or dungeon boss; the in-game encyclopedia lists exactly where. Farming the drop is "free" but costs time, and drop rates can be brutal, so weight your Prospecting if you're going to grind. Dungeon runs in a group are usually the fastest way to chase a boss-locked piece.</p>

<h2>Crafting it</h2>
<p>Many sets are crafted, not dropped. The recipe lists the resources and the profession level you need; the Fashionista shows the recipe right on the item. Crafting is often cheaper than buying the finished item (you pay in resources and a maged exo or two instead of the full market price) but it means leveling the right profession or finding a guildmate who has.</p>

<h2>Just buying it</h2>
<p>Sometimes your time is worth more than the kamas. The market is the fast lane: search the item, compare prices, and buy. Prices swing with supply, so a piece that's overpriced today might be cheap next week. If a build piece is bleeding your purse, forbid it in the tool and re-run: the next-best item is often a fraction of the cost for almost the same result.</p>

<h2>Prioritize, don't bankrupt yourself</h2>
<p>You don't need the full set on day one. Slot in the cheap pieces first, lock the ones you own, and let the optimizer fill the rest with what you can afford right now. Upgrade piece by piece as your kamas grow. A "good enough" set you actually wear beats a perfect one you can't afford.</p>

<p><em>See an item's stats and recipe: <a href="/encyclopedia/">browse the encyclopedia.</a></em></p>
''',
            },
            'fr': {
                'title': "T'as le build : maintenant, comment choper le stuff ?",
                'desc': "L'optimiseur te sort un set parfait, puis la réalité te rattrape : t'as pas une pièce. Comment obtenir chaque item (drop, craft ou achat) et par où commencer.",
                'lead': "L'optimiseur te sort un set parfait, puis la réalité te rattrape : t'as pas une seule pièce. Voilà comment choper le stuff pour de vrai, sans te ruiner.",
                'body': '''
<h2>Trois façons d'avoir n'importe quel item</h2>
<p>Chaque pièce de ton build vient d'un de ces trois endroits : un monstre la drop, quelqu'un la craft, ou tu l'achètes au marché. La plupart des items s'obtiennent de plusieurs façons, et la route la moins chère change d'un serveur à l'autre. L'astuce, c'est de savoir quel combat lancer, quel métier monter, ou quand juste sortir les kamas.</p>

<h2>La dropper toi-même</h2>
<p>Beaucoup de pièces droppent d'un monstre précis ou d'un boss de donjon ; l'encyclopédie en jeu indique exactement où. Farmer le drop est "gratuit" mais coûte du temps, et les taux de drop peuvent être violents, donc pondère ta Prospection si tu comptes grind. Les donjons en groupe sont souvent le plus rapide pour une pièce bloquée derrière un boss.</p>

<h2>La crafter</h2>
<p>Beaucoup de panoplies se craftent plutôt qu'elles ne droppent. La recette liste les ressources et le niveau de métier requis ; la Fashionista t'affiche la recette directement sur l'item. Crafter revient souvent moins cher qu'acheter l'item fini (tu paies en ressources et un exo ou deux à maginer au lieu du prix plein du marché) mais ça implique de monter le bon métier ou de trouver un membre de guilde qui l'a.</p>

<h2>Juste l'acheter</h2>
<p>Parfois ton temps vaut plus que les kamas. Le marché (HDV) c'est la voie rapide : tu cherches l'item, tu compares les prix, tu achètes. Les prix bougent avec l'offre, donc une pièce hors de prix aujourd'hui peut être bradée la semaine prochaine. Si une pièce du build saigne ta bourse, interdis-la dans l'outil et relance : l'item suivant coûte souvent une fraction du prix pour presque le même résultat.</p>

<h2>Priorise, ne te ruine pas</h2>
<p>T'as pas besoin de la panoplie complète dès le premier jour. Mets les pièces pas chères d'abord, verrouille celles que t'as, et laisse l'optimiseur remplir le reste avec ce que tu peux te payer maintenant. Améliore pièce par pièce au fur et à mesure que tes kamas montent. Un set "suffisant" que tu portes vraiment bat un set parfait que tu peux pas t'offrir.</p>

<p><em>Vois les stats et la recette d'un item : <a href="/encyclopedia/">parcours l'encyclopédie.</a></em></p>
''',
            },
            'es': {
                'title': "Ya tienes el build: ¿y ahora cómo consigues el equipo?",
                'desc': "El optimizador te da un set perfecto, y llega la realidad: no tienes ni una pieza. Cómo conseguir cada ítem (dropear, fabricar o comprar) y por dónde empezar.",
                'lead': "El optimizador te da un set perfecto, y entonces llega la realidad: no tienes ni una pieza. Aquí tienes cómo conseguir el equipo de verdad, sin arruinarte.",
                'body': '''
<h2>Tres formas de conseguir cualquier ítem</h2>
<p>Cada pieza de tu build viene de uno de tres sitios: la dropea un monstruo, alguien la fabrica, o la compras en el mercado. La mayoría de los ítems se consiguen de varias formas, y la ruta más barata cambia de un servidor a otro. El truco es saber qué pelea hacer, qué profesión subir, o cuándo simplemente pagar.</p>

<h2>Dropearla tú mismo</h2>
<p>Muchas piezas dropean de un monstruo concreto o un jefe de mazmorra; la enciclopedia del juego indica exactamente dónde. Farmear el drop es "gratis" pero cuesta tiempo, y las tasas de drop pueden ser brutales, así que pondera tu Prospección si vas a grindear. Las mazmorras en grupo suelen ser lo más rápido para una pieza bloqueada tras un jefe.</p>

<h2>Fabricarla</h2>
<p>Muchas panoplias se fabrican en vez de dropearse. La receta lista los recursos y el nivel de profesión que necesitas; la Fashionista te muestra la receta en el propio ítem. Fabricar suele salir más barato que comprar el ítem terminado (pagas en recursos y un exo o dos forjados en vez del precio completo del mercado) pero implica subir la profesión adecuada o encontrar a alguien del gremio que la tenga.</p>

<h2>Simplemente comprarla</h2>
<p>A veces tu tiempo vale más que los kamas. El mercado (HDV) es la vía rápida: busca el ítem, compara precios y compra. Los precios oscilan con la oferta, así que una pieza carísima hoy puede estar barata la semana que viene. Si una pieza del build te desangra la bolsa, prohíbela en la herramienta y vuelve a lanzar: el siguiente ítem suele costar una fracción por casi el mismo resultado.</p>

<h2>Prioriza, no te arruines</h2>
<p>No necesitas el set completo el primer día. Mete las piezas baratas primero, bloquea las que tengas, y deja que el optimizador rellene el resto con lo que te puedas permitir ahora. Mejora pieza a pieza según suban tus kamas. Un set "suficiente" que de verdad llevas gana a uno perfecto que no puedes pagar.</p>

<p><em>Mira las estadísticas y la receta de un ítem: <a href="/encyclopedia/">explora la enciclopedia.</a></em></p>
''',
            },
            'pt': {
                'title': "Você tem o build: e agora, como conseguir o equipamento?",
                'desc': "O otimizador te dá um set perfeito, e aí bate a realidade: você não tem uma peça. Como conseguir cada item (dropar, fabricar ou comprar) e por onde começar.",
                'lead': "O otimizador te dá um set perfeito, e aí bate a realidade: você não tem uma peça sequer. Veja como conseguir o equipamento de verdade, sem quebrar.",
                'body': '''
<h2>Três jeitos de conseguir qualquer item</h2>
<p>Cada peça do seu build vem de um de três lugares: um monstro dropa, alguém fabrica, ou você compra no mercado. A maioria dos itens dá pra conseguir de mais de um jeito, e a rota mais barata muda de servidor pra servidor. O truque é saber qual luta fazer, qual profissão subir, ou quando simplesmente pagar.</p>

<h2>Dropar você mesmo</h2>
<p>Muitas peças dropam de um monstro específico ou de um chefe de masmorra; a enciclopédia do jogo mostra exatamente onde. Farmar o drop é "de graça" mas custa tempo, e as taxas de drop podem ser brutais, então pondere sua Prospecção se for grindar. Masmorras em grupo costumam ser o mais rápido pra uma peça travada atrás de um chefe.</p>

<h2>Fabricar</h2>
<p>Muitos conjuntos são fabricados em vez de dropados. A receita lista os recursos e o nível de profissão necessários; a Fashionista mostra a receita no próprio item. Fabricar costuma sair mais barato que comprar o item pronto (você paga em recursos e um exo ou dois forjados em vez do preço cheio do mercado) mas implica subir a profissão certa ou achar alguém da guilda que tenha.</p>

<h2>Só comprar</h2>
<p>Às vezes seu tempo vale mais que os kamas. O mercado (HDV) é a via rápida: procura o item, compara preços e compra. Os preços oscilam com a oferta, então uma peça caríssima hoje pode estar barata semana que vem. Se uma peça do build está sangrando sua bolsa, proíba ela na ferramenta e rode de novo: o próximo item costuma custar uma fração pelo quase mesmo resultado.</p>

<h2>Priorize, não quebre</h2>
<p>Você não precisa do set completo no primeiro dia. Coloque as peças baratas primeiro, trave as que você tem, e deixe o otimizador preencher o resto com o que dá pra pagar agora. Melhore peça por peça conforme seus kamas sobem. Um set "bom o bastante" que você realmente usa ganha de um perfeito que você não pode pagar.</p>

<p><em>Veja as estatísticas e a receita de um item: <a href="/encyclopedia/">explore a enciclopédia.</a></em></p>
''',
            },
            'de': {
                'title': "Du hast das Build: aber wie kommst du an die Ausrüstung?",
                'desc': "Der Optimierer gibt dir ein perfektes Set, dann die Realität: Du besitzt kein Teil. So bekommst du jedes Item (droppen, herstellen, kaufen) und wo du anfängst.",
                'lead': "Der Optimierer gibt dir ein perfektes Set, dann kommt die Realität: Du besitzt kein einziges Teil. So kommst du wirklich an die Ausrüstung, ohne pleitezugehen.",
                'body': '''
<h2>Drei Wege zu jedem Item</h2>
<p>Jedes Teil deines Builds kommt aus einer von drei Quellen: ein Monster droppt es, jemand stellt es her, oder du kaufst es auf dem Markt. Die meisten Items bekommst du auf mehr als einem Weg, und die günstigste Route ändert sich von Server zu Server. Der Trick ist zu wissen, welchen Kampf du läufst, welchen Beruf du levelst, oder wann du einfach zahlst.</p>

<h2>Selbst droppen</h2>
<p>Viele Teile droppen von einem bestimmten Monster oder einem Dungeon-Boss; die Ingame-Enzyklopädie zeigt genau, wo. Den Drop zu farmen ist "gratis", kostet aber Zeit, und die Drop-Raten können brutal sein, also gewichte deine Prospektion, wenn du grinden willst. Dungeon-Läufe in der Gruppe sind meist am schnellsten für ein Teil, das hinter einem Boss steckt.</p>

<h2>Herstellen</h2>
<p>Viele Sets werden hergestellt statt gedroppt. Das Rezept listet die Ressourcen und das nötige Berufslevel; die Fashionista zeigt dir das Rezept direkt am Item. Herstellen ist oft günstiger als das fertige Item zu kaufen (du zahlst in Ressourcen und ein, zwei gemagten Exos statt dem vollen Marktpreis) aber es heißt, den richtigen Beruf zu leveln oder ein Gildenmitglied zu finden, das ihn hat.</p>

<h2>Einfach kaufen</h2>
<p>Manchmal ist deine Zeit mehr wert als die Kamas. Der Markt ist die Überholspur: Item suchen, Preise vergleichen, kaufen. Preise schwanken mit dem Angebot, also ist ein heute überteuertes Teil nächste Woche vielleicht billig. Wenn ein Build-Teil deinen Geldbeutel ausblutet, verbiete es im Tool und rechne neu: das nächstbeste Item kostet oft einen Bruchteil bei fast gleichem Ergebnis.</p>

<h2>Priorisiere, ruiniere dich nicht</h2>
<p>Du brauchst nicht das komplette Set am ersten Tag. Steck zuerst die günstigen Teile rein, sperr die, die du hast, und lass den Optimierer den Rest mit dem füllen, was du dir gerade leisten kannst. Rüste Teil für Teil auf, während deine Kamas wachsen. Ein "gut genug"-Set, das du wirklich trägst, schlägt ein perfektes, das du dir nicht leisten kannst.</p>

<p><em>Sieh dir Werte und Rezept eines Items an: <a href="/encyclopedia/">durchstöbere die Enzyklopädie.</a></em></p>
''',
            },
        },
    },

    # ------------------------------------------------------------------ #
    'comparing-builds': {
        'published': '2026-07-01',
        'i18n': {
            'en': {
                'title': "Comparing builds side by side: which set is better?",
                'desc': "You've got two sets and aren't sure which to wear. Throw them into the comparison and the Fashionista shows exactly what you gain and lose, stat by stat.",
                'lead': "You've got two sets and you're not sure which one to wear. Instead of squinting at two tabs, put them side by side and let the numbers decide.",
                'body': '''
<h2>Why compare at all</h2>
<p>Two builds can look similar and play completely differently. One has 200 more vitality; the other hits 8% harder. Eyeballing that across a dozen slots is hopeless. The comparison lines both sets up column by column so the trade-offs jump out: no spreadsheet, no guesswork.</p>

<h2>How to set it up</h2>
<p>On any solution page (yours or a shared build), hit <strong>Add to comparison</strong>. Do it on a second build (or a third, or a fourth) and open the <a href="/choose_compare_sets/">comparison</a>. You can also paste build share links straight in. Your cart sticks around as you browse, so you can collect candidates and compare them all at once.</p>

<h2>Reading the result</h2>
<p>Each build gets a column; with exactly two, you also get a <em>diff</em> column that spells out the gap on every stat. Items shared between sets line up, so you instantly see which pieces actually differ and which carry over. That's usually where the real decision lives, not in the totals, but in the two or three slots that aren't the same.</p>

<h2>What to compare</h2>
<p>The obvious use is "my current set vs. the optimizer's suggestion." But it's just as good for "PvM vs. PvP variant," "cheap vs. expensive version," or settling a guild argument by dropping two shared builds in together. Anytime you're torn between two directions, compare them instead of debating them.</p>

<p><em>Got two builds in mind? <a href="/choose_compare_sets/">Compare them now.</a></em></p>
''',
            },
            'fr': {
                'title': "Comparer deux builds côte à côte : lequel est meilleur ?",
                'desc': "T'as deux sets et tu sais pas lequel porter. Balance-les dans le comparateur : la Fashionista te montre exactement ce que tu gagnes et perds, stat par stat.",
                'lead': "T'as deux sets et tu sais pas lequel porter. Plutôt que de loucher sur deux onglets, mets-les côte à côte et laisse les chiffres trancher.",
                'body': '''
<h2>Pourquoi comparer</h2>
<p>Deux builds peuvent sembler proches et jouer complètement différemment. L'un a 200 vita de plus ; l'autre tape 8% plus fort. Juger ça à l'œil sur douze emplacements, c'est mission impossible. Le comparateur aligne les deux sets colonne par colonne pour que les compromis sautent aux yeux : pas de tableur, pas de devinette.</p>

<h2>Comment le lancer</h2>
<p>Sur n'importe quelle page de solution (la tienne ou un build partagé), clique sur <strong>Ajouter à la comparaison</strong>. Fais-le sur un deuxième build (ou un troisième, ou un quatrième) et ouvre le <a href="/choose_compare_sets/">comparateur</a>. Tu peux aussi coller directement des liens de partage. Ton panier reste en place pendant que tu navigues, donc tu collectes des candidats et tu compares tout d'un coup.</p>

<h2>Lire le résultat</h2>
<p>Chaque build a sa colonne ; avec exactement deux, t'as en plus une colonne <em>diff</em> qui détaille l'écart sur chaque stat. Les items communs aux deux sets s'alignent, donc tu vois direct quelles pièces diffèrent vraiment et lesquelles reviennent. C'est en général là que se joue la vraie décision, pas dans les totaux, mais dans les deux-trois emplacements qui ne sont pas les mêmes.</p>

<h2>Quoi comparer</h2>
<p>L'usage évident, c'est "mon set actuel vs la propo de l'optimiseur". Mais c'est aussi parfait pour "variante PvM vs PvP", "version cheap vs chère", ou clore un débat de guilde en mettant deux builds partagés ensemble. Dès que t'hésites entre deux directions, compare-les au lieu d'en débattre.</p>

<p><em>Deux builds en tête ? <a href="/choose_compare_sets/">Compare-les maintenant.</a></em></p>
''',
            },
            'es': {
                'title': "Comparar builds lado a lado: ¿cuál set es mejor?",
                'desc': "Tienes dos sets y no sabes cuál llevar. Mételos en el comparador y la Fashionista te muestra exactamente qué ganas y qué pierdes, estadística por estadística.",
                'lead': "Tienes dos sets y no sabes cuál llevar. En vez de bizquear entre dos pestañas, ponlos lado a lado y deja que los números decidan.",
                'body': '''
<h2>Por qué comparar</h2>
<p>Dos builds pueden parecer iguales y jugarse completamente distinto. Uno tiene 200 de vitalidad más; el otro pega un 8% más fuerte. Juzgar eso a ojo en una docena de ranuras es imposible. El comparador alinea los dos sets columna por columna para que los compromisos salten a la vista: sin hoja de cálculo, sin adivinar.</p>

<h2>Cómo montarlo</h2>
<p>En cualquier página de solución (la tuya o un build compartido), dale a <strong>Añadir a la comparación</strong>. Hazlo en un segundo build (o un tercero, o un cuarto) y abre el <a href="/choose_compare_sets/">comparador</a>. También puedes pegar enlaces de builds compartidos directamente. Tu carrito se queda mientras navegas, así que reúnes candidatos y los comparas todos de golpe.</p>

<h2>Leer el resultado</h2>
<p>Cada build tiene su columna; con exactamente dos, tienes además una columna <em>diff</em> que detalla la diferencia en cada estadística. Los ítems compartidos entre sets se alinean, así que ves al instante qué piezas difieren de verdad y cuáles se repiten. Ahí suele estar la decisión real, no en los totales, sino en las dos o tres ranuras que no son iguales.</p>

<h2>Qué comparar</h2>
<p>El uso obvio es "mi set actual vs. la sugerencia del optimizador". Pero va igual de bien para "variante PvM vs. PvP", "versión barata vs. cara", o zanjar una discusión de gremio metiendo dos builds compartidos juntos. Cuando dudes entre dos direcciones, compáralas en vez de debatirlas.</p>

<p><em>¿Dos builds en mente? <a href="/choose_compare_sets/">Compáralos ahora.</a></em></p>
''',
            },
            'pt': {
                'title': "Comparar builds lado a lado: qual set é melhor?",
                'desc': "Você tem dois sets e não sabe qual usar. Jogue os dois no comparador e a Fashionista mostra exatamente o que você ganha e perde, atributo por atributo.",
                'lead': "Você tem dois sets e não sabe qual usar. Em vez de apertar os olhos entre duas abas, coloque-os lado a lado e deixe os números decidirem.",
                'body': '''
<h2>Por que comparar</h2>
<p>Dois builds podem parecer iguais e jogar de um jeito completamente diferente. Um tem 200 de vitalidade a mais; o outro bate 8% mais forte. Julgar isso no olho em uma dúzia de slots é impossível. O comparador alinha os dois sets coluna por coluna pra que os trade-offs saltem aos olhos: sem planilha, sem adivinhação.</p>

<h2>Como montar</h2>
<p>Em qualquer página de solução (a sua ou um build compartilhado), clique em <strong>Adicionar à comparação</strong>. Faça isso num segundo build (ou num terceiro, ou quarto) e abra o <a href="/choose_compare_sets/">comparador</a>. Você também pode colar links de builds compartilhados direto. Seu carrinho fica enquanto você navega, então você junta candidatos e compara todos de uma vez.</p>

<h2>Ler o resultado</h2>
<p>Cada build ganha uma coluna; com exatamente dois, você ainda ganha uma coluna <em>diff</em> que detalha a diferença em cada atributo. Os itens compartilhados entre os sets se alinham, então você vê na hora quais peças realmente diferem e quais se repetem. Geralmente é aí que mora a decisão de verdade, não nos totais, mas nos dois ou três slots que não são iguais.</p>

<h2>O que comparar</h2>
<p>O uso óbvio é "meu set atual vs. a sugestão do otimizador". Mas serve igual pra "variante PvM vs. PvP", "versão barata vs. cara", ou encerrar uma discussão de guilda colocando dois builds compartilhados juntos. Sempre que estiver dividido entre duas direções, compare em vez de debater.</p>

<p><em>Dois builds em mente? <a href="/choose_compare_sets/">Compare agora.</a></em></p>
''',
            },
            'de': {
                'title': "Builds nebeneinander vergleichen: welches Set ist besser?",
                'desc': "Du hast zwei Sets und weißt nicht, welches du trägst. Wirf sie in den Vergleich: die Fashionista zeigt genau, was du gewinnst und verlierst, Wert für Wert.",
                'lead': "Du hast zwei Sets und weißt nicht, welches du tragen sollst. Statt zwischen zwei Tabs zu schielen, stell sie nebeneinander und lass die Zahlen entscheiden.",
                'body': '''
<h2>Warum überhaupt vergleichen</h2>
<p>Zwei Builds können ähnlich aussehen und sich völlig anders spielen. Eins hat 200 Vitalität mehr; das andere haut 8% härter zu. Das über ein Dutzend Plätze nach Augenmaß zu beurteilen, ist aussichtslos. Der Vergleich stellt beide Sets Spalte für Spalte auf, sodass die Kompromisse ins Auge springen: keine Tabelle, kein Raten.</p>

<h2>So richtest du es ein</h2>
<p>Klick auf einer beliebigen Lösungsseite (deiner oder einem geteilten Build) auf <strong>Zum Vergleich hinzufügen</strong>. Mach das bei einem zweiten Build (oder einem dritten, oder vierten) und öffne den <a href="/choose_compare_sets/">Vergleich</a>. Du kannst auch Teil-Links direkt einfügen. Dein Warenkorb bleibt beim Stöbern erhalten, du sammelst also Kandidaten und vergleichst sie alle auf einmal.</p>

<h2>Das Ergebnis lesen</h2>
<p>Jedes Build bekommt eine Spalte; bei genau zweien gibt es zusätzlich eine <em>Diff</em>-Spalte, die den Abstand bei jedem Wert aufschlüsselt. Items, die sich beide Sets teilen, stehen auf einer Linie, sodass du sofort siehst, welche Teile sich wirklich unterscheiden und welche gleich bleiben. Da liegt meist die echte Entscheidung, nicht in den Summen, sondern in den zwei, drei Plätzen, die nicht gleich sind.</p>

<h2>Was du vergleichen kannst</h2>
<p>Der naheliegende Einsatz ist "mein aktuelles Set vs. der Vorschlag des Optimierers". Aber es taugt genauso für "PvM- vs. PvP-Variante", "günstige vs. teure Version" oder um einen Gildenstreit zu klären, indem du zwei geteilte Builds zusammenwirfst. Immer wenn du zwischen zwei Richtungen schwankst, vergleich sie, statt zu diskutieren.</p>

<p><em>Zwei Builds im Kopf? <a href="/choose_compare_sets/">Vergleich sie jetzt.</a></em></p>
''',
            },
        },
    },

    'understanding-your-solution': {
        'published': '2026-07-01',
        'i18n': {
            'en': {
                'title': "Reading your solution page: what the result tells you",
                'desc': "The Fashionista handed you a full set. Now what? How to read the solution page: the items it picked, your final stats, and the warnings that actually matter.",
                'lead': "You hit generate and a full set appears. Before you copy it into the game, it pays to understand what the solution page is showing you, and what to do when something looks off.",
                'body': '''
<h2>The set it built</h2>
<p>Every slot shows the item the optimizer chose: weapon, hat, cloak, rings, the lot. Click any piece to see its stats or to <strong>switch it</strong> for another candidate; the totals update on the spot. The set isn't sacred: it's the best the solver found for the weights and limits you gave it, and it's yours to nudge.</p>

<h2>The stats you actually get</h2>
<p>The characteristics panel adds up every line across the whole set (power, damage, resistances, AP/MP, the works), including set bonuses. This is the number that matters, not what any single item shows. If a total looks low, that's usually the sign a weight needs bumping, not a broken build.</p>

<h2>When something's flagged</h2>
<p>Ask for a minimum the items can't reach (12 AP, a resistance floor, a set-bonus condition) and the page tells you instead of quietly ignoring it. A flagged line means "no legal set hits this here." Loosen the minimum, raise the level, or accept the trade-off; the warning is information, not a failure.</p>

<h2>Make it yours</h2>
<p>Switch any slot, lock the pieces you love so the solver keeps them, forbid the ones you'll never farm, and run it again. Happy with it? Share the build, or drop it into the <a href="/choose_compare_sets/">comparison</a> against your current gear to see exactly what you'd gain.</p>

<p><em>No solution yet? <a href="/setup/">Start a build.</a></em></p>
''',
            },
            'fr': {
                'title': "Lire ta page de solution : ce que le résultat te dit",
                'desc': "La Fashionista t'a sorti un set complet. Et maintenant ? Lire la page de solution : les items choisis, tes stats finales, les avertissements importants.",
                'lead': "Tu cliques sur générer et un set complet apparaît. Avant de le recopier en jeu, ça vaut le coup de comprendre ce que la page de solution te montre, et quoi faire quand un truc cloche.",
                'body': '''
<h2>Le set qu'elle a construit</h2>
<p>Chaque emplacement affiche l'item que l'optimiseur a choisi : arme, chapeau, cape, anneaux, tout. Clique sur une pièce pour voir ses stats ou pour la <strong>remplacer</strong> par un autre candidat ; les totaux se mettent à jour direct. Le set n'est pas sacré : c'est le meilleur que le solveur a trouvé pour les poids et les limites que tu lui as donnés, et tu peux le retoucher.</p>

<h2>Les stats que t'obtiens vraiment</h2>
<p>Le panneau de caractéristiques additionne chaque ligne sur tout le set (puissance, dommages, résistances, PA/PM, tout), bonus de panoplie compris. C'est ce chiffre-là qui compte, pas ce qu'affiche un item isolé. Si un total te paraît faible, c'est en général le signe qu'un poids doit monter, pas que le build est cassé.</p>

<h2>Quand un truc est signalé</h2>
<p>Demande un minimum que les items ne peuvent pas atteindre (12 PA, un plancher de résistance, une condition de panoplie) et la page te le dit au lieu de l'ignorer en douce. Une ligne signalée veut dire "aucun set légal n'atteint ça ici". Assouplis le minimum, monte le niveau, ou accepte le compromis ; l'avertissement est une info, pas un échec.</p>

<h2>Fais-le tien</h2>
<p>Remplace n'importe quel emplacement, verrouille les pièces que t'adores pour que le solveur les garde, interdis celles que tu ne farmeras jamais, et relance. Satisfait ? Partage le build, ou balance-le dans le <a href="/choose_compare_sets/">comparateur</a> face à ton stuff actuel pour voir exactement ce que tu gagnerais.</p>

<p><em>Pas encore de solution ? <a href="/setup/">Lance un build.</a></em></p>
''',
            },
            'es': {
                'title': "Leer tu solución: lo que la página de resultado te dice",
                'desc': "La Fashionista te sacó un set completo. ¿Y ahora? Cómo leer la página de solución: los ítems elegidos, tus estadísticas finales y los avisos que importan.",
                'lead': "Le das a generar y aparece un set completo. Antes de copiarlo al juego, vale la pena entender qué te muestra la página de solución, y qué hacer cuando algo no cuadra.",
                'body': '''
<h2>El set que montó</h2>
<p>Cada ranura muestra el ítem que eligió el optimizador: arma, sombrero, capa, anillos, todo. Haz clic en cualquier pieza para ver sus estadísticas o para <strong>cambiarla</strong> por otro candidato; los totales se actualizan al momento. El set no es sagrado: es lo mejor que encontró el solucionador para los pesos y límites que le diste, y puedes ajustarlo.</p>

<h2>Las estadísticas que consigues de verdad</h2>
<p>El panel de características suma cada línea de todo el set (poder, daño, resistencias, PA/PM, todo), incluidos los bonus de conjunto. Ese es el número que importa, no lo que muestra un ítem suelto. Si un total te parece bajo, suele ser la señal de que hay que subir un peso, no de que el build esté roto.</p>

<h2>Cuando algo sale marcado</h2>
<p>Pide un mínimo que los ítems no pueden alcanzar (12 PA, un suelo de resistencia, una condición de conjunto) y la página te lo dice en vez de ignorarlo en silencio. Una línea marcada significa "ningún set legal llega a esto aquí". Relaja el mínimo, sube el nivel o acepta el compromiso; el aviso es información, no un fallo.</p>

<h2>Hazlo tuyo</h2>
<p>Cambia cualquier ranura, bloquea las piezas que te encantan para que el solucionador las mantenga, prohíbe las que nunca vas a farmear y vuelve a lanzarlo. ¿Contento? Comparte el build, o mételo en el <a href="/choose_compare_sets/">comparador</a> frente a tu equipo actual para ver exactamente qué ganarías.</p>

<p><em>¿Aún sin solución? <a href="/setup/">Empieza un build.</a></em></p>
''',
            },
            'pt': {
                'title': "Ler sua solução: o que a página de resultado te diz",
                'desc': "A Fashionista te entregou um set completo. E agora? Como ler a página de solução: os itens escolhidos, seus atributos finais e os avisos que importam.",
                'lead': "Você clica em gerar e aparece um set completo. Antes de copiar pro jogo, vale entender o que a página de solução está mostrando, e o que fazer quando algo parece errado.",
                'body': '''
<h2>O set que ela montou</h2>
<p>Cada slot mostra o item que o otimizador escolheu: arma, chapéu, capa, anéis, tudo. Clique em qualquer peça pra ver os atributos ou pra <strong>trocá-la</strong> por outro candidato; os totais atualizam na hora. O set não é sagrado: é o melhor que o solver achou pros pesos e limites que você deu, e dá pra ajustar.</p>

<h2>Os atributos que você realmente ganha</h2>
<p>O painel de características soma cada linha do set inteiro (potência, dano, resistências, PA/PM, tudo), incluindo bônus de conjunto. É esse número que importa, não o que um item isolado mostra. Se um total parece baixo, geralmente é sinal de que um peso precisa subir, não de que o build está quebrado.</p>

<h2>Quando algo é sinalizado</h2>
<p>Peça um mínimo que os itens não conseguem atingir (12 PA, um piso de resistência, uma condição de conjunto) e a página te avisa em vez de ignorar em silêncio. Uma linha sinalizada quer dizer "nenhum set legal alcança isso aqui". Afrouxe o mínimo, suba o nível ou aceite o trade-off; o aviso é informação, não uma falha.</p>

<h2>Deixe do seu jeito</h2>
<p>Troque qualquer slot, trave as peças que você ama pra o solver mantê-las, proíba as que você nunca vai farmar e rode de novo. Curtiu? Compartilhe o build, ou jogue no <a href="/choose_compare_sets/">comparador</a> contra o seu equipamento atual pra ver exatamente o que você ganharia.</p>

<p><em>Ainda sem solução? <a href="/setup/">Comece um build.</a></em></p>
''',
            },
            'de': {
                'title': "Deine Lösung lesen: was die Ergebnisseite wirklich sagt",
                'desc': "Die Fashionista hat dir ein komplettes Set gebaut. Und jetzt? Wie du die Lösungsseite liest: die gewählten Items, deine Endwerte und die Warnungen, die zählen.",
                'lead': "Du klickst auf Generieren und ein komplettes Set erscheint. Bevor du es ins Spiel überträgst, lohnt es sich zu verstehen, was die Lösungsseite dir zeigt, und was zu tun ist, wenn etwas nicht passt.",
                'body': '''
<h2>Das Set, das sie gebaut hat</h2>
<p>Jeder Platz zeigt das Item, das der Optimierer gewählt hat: Waffe, Hut, Umhang, Ringe, alles. Klick auf ein Teil, um seine Werte zu sehen oder es gegen einen anderen Kandidaten <strong>auszutauschen</strong>; die Summen aktualisieren sich sofort. Das Set ist nicht in Stein gemeißelt: es ist das Beste, was der Solver für die Gewichte und Grenzen gefunden hat, die du ihm gegeben hast, und du darfst nachjustieren.</p>

<h2>Die Werte, die du wirklich bekommst</h2>
<p>Das Eigenschaften-Feld summiert jede Zeile über das ganze Set (Stärke, Schaden, Resistenzen, AP/BP, alles), Set-Boni inklusive. Diese Zahl zählt, nicht was ein einzelnes Item anzeigt. Wirkt eine Summe niedrig, ist das meist das Zeichen, dass ein Gewicht hoch muss, nicht dass das Build kaputt ist.</p>

<h2>Wenn etwas markiert ist</h2>
<p>Verlang ein Minimum, das die Items nicht erreichen können (12 AP, eine Resistenz-Untergrenze, eine Set-Bedingung) und die Seite sagt es dir, statt es stillschweigend zu ignorieren. Eine markierte Zeile heißt "kein zulässiges Set schafft das hier". Lockere das Minimum, erhöhe die Stufe oder akzeptiere den Kompromiss; die Warnung ist eine Info, kein Fehler.</p>

<h2>Mach es zu deinem</h2>
<p>Tausch jeden Platz, sperr die Teile, die du liebst, damit der Solver sie behält, verbiete die, die du nie farmst, und lass es neu laufen. Zufrieden? Teil das Build oder wirf es in den <a href="/choose_compare_sets/">Vergleich</a> gegen deine aktuelle Ausrüstung, um genau zu sehen, was du gewinnen würdest.</p>

<p><em>Noch keine Lösung? <a href="/setup/">Starte ein Build.</a></em></p>
''',
            },
        },
    },

    'tuning-your-weights': {
        'published': '2026-07-02',
        'i18n': {
            'en': {
                'title': "Tuning your weights: tell the optimizer what matters",
                'desc': "The weights page is where a generic set becomes your set. What the numbers mean, presets vs custom weights, and the mistakes that quietly ruin a solution.",
                'lead': "The optimizer doesn't guess what you want: it maximizes exactly what you tell it to. The weights page is where you tell it. Five minutes here beats an hour of switching items by hand.",
                'body': '''
<h2>What a weight actually is</h2>
<p>Every characteristic gets a number: how many points of value one unit of that stat is worth to you. The solver adds it all up across every candidate set and returns the highest total. A weight of 0 means "I don't care at all": the stat can end up at anything. A big weight means the solver will sacrifice other things to get it. There is no magic scale; only the ratios between your weights matter.</p>

<h2>Presets first, custom second</h2>
<p>The wizard's questions (element, playstyle, level) generate a sensible starting profile, and the <a href="/smartbuild/">smart build</a> does the same from a text description. Start there. Then open the weights page and nudge: hunting resistances for a tanky feel, raising crit for a crit build, zeroing prospecting if you never farm. Small edits to a good preset beat writing twenty numbers from scratch.</p>

<h2>Weights are wishes; minimums are rules</h2>
<p>If something is non-negotiable (12 AP, 6 MP, a vitality floor), don't inflate its weight: set a <strong>minimum</strong> instead. A minimum is a hard constraint the solver must satisfy; a weight is a preference it trades against everything else. Overweighting AP "to be safe" is the classic mistake: the solver chases AP the set already has and neglects the stats you actually wanted.</p>

<h2>When the result looks off</h2>
<p>A weird solution is almost always the weights talking. Too much vitality and no damage? Your vitality weight dominates. An empty slot? No item there scores positive value under your weights. Iterate: change one number, re-run, compare. The <a href="/choose_compare_sets/">comparison</a> shows exactly what your edit bought you.</p>

<p><em>Ready to fine-tune? <a href="/setup/">Open a project</a> and head to the weights page.</em></p>
''',
            },
            'fr': {
                'title': "Bien régler tes poids : dire à l'optimiseur ce qui compte",
                'desc': "La page des poids, c'est là qu'un set générique devient ton set. Ce que veulent dire les chiffres, presets ou poids perso, et les erreurs qui ruinent tout.",
                'lead': "L'optimiseur ne devine pas ce que tu veux : il maximise exactement ce que tu lui dis. La page des poids, c'est là que tu lui dis. Cinq minutes ici valent mieux qu'une heure à changer les items à la main.",
                'body': '''
<h2>C'est quoi, un poids</h2>
<p>Chaque caractéristique reçoit un nombre : combien de points de valeur vaut une unité de cette stat pour toi. Le solveur additionne tout sur chaque set candidat et renvoie le meilleur total. Un poids de 0 veut dire « je m'en fiche complètement » : la stat peut finir n'importe où. Un gros poids, et le solveur sacrifiera le reste pour l'obtenir. Il n'y a pas d'échelle magique ; seuls les rapports entre tes poids comptent.</p>

<h2>Preset d'abord, personnalisation ensuite</h2>
<p>Les questions de l'assistant (élément, style de jeu, niveau) génèrent un profil de départ raisonnable, et le <a href="/smartbuild/">build intelligent</a> fait pareil depuis une description texte. Pars de là. Puis ouvre la page des poids et ajuste : monte les résistances pour un feeling tanky, monte le critique pour un build crit, mets la prospection à zéro si tu ne farmes jamais. Retoucher un bon preset bat l'écriture de vingt chiffres à partir de rien.</p>

<h2>Les poids sont des souhaits ; les minimums sont des règles</h2>
<p>Si quelque chose est non négociable (12 PA, 6 PM, un plancher de vitalité), ne gonfle pas son poids : mets un <strong>minimum</strong> à la place. Un minimum est une contrainte dure que le solveur doit satisfaire ; un poids est une préférence qu'il arbitre contre tout le reste. Surponder les PA « par sécurité » est l'erreur classique : le solveur court après des PA que le set a déjà et néglige les stats que tu voulais vraiment.</p>

<h2>Quand le résultat semble bizarre</h2>
<p>Une solution étrange, c'est presque toujours les poids qui parlent. Trop de vitalité et pas de dégâts ? Ton poids vitalité domine. Un emplacement vide ? Aucun item n'y apporte de valeur positive avec tes poids. Itère : change un chiffre, relance, compare. Le <a href="/choose_compare_sets/">comparateur</a> montre exactement ce que ta retouche t'a acheté.</p>

<p><em>Prêt à affiner ? <a href="/setup/">Ouvre un projet</a> et va sur la page des poids.</em></p>
''',
            },
            'es': {
                'title': "Ajustar tus pesos: dile al optimizador lo que importa",
                'desc': "La página de pesos es donde un set genérico se vuelve tuyo. Qué significan los números, presets o pesos personalizados, y los errores que arruinan todo.",
                'lead': "El optimizador no adivina lo que quieres: maximiza exactamente lo que le dices. La página de pesos es donde se lo dices. Cinco minutos aquí valen más que una hora cambiando ítems a mano.",
                'body': '''
<h2>Qué es un peso</h2>
<p>Cada característica recibe un número: cuántos puntos de valor vale para ti una unidad de esa estadística. El solucionador lo suma todo en cada set candidato y devuelve el mejor total. Un peso de 0 significa "no me importa nada": la estadística puede acabar en cualquier valor. Un peso grande, y el solucionador sacrificará el resto para conseguirla. No hay escala mágica; solo importan las proporciones entre tus pesos.</p>

<h2>Primero el preset, después lo personalizado</h2>
<p>Las preguntas del asistente (elemento, estilo de juego, nivel) generan un perfil de partida razonable, y el <a href="/smartbuild/">build inteligente</a> hace lo mismo desde una descripción de texto. Empieza ahí. Luego abre la página de pesos y ajusta: sube las resistencias para un toque tanque, sube el crítico para un build de críticos, pon la prospección a cero si nunca farmeas. Retocar un buen preset gana a escribir veinte números desde cero.</p>

<h2>Los pesos son deseos; los mínimos son reglas</h2>
<p>Si algo no es negociable (12 PA, 6 PM, un suelo de vitalidad), no infles su peso: pon un <strong>mínimo</strong>. Un mínimo es una restricción dura que el solucionador debe cumplir; un peso es una preferencia que negocia contra todo lo demás. Sobreponderar los PA "por seguridad" es el error clásico: el solucionador persigue PA que el set ya tiene y descuida las estadísticas que de verdad querías.</p>

<h2>Cuando el resultado se ve raro</h2>
<p>Una solución extraña casi siempre son los pesos hablando. ¿Mucha vitalidad y nada de daño? Tu peso de vitalidad domina. ¿Una ranura vacía? Ningún ítem aporta ahí valor positivo con tus pesos. Itera: cambia un número, relanza, compara. El <a href="/choose_compare_sets/">comparador</a> muestra exactamente qué te compró tu ajuste.</p>

<p><em>¿Listo para afinar? <a href="/setup/">Abre un proyecto</a> y ve a la página de pesos.</em></p>
''',
            },
            'pt': {
                'title': "Ajustar seus pesos: diga ao otimizador o que importa",
                'desc': "A página de pesos é onde um set genérico vira o seu. O que os números significam, presets ou pesos personalizados, e os erros que arruínam tudo.",
                'lead': "O otimizador não adivinha o que você quer: ele maximiza exatamente o que você diz. A página de pesos é onde você diz. Cinco minutos aqui valem mais que uma hora trocando itens na mão.",
                'body': '''
<h2>O que é um peso</h2>
<p>Cada característica recebe um número: quantos pontos de valor uma unidade daquele atributo vale para você. O solver soma tudo em cada set candidato e devolve o melhor total. Peso 0 significa "não me importo nada": o atributo pode terminar em qualquer valor. Um peso grande, e o solver sacrifica o resto para consegui-lo. Não existe escala mágica; só as proporções entre os seus pesos importam.</p>

<h2>Preset primeiro, personalização depois</h2>
<p>As perguntas do assistente (elemento, estilo de jogo, nível) geram um perfil inicial razoável, e o <a href="/smartbuild/">build inteligente</a> faz o mesmo a partir de uma descrição em texto. Comece por aí. Depois abra a página de pesos e ajuste: suba as resistências para um jeito tanque, suba o crítico para um build de crítico, zere a prospecção se você nunca farma. Retocar um bom preset ganha de escrever vinte números do zero.</p>

<h2>Pesos são desejos; mínimos são regras</h2>
<p>Se algo é inegociável (12 PA, 6 PM, um piso de vitalidade), não infle o peso: defina um <strong>mínimo</strong>. Um mínimo é uma restrição dura que o solver precisa cumprir; um peso é uma preferência que ele negocia contra todo o resto. Superponderar PA "por garantia" é o erro clássico: o solver corre atrás de PA que o set já tem e negligencia os atributos que você queria de verdade.</p>

<h2>Quando o resultado parece estranho</h2>
<p>Uma solução esquisita é quase sempre culpa dos pesos. Muita vitalidade e nada de dano? Seu peso de vitalidade domina. Um slot vazio? Nenhum item ali soma valor positivo com os seus pesos. Itere: mude um número, rode de novo, compare. O <a href="/choose_compare_sets/">comparador</a> mostra exatamente o que o seu ajuste comprou.</p>

<p><em>Pronto para afinar? <a href="/setup/">Abra um projeto</a> e vá à página de pesos.</em></p>
''',
            },
            'de': {
                'title': "Gewichte einstellen: dem Optimierer sagen, was zählt",
                'desc': "Auf der Gewichte-Seite wird aus einem generischen Set dein Set. Was die Zahlen bedeuten, Presets oder eigene Gewichte, und welche Fehler alles ruinieren.",
                'lead': "Der Optimierer rät nicht, was du willst: er maximiert genau das, was du ihm sagst. Auf der Gewichte-Seite sagst du es ihm. Fünf Minuten hier schlagen eine Stunde Items-Tauschen von Hand.",
                'body': '''
<h2>Was ein Gewicht eigentlich ist</h2>
<p>Jede Eigenschaft bekommt eine Zahl: wie viele Wertpunkte dir eine Einheit dieses Werts bedeutet. Der Solver summiert alles über jedes Kandidaten-Set und liefert die höchste Gesamtsumme. Ein Gewicht von 0 heißt "völlig egal": der Wert kann irgendwo landen. Ein großes Gewicht, und der Solver opfert anderes dafür. Es gibt keine magische Skala; nur die Verhältnisse zwischen deinen Gewichten zählen.</p>

<h2>Erst Preset, dann Feintuning</h2>
<p>Die Fragen des Assistenten (Element, Spielstil, Stufe) erzeugen ein vernünftiges Startprofil, und das <a href="/smartbuild/">Smart Build</a> macht dasselbe aus einer Textbeschreibung. Fang dort an. Dann öffne die Gewichte-Seite und justiere nach: Resistenzen hoch für ein zäheres Set, Krit hoch für ein Krit-Build, Prospektion auf null, wenn du nie farmst. Ein gutes Preset nachzuschärfen schlägt zwanzig Zahlen aus dem Nichts.</p>

<h2>Gewichte sind Wünsche; Minima sind Regeln</h2>
<p>Wenn etwas nicht verhandelbar ist (12 AP, 6 BP, eine Vitalitäts-Untergrenze), bläh nicht das Gewicht auf: setz stattdessen ein <strong>Minimum</strong>. Ein Minimum ist eine harte Bedingung, die der Solver erfüllen muss; ein Gewicht ist eine Vorliebe, die er gegen alles andere abwägt. AP "zur Sicherheit" zu übergewichten ist der Klassiker: der Solver jagt AP hinterher, die das Set längst hat, und vernachlässigt die Werte, die du eigentlich wolltest.</p>

<h2>Wenn das Ergebnis komisch aussieht</h2>
<p>Eine seltsame Lösung sind fast immer die Gewichte. Viel Vitalität, kein Schaden? Dein Vitalitätsgewicht dominiert. Ein leerer Platz? Kein Item bringt dort mit deinen Gewichten positiven Wert. Iteriere: eine Zahl ändern, neu laufen lassen, vergleichen. Der <a href="/choose_compare_sets/">Vergleich</a> zeigt genau, was dir die Änderung gebracht hat.</p>

<p><em>Bereit zum Feintuning? <a href="/setup/">Öffne ein Projekt</a> und geh zur Gewichte-Seite.</em></p>
''',
            },
        },
    },

    'forgemagie-planning': {
        'published': '2026-07-02',
        'i18n': {
            'en': {
                'title': "Planning a maging run: simulate before you burn kamas",
                'desc': "Smithmagic is a money pit when you improvise. How the simulator works (sink, over/exo weight, the 101 cap) and how to plan a run before you buy runes.",
                'lead': "Every mager has a story about the item they destroyed at 3 a.m. The simulator exists so that story isn't yours: plan the runs, see what can pass, then spend.",
                'body': '''
<h2>What the simulator does</h2>
<p>Open the <a href="/forgemagie/">smithmagic simulator</a>, pick an item, and set the stats you want on it. The tool knows every stat's rune weight and the item's sink, and tells you whether your plan is even possible, before you buy anything.</p>

<h2>Sink, in one paragraph</h2>
<p>Every stat you push above the item's natural roll costs weight, and the item only has so much room. The simulator tracks that budget for you: a plan that fits reads as safe, a tight one reads as risky, and an impossible one is called out in red. No more discovering the hard way that your dream line never fit.</p>

<h2>The two rules that kill plans</h2>
<p>First, the <strong>101 cap</strong>: the total over/exo weight on a single stat can never exceed 101, and the simulator flags any stat where your target crosses it. Second, <strong>AP, MP and Range exos</strong> only land on a critical success, commonly estimated around 1% per rune: the tool marks these lines so you budget them as a long grind, not a quick job.</p>

<h2>A sane workflow</h2>
<p>Generate your target build first, so you know which stats the set actually needs. Then simulate the maging on each candidate item and compare: sometimes hunting a different item beats overmaging the one you own. When the plan reads safe, buy the runes, and not before.</p>

<p><em>Got an item in mind? <a href="/forgemagie/">Open the simulator</a> and test your plan.</em></p>
''',
            },
            'fr': {
                'title': "Planifier ta forgemagie : simule avant de brûler tes kamas",
                'desc': "La forgemagie est un gouffre à kamas quand on improvise. Comprends le simulateur (puits, poids over/exo, plafond 101) et planifie avant d'acheter des runes.",
                'lead': "Chaque forgemage a une histoire d'objet détruit à 3 h du matin. Le simulateur existe pour que cette histoire ne soit pas la tienne : planifie, vois ce qui peut passer, puis dépense.",
                'body': '''
<h2>Ce que fait le simulateur</h2>
<p>Ouvre le <a href="/forgemagie/">simulateur de forgemagie</a>, choisis un objet, et pose les stats que tu veux dessus. L'outil connaît le poids de rune de chaque stat et le puits de l'objet, et te dit si ton plan est seulement possible, avant d'acheter quoi que ce soit.</p>

<h2>Le puits, en un paragraphe</h2>
<p>Chaque stat que tu montes au-dessus du jet naturel de l'objet coûte du poids, et l'objet n'a qu'une marge limitée. Le simulateur suit ce budget pour toi : un plan qui rentre s'affiche comme sûr, un plan serré comme risqué, et un plan impossible est signalé en rouge. Fini de découvrir à tes dépens que ta ligne de rêve ne rentrait pas.</p>

<h2>Les deux règles qui tuent les plans</h2>
<p>D'abord, le <strong>plafond de 101</strong> : le poids total en over/exo sur une même stat ne peut jamais dépasser 101, et le simulateur signale toute stat où ta cible le franchit. Ensuite, les <strong>exos PA, PM et PO</strong> ne passent que sur un succès critique, estimé autour de 1 % par rune : l'outil marque ces lignes pour que tu les budgètes comme un long grind, pas comme une affaire vite pliée.</p>

<h2>Un déroulé sain</h2>
<p>Génère d'abord ton build cible, pour savoir quelles stats le set attend vraiment. Puis simule la forgemagie sur chaque objet candidat et compare : parfois, chasser un autre objet vaut mieux qu'overmager celui que tu possèdes. Quand le plan s'affiche sûr, achète les runes, et pas avant.</p>

<p><em>Un objet en tête ? <a href="/forgemagie/">Ouvre le simulateur</a> et teste ton plan.</em></p>
''',
            },
            'es': {
                'title': "Planificar tu forjamagia: simula antes de quemar kamas",
                'desc': "La forjamagia es un pozo de kamas cuando improvisas. Cómo funciona el simulador (pozo, peso over/exo, límite de 101) y cómo planificar antes de comprar runas.",
                'lead': "Todo forjamago tiene una historia de un objeto destruido a las 3 de la mañana. El simulador existe para que esa historia no sea la tuya: planifica, mira qué puede pasar, y luego gasta.",
                'body': '''
<h2>Qué hace el simulador</h2>
<p>Abre el <a href="/forgemagie/">simulador de forjamagia</a>, elige un objeto y pon las estadísticas que quieres en él. La herramienta conoce el peso de runa de cada estadística y el pozo del objeto, y te dice si tu plan es siquiera posible, antes de comprar nada.</p>

<h2>El pozo, en un párrafo</h2>
<p>Cada estadística que subes por encima de la tirada natural del objeto cuesta peso, y el objeto solo tiene un margen limitado. El simulador lleva ese presupuesto por ti: un plan que cabe se muestra seguro, uno justo se muestra arriesgado, y uno imposible se marca en rojo. Se acabó descubrir por las malas que tu línea soñada nunca cabía.</p>

<h2>Las dos reglas que matan planes</h2>
<p>Primero, el <strong>límite de 101</strong>: el peso total en over/exo sobre una misma estadística nunca puede superar 101, y el simulador marca cualquier estadística donde tu objetivo lo cruce. Segundo, los <strong>exos de PA, PM y Alcance</strong> solo pasan con un éxito crítico, estimado en torno al 1% por runa: la herramienta señala esas líneas para que las presupuestes como un grind largo, no como algo rápido.</p>

<h2>Un flujo sensato</h2>
<p>Genera primero tu build objetivo, para saber qué estadísticas necesita de verdad el set. Luego simula la forja en cada objeto candidato y compara: a veces cazar otro objeto gana a overmagear el que ya tienes. Cuando el plan se muestre seguro, compra las runas, y no antes.</p>

<p><em>¿Un objeto en mente? <a href="/forgemagie/">Abre el simulador</a> y prueba tu plan.</em></p>
''',
            },
            'pt': {
                'title': "Planejar sua forjamagia: simule antes de queimar kamas",
                'desc': "Forjamagia é um poço de kamas quando você improvisa. Como funciona o simulador (poço, peso over/exo, teto de 101) e como planejar antes de comprar runas.",
                'lead': "Todo forjamago tem uma história de item destruído às 3 da manhã. O simulador existe para que essa história não seja a sua: planeje, veja o que pode passar, depois gaste.",
                'body': '''
<h2>O que o simulador faz</h2>
<p>Abra o <a href="/forgemagie/">simulador de forjamagia</a>, escolha um item e defina os atributos que você quer nele. A ferramenta conhece o peso de runa de cada atributo e o poço do item, e diz se o seu plano é sequer possível, antes de comprar qualquer coisa.</p>

<h2>O poço, em um parágrafo</h2>
<p>Cada atributo que você sobe acima do jet natural do item custa peso, e o item só tem uma margem limitada. O simulador acompanha esse orçamento por você: um plano que cabe aparece como seguro, um apertado como arriscado, e um impossível é marcado em vermelho. Chega de descobrir do jeito difícil que a sua linha dos sonhos nunca coube.</p>

<h2>As duas regras que matam planos</h2>
<p>Primeiro, o <strong>teto de 101</strong>: o peso total em over/exo em um mesmo atributo nunca pode passar de 101, e o simulador sinaliza qualquer atributo em que a sua meta o ultrapasse. Segundo, os <strong>exos de PA, PM e Alcance</strong> só passam com um sucesso crítico, estimado em torno de 1% por runa: a ferramenta marca essas linhas para você orçá-las como um grind longo, não como serviço rápido.</p>

<h2>Um fluxo saudável</h2>
<p>Gere primeiro o seu build alvo, para saber quais atributos o set realmente precisa. Depois simule a forja em cada item candidato e compare: às vezes caçar outro item ganha de overmagear o que você já tem. Quando o plano aparecer seguro, compre as runas, e não antes.</p>

<p><em>Um item em mente? <a href="/forgemagie/">Abra o simulador</a> e teste seu plano.</em></p>
''',
            },
            'de': {
                'title': "Schmiedemagie planen: erst der Simulator, dann die Kamas",
                'desc': "Schmiedemagie ist ein Kama-Grab, wenn man improvisiert. Wie der Simulator funktioniert (Senke, Over/Exo-Gewicht, 101-Grenze) und wie du vorher planst.",
                'lead': "Jeder Schmiedemagier hat eine Geschichte über das Item, das er um 3 Uhr nachts zerstört hat. Den Simulator gibt es, damit diese Geschichte nicht deine wird: planen, sehen was durchgehen kann, dann ausgeben.",
                'body': '''
<h2>Was der Simulator macht</h2>
<p>Öffne den <a href="/forgemagie/">Schmiedemagie-Simulator</a>, wähl ein Item und setz die Werte, die du darauf willst. Das Tool kennt das Runengewicht jedes Werts und die Senke des Items, und sagt dir, ob dein Plan überhaupt möglich ist, bevor du irgendetwas kaufst.</p>

<h2>Die Senke, in einem Absatz</h2>
<p>Jeder Wert, den du über den natürlichen Wurf des Items hinaus treibst, kostet Gewicht, und das Item hat nur begrenzten Spielraum. Der Simulator führt dieses Budget für dich: ein Plan, der passt, gilt als sicher, ein knapper als riskant, und ein unmöglicher wird rot markiert. Nie wieder auf die harte Tour lernen, dass die Traumzeile nie gepasst hätte.</p>

<h2>Die zwei Regeln, die Pläne killen</h2>
<p>Erstens die <strong>101-Grenze</strong>: das gesamte Over/Exo-Gewicht auf einem einzelnen Wert kann nie über 101 gehen, und der Simulator markiert jeden Wert, bei dem dein Ziel sie reißt. Zweitens landen <strong>AP-, BP- und Reichweiten-Exos</strong> nur bei einem kritischen Erfolg, üblicherweise um 1% pro Rune geschätzt: das Tool kennzeichnet diese Zeilen, damit du sie als langen Grind einplanst, nicht als schnelle Nummer.</p>

<h2>Ein vernünftiger Ablauf</h2>
<p>Erzeuge zuerst dein Ziel-Build, damit du weißt, welche Werte das Set wirklich braucht. Dann simuliere die Schmiedemagie auf jedem Kandidaten-Item und vergleiche: manchmal schlägt die Jagd nach einem anderen Item das Overmagen des eigenen. Erst wenn der Plan sicher aussieht, kauf die Runen, und nicht vorher.</p>

<p><em>Ein Item im Kopf? <a href="/forgemagie/">Öffne den Simulator</a> und teste deinen Plan.</em></p>
''',
            },
        },
    },
    'crafting-and-professions': {
        'published': '2026-07-10',
        'i18n': {
            'en': {
                'title': 'Crafting and professions in Dofus, version by version',
                'desc': "Where a recipe comes from, which profession crafts it and where the ingredients drop: how to plan a craft with the encyclopedia, in every Dofus version.",
                'lead': "Crafting looks simple until you need one missing ingredient at the worst moment. Here is how to plan a craft from the item page down to the monsters you will actually hunt.",
                'body': '''
<h2>Start from the item, not from the recipe</h2>
<p>Open any craftable item in the <a href="/encyclopedia/">encyclopedia</a> and the recipe sits right on its page, with the profession that crafts it and, where the game defines one, the level it asks for. Special workbench recipes that no player profession can learn simply show no profession line: that is the game's own data, not a gap.</p>

<h2>Every ingredient is one click away</h2>
<p>Each ingredient in a recipe links to its own resource page: what else it is used to craft, and which monsters drop it with their rates. That last part turns a shopping list into a hunting plan: if the resource drops from a monster you can farm, you can decide whether to buy or to hunt with actual numbers instead of guesses.</p>

<h2>Professions differ by version</h2>
<p>The profession behind a recipe is not the same story in every version. Modern Dofus merged the old crafting professions, so a sword recipe belongs to the unified Smith. Dofus Retro (1.29) still lives before that merge: the encyclopedia shows the era-accurate professions like Sword Smith or Hammer Smith, and recipes there carry no level requirement because the 1.29 data defines none. Dofus Touch sits in between with its own set of professions. The tool reads each version's own game files, so what you see matches what your version actually plays like.</p>

<h2>Resources are searchable too</h2>
<p>The encyclopedia search does not stop at equipment: type a resource name and you will land on its page directly, in any of the five supported languages, accents optional. From there, the "used to craft" list answers the reverse question: is this thing in my bank worth keeping?</p>

<h2>Planning a craft for a build</h2>
<p>The practical loop: generate your build, open the items the optimizer picked, and check their recipes. If a piece is craftable, its ingredients and their drop sources tell you whether crafting beats buying on your server. Keep the resource pages open while you farm; the drop rates are per monster, so you can pick the target that actually pays.</p>

<p><em>Missing one ingredient right now? <a href="/encyclopedia/">Search it in the encyclopedia</a> and see who drops it.</em></p>
''',
            },
            'fr': {
                'title': 'Craft et métiers sur Dofus, version par version',
                'desc': "D'où vient une recette, quel métier la fabrique et où droppent les ingrédients : comment planifier un craft avec l'encyclopédie, dans chaque version de Dofus.",
                'lead': "Le craft a l'air simple jusqu'au moment où il manque un ingrédient au pire moment. Voici comment planifier un craft depuis la page de l'objet jusqu'aux monstres que vous allez vraiment chasser.",
                'body': '''
<h2>Partez de l'objet, pas de la recette</h2>
<p>Ouvrez n'importe quel objet fabricable dans l'<a href="/encyclopedia/">encyclopédie</a> : la recette est sur sa page, avec le métier qui la fabrique et, quand le jeu en définit un, le niveau demandé. Les recettes d'établis spéciaux qu'aucun métier de joueur ne peut apprendre n'affichent simplement pas de ligne de métier : c'est la donnée du jeu, pas un oubli.</p>

<h2>Chaque ingrédient est à un clic</h2>
<p>Chaque ingrédient d'une recette mène à sa propre page de ressource : ce qu'il sert à fabriquer d'autre, et quels monstres le droppent avec leurs taux. C'est ce qui transforme une liste de courses en plan de chasse : si la ressource tombe sur un monstre farmable, vous décidez d'acheter ou de chasser avec de vrais chiffres plutôt qu'au doigt mouillé.</p>

<h2>Les métiers changent selon la version</h2>
<p>Le métier derrière une recette ne raconte pas la même histoire partout. Le Dofus moderne a fusionné les anciens métiers de forge, donc une recette d'épée appartient au Forgeron unifié. Dofus Retro (1.29) vit encore avant cette fusion : l'encyclopédie y montre les métiers d'époque comme Forgeur d'Épées ou Forgeur de Marteaux, et les recettes n'y portent pas de niveau requis parce que les données 1.29 n'en définissent pas. Dofus Touch a son propre jeu de métiers, entre les deux. L'outil lit les fichiers de jeu de chaque version : ce que vous voyez correspond à ce que votre version joue vraiment.</p>

<h2>Les ressources aussi se cherchent</h2>
<p>La recherche de l'encyclopédie ne s'arrête pas aux équipements : tapez un nom de ressource et vous arrivez directement sur sa page, dans n'importe laquelle des cinq langues du site, accents facultatifs. De là, la liste « Sert à fabriquer » répond à la question inverse : ce truc dans ma banque vaut-il la peine d'être gardé ?</p>

<h2>Planifier un craft pour un build</h2>
<p>La boucle pratique : générez votre build, ouvrez les objets choisis par l'optimiseur et regardez leurs recettes. Si une pièce est fabricable, ses ingrédients et leurs sources de drop vous disent si le craft bat l'achat sur votre serveur. Gardez les pages de ressources ouvertes pendant le farm : les taux sont par monstre, vous choisissez la cible qui rapporte vraiment.</p>

<p><em>Il vous manque un ingrédient là, tout de suite ? <a href="/encyclopedia/">Cherchez-le dans l'encyclopédie</a> et voyez qui le droppe.</em></p>
''',
            },
            'es': {
                'title': 'Fabricación y oficios en Dofus, versión por versión',
                'desc': "De dónde sale una receta, qué oficio la fabrica y dónde caen los ingredientes: cómo planificar una fabricación con la enciclopedia, en cada versión de Dofus.",
                'lead': "Fabricar parece sencillo hasta que falta un ingrediente en el peor momento. Así se planifica una fabricación desde la página del objeto hasta los monstruos que de verdad vas a cazar.",
                'body': '''
<h2>Empieza por el objeto, no por la receta</h2>
<p>Abre cualquier objeto fabricable en la <a href="/encyclopedia/">enciclopedia</a>: la receta está en su página, con el oficio que la fabrica y, cuando el juego lo define, el nivel que exige. Las recetas de bancos de trabajo especiales que ningún oficio de jugador puede aprender simplemente no muestran línea de oficio: es el dato del juego, no un descuido.</p>

<h2>Cada ingrediente está a un clic</h2>
<p>Cada ingrediente de una receta lleva a su propia página de recurso: qué más sirve para fabricar y qué monstruos lo sueltan con sus tasas. Eso convierte una lista de la compra en un plan de caza: si el recurso cae de un monstruo farmeable, decides entre comprar o cazar con números reales en la mano.</p>

<h2>Los oficios cambian según la versión</h2>
<p>El oficio detrás de una receta no cuenta la misma historia en todas partes. El Dofus moderno fusionó los antiguos oficios de forja, así que una receta de espada pertenece al Herrero unificado. Dofus Retro (1.29) vive antes de esa fusión: la enciclopedia muestra los oficios de la época, como Forjador de Espadas, y las recetas no llevan nivel requerido porque los datos de 1.29 no lo definen. Dofus Touch tiene su propio conjunto de oficios, a medio camino. La herramienta lee los archivos de juego de cada versión: lo que ves corresponde a lo que tu versión realmente juega.</p>

<h2>Los recursos también se buscan</h2>
<p>La búsqueda de la enciclopedia no se queda en el equipamiento: escribe el nombre de un recurso y aterrizas directamente en su página, en cualquiera de los cinco idiomas del sitio, con o sin acentos. Desde ahí, la lista « Sirve para fabricar » responde la pregunta inversa: ¿vale la pena guardar esto que tengo en el banco?</p>

<h2>Planificar una fabricación para un build</h2>
<p>El bucle práctico: genera tu build, abre los objetos que eligió el optimizador y mira sus recetas. Si una pieza es fabricable, sus ingredientes y sus fuentes de drop te dicen si fabricar gana a comprar en tu servidor. Mantén abiertas las páginas de recursos mientras farmeas: las tasas son por monstruo, así eliges el objetivo que de verdad compensa.</p>

<p><em>¿Te falta un ingrediente ahora mismo? <a href="/encyclopedia/">Búscalo en la enciclopedia</a> y mira quién lo suelta.</em></p>
''',
            },
            'pt': {
                'title': 'Fabricação e profissões no Dofus, versão por versão',
                'desc': "De onde vem uma receita, qual profissão a fabrica e onde os ingredientes dropam: como planejar uma fabricação com a enciclopédia, em cada versão de Dofus.",
                'lead': "Fabricar parece simples até faltar um ingrediente na pior hora. Veja como planejar uma fabricação da página do item até os monstros que você vai realmente caçar.",
                'body': '''
<h2>Comece pelo item, não pela receita</h2>
<p>Abra qualquer item fabricável na <a href="/encyclopedia/">enciclopédia</a>: a receita está na página dele, com a profissão que a fabrica e, quando o jogo define, o nível exigido. Receitas de bancadas especiais que nenhuma profissão de jogador pode aprender simplesmente não mostram linha de profissão: é o dado do jogo, não um esquecimento.</p>

<h2>Cada ingrediente está a um clique</h2>
<p>Cada ingrediente de uma receita leva à sua própria página de recurso: o que mais ele fabrica e quais monstros o dropam, com as taxas. Isso transforma uma lista de compras em plano de caça: se o recurso cai de um monstro farmável, você decide entre comprar ou caçar com números de verdade.</p>

<h2>As profissões mudam conforme a versão</h2>
<p>A profissão por trás de uma receita não conta a mesma história em todo lugar. O Dofus moderno fundiu as antigas profissões de forja, então uma receita de espada pertence ao Ferreiro unificado. O Dofus Retro (1.29) ainda vive antes dessa fusão: a enciclopédia mostra as profissões da época, como Forjador de Espadas, e as receitas não trazem nível exigido porque os dados de 1.29 não o definem. O Dofus Touch tem seu próprio conjunto de profissões, no meio do caminho. A ferramenta lê os arquivos de jogo de cada versão: o que você vê corresponde ao que a sua versão realmente joga.</p>

<h2>Recursos também aparecem na busca</h2>
<p>A busca da enciclopédia não para no equipamento: digite o nome de um recurso e você cai direto na página dele, em qualquer um dos cinco idiomas do site, com ou sem acentos. De lá, a lista « Serve para fabricar » responde a pergunta inversa: vale a pena guardar isso que está no meu banco?</p>

<h2>Planejando uma fabricação para um build</h2>
<p>O ciclo prático: gere seu build, abra os itens que o otimizador escolheu e veja as receitas. Se uma peça é fabricável, os ingredientes e as fontes de drop dizem se fabricar vence comprar no seu servidor. Deixe as páginas de recursos abertas enquanto farma: as taxas são por monstro, então você escolhe o alvo que realmente compensa.</p>

<p><em>Faltando um ingrediente agora? <a href="/encyclopedia/">Procure na enciclopédia</a> e veja quem dropa.</em></p>
''',
            },
            'de': {
                'title': 'Handwerk und Berufe in Dofus, Version für Version',
                'desc': "Woher ein Rezept kommt, welcher Beruf es herstellt und wo die Zutaten droppen: So planst du ein Handwerk mit der Enzyklopädie, in jeder Dofus-Version.",
                'lead': "Handwerk wirkt simpel, bis im dümmsten Moment eine Zutat fehlt. So planst du ein Handwerk von der Item-Seite bis zu den Monstern, die du wirklich jagen wirst.",
                'body': '''
<h2>Beim Item anfangen, nicht beim Rezept</h2>
<p>Öffne ein beliebiges herstellbares Item in der <a href="/encyclopedia/">Enzyklopädie</a>: Das Rezept steht direkt auf seiner Seite, mit dem Beruf, der es herstellt, und, wo das Spiel eines definiert, dem verlangten Level. Rezepte spezieller Werkbänke, die kein Spielerberuf lernen kann, zeigen schlicht keine Berufszeile: Das sind die Spieldaten selbst, keine Lücke.</p>

<h2>Jede Zutat ist einen Klick entfernt</h2>
<p>Jede Zutat eines Rezepts führt zu ihrer eigenen Ressourcen-Seite: wofür sie sonst noch gebraucht wird und welche Monster sie mit welchen Raten fallen lassen. Genau das macht aus einer Einkaufsliste einen Jagdplan: Droppt die Ressource bei einem farmbaren Monster, entscheidest du mit echten Zahlen, ob du kaufst oder jagst.</p>

<h2>Berufe unterscheiden sich je nach Version</h2>
<p>Der Beruf hinter einem Rezept erzählt nicht überall dieselbe Geschichte. Das moderne Dofus hat die alten Schmiedeberufe zusammengelegt, ein Schwertrezept gehört also zum vereinten Schmied. Dofus Retro (1.29) lebt noch vor dieser Fusion: Die Enzyklopädie zeigt dort die zeitgenössischen Berufe wie Schwertschmied, und Rezepte tragen kein Mindestlevel, weil die 1.29-Daten keines definieren. Dofus Touch hat seinen eigenen Berufssatz dazwischen. Das Tool liest die Spieldateien jeder Version: Was du siehst, entspricht dem, was deine Version wirklich spielt.</p>

<h2>Auch Ressourcen sind durchsuchbar</h2>
<p>Die Enzyklopädie-Suche endet nicht beim Equipment: Tippe einen Ressourcennamen und du landest direkt auf ihrer Seite, in jeder der fünf Sprachen der Seite, Akzente optional. Von dort beantwortet die Liste „Wird gebraucht für" die umgekehrte Frage: Lohnt es sich, das Zeug in meiner Bank zu behalten?</p>

<h2>Ein Handwerk für ein Build planen</h2>
<p>Der praktische Ablauf: Erzeuge dein Build, öffne die Items, die der Optimierer gewählt hat, und prüfe ihre Rezepte. Ist ein Teil herstellbar, sagen dir die Zutaten und ihre Drop-Quellen, ob Herstellen auf deinem Server das Kaufen schlägt. Lass die Ressourcen-Seiten beim Farmen offen: Die Raten gelten pro Monster, du wählst also das Ziel, das sich wirklich lohnt.</p>

<p><em>Fehlt dir gerade eine Zutat? <a href="/encyclopedia/">Such sie in der Enzyklopädie</a> und sieh, wer sie droppt.</em></p>
''',
            },
        },
    },
    # ------------------------------------------------------------------ #
    'choosing-your-class': {
        'published': '2026-07-10',
        'i18n': {
            'en': {
                'title': 'Choosing your class in Dofus, version by version',
                'desc': "Iop or Cra, Retro or Touch: why the best class depends on the Dofus version you play, and how to audition a class with an optimized build first.",
                'lead': "Most class guides open with a tier list. This one opens with a warning: the best class depends on which Dofus you play, and the same name rarely plays the same way twice.",
                'body': '''
<h2>Pick a role, not a rank</h2>
<p>Tier lists age badly; roles do not. Decide what you want to be doing turn after turn: hitting from range (Cra), bursting in melee (Iop), healing and shielding (Eniripsa), locking the map down (Feca), trading your own life for damage (Sacrier), or playing dirty with traps and invisibility (Sram). You will spend hundreds of hours in that role, so start from what you enjoy, then check how your version treats it.</p>

<h2>The same class is not the same game</h2>
<p>Kits, spells and balance differ across <a href="/guides/versions-explained/">Dofus versions</a>. Dofus Retro (1.29) is the extreme case: era gear is rigid, vitality and wisdom carry enormous weight, and the classic Sacrier is played as a nearly unkillable vitality sponge rather than a damage dealer. Dofus Touch froze its own branch of the game and balances it separately, so some classes shine there on paths that no longer exist elsewhere. Dofus 3 rebalances regularly, which keeps the modern meta moving. If a friend swears by a class, ask which version they play before copying them.</p>

<h2>The element is half the choice</h2>
<p>Inside one class, the real fork is the element path: a fire build and an air build of the same class gear completely differently and often play differently too. Whether to stay mono-element or split is its own topic, covered in <a href="/guides/mono-vs-multi-element/">mono vs multi element</a>. When in doubt, pick the path your version's gear actually supports at your level: that is usually the constraint that decides.</p>

<h2>Let the optimizer absorb the decision</h2>
<p>This is where the tool does the heavy lifting: when you <a href="/setup/">create a project</a>, the Fashionista weights stats for your class, your element and your exact game version, because a stat that wins fights in one version can be dead weight in another. Style presets (glass cannon, tanky, balanced) tilt those weights toward how you want to play, and <a href="/guides/tuning-your-weights/">you can retune everything</a> once you know your own priorities.</p>

<h2>Audition your shortlist</h2>
<p>Builds are free and take a minute. Shortlist two or three classes, generate a build for each at the level you actually play, and <a href="/guides/comparing-builds/">compare the results side by side</a>. Seeing what each class realistically wears and reaches at your level answers the question better than any ranking written for someone else's version.</p>

<p><em>Undecided? <a href="/setup/">Start a project</a> for each candidate and let the sets argue for them.</em></p>
''',
            },
            'fr': {
                'title': 'Choisir sa classe sur Dofus, version par version',
                'desc': "Iop ou Crâ, Retro ou Touch : la meilleure classe dépend de la version de Dofus que vous jouez. Comment auditionner une classe avec un build optimisé.",
                'lead': "La plupart des guides de classes commencent par une tier list. Celui-ci commence par un avertissement : la meilleure classe dépend du Dofus que vous jouez, et le même nom se joue rarement deux fois pareil.",
                'body': '''
<h2>Choisissez un rôle, pas un rang</h2>
<p>Les tier lists vieillissent mal ; les rôles, non. Décidez ce que vous voulez faire tour après tour : frapper à distance (Crâ), exploser au corps à corps (Iop), soigner et protéger (Eniripsa), verrouiller la carte (Feca), échanger votre vie contre des dégâts (Sacrieur), ou jouer sale avec pièges et invisibilité (Sram). Vous passerez des centaines d'heures dans ce rôle : partez de ce qui vous amuse, puis regardez comment votre version le traite.</p>

<h2>La même classe n'est pas le même jeu</h2>
<p>Kits, sorts et équilibrage changent selon les <a href="/guides/versions-explained/">versions de Dofus</a>. Dofus Retro (1.29) est le cas extrême : l'équipement d'époque est rigide, la vitalité et la sagesse pèsent énormément, et le Sacrieur classique s'y joue en éponge de vitalité quasi intuable plutôt qu'en attaquant. Dofus Touch a gelé sa propre branche du jeu et l'équilibre séparément : certaines classes y brillent sur des voies qui n'existent plus ailleurs. Dofus 3 rééquilibre régulièrement, ce qui fait bouger la méta moderne. Si un ami ne jure que par une classe, demandez-lui d'abord sa version avant de le copier.</p>

<h2>L'élément est la moitié du choix</h2>
<p>Au sein d'une classe, la vraie bifurcation est la voie élémentaire : un build feu et un build air de la même classe s'équipent tout autrement et se jouent souvent différemment. Rester mono-élément ou se répartir est un sujet à part entière, traité dans <a href="/guides/mono-vs-multi-element/">mono ou multi élément</a>. Dans le doute, prenez la voie que l'équipement de votre version soutient vraiment à votre niveau : c'est presque toujours la contrainte qui tranche.</p>

<h2>Laissez l'optimiseur absorber la décision</h2>
<p>C'est là que l'outil fait le gros du travail : quand vous <a href="/setup/">créez un projet</a>, le Fashionista pondère les stats pour votre classe, votre élément et votre version exacte du jeu, parce qu'une stat qui gagne des combats dans une version peut être du poids mort dans une autre. Les styles prédéfinis (glass cannon, tanky, équilibré) inclinent ces poids vers votre façon de jouer, et <a href="/guides/tuning-your-weights/">tout se réajuste</a> quand vous connaissez vos priorités.</p>

<h2>Auditionnez votre short-list</h2>
<p>Les builds sont gratuits et prennent une minute. Retenez deux ou trois classes, générez un build pour chacune au niveau que vous jouez vraiment, et <a href="/guides/comparing-builds/">comparez les résultats côte à côte</a>. Voir ce que chaque classe porte et atteint réellement à votre niveau répond mieux à la question que n'importe quel classement écrit pour la version de quelqu'un d'autre.</p>

<p><em>Indécis ? <a href="/setup/">Créez un projet</a> par candidate et laissez les panoplies plaider.</em></p>
''',
            },
            'es': {
                'title': 'Elegir tu clase en Dofus, versión por versión',
                'desc': "Yopuka u Ocra, Retro o Touch: por qué la mejor clase depende de la versión de Dofus que juegas, y cómo probar una clase con un build optimizado antes.",
                'lead': "La mayoría de las guías de clases empiezan con una tier list. Esta empieza con una advertencia: la mejor clase depende de qué Dofus juegas, y el mismo nombre rara vez se juega igual dos veces.",
                'body': '''
<h2>Elige un rol, no un puesto</h2>
<p>Las tier lists envejecen mal; los roles, no. Decide qué quieres hacer turno tras turno: golpear a distancia (Ocra), reventar en cuerpo a cuerpo (Yopuka), curar y proteger (Aniripsa), bloquear el mapa (Feca), cambiar tu propia vida por daño (Sacrógrito) o jugar sucio con trampas e invisibilidad (Sram). Vas a pasar cientos de horas en ese rol: parte de lo que te divierte y luego mira cómo lo trata tu versión.</p>

<h2>La misma clase no es el mismo juego</h2>
<p>Kits, hechizos y equilibrio cambian según la <a href="/guides/versions-explained/">versión de Dofus</a>. Dofus Retro (1.29) es el caso extremo: el equipo de la época es rígido, la vitalidad y la sabiduría pesan muchísimo, y el Sacrógrito clásico se juega como una esponja de vitalidad casi inmatable, no como atacante. Dofus Touch congeló su propia rama del juego y la equilibra por separado: algunas clases brillan allí por caminos que ya no existen en otras versiones. Dofus 3 reequilibra con regularidad, así que la meta moderna no deja de moverse. Si un amigo jura por una clase, pregúntale primero qué versión juega antes de copiarle.</p>

<h2>El elemento es la mitad de la elección</h2>
<p>Dentro de una clase, la bifurcación real es la vía elemental: un build de fuego y uno de aire de la misma clase se equipan de forma totalmente distinta y a menudo también se juegan distinto. Quedarse mono elemento o repartirse es un tema aparte, tratado en <a href="/guides/mono-vs-multi-element/">mono o multi elemento</a>. Ante la duda, elige la vía que el equipo de tu versión realmente sostiene a tu nivel: esa suele ser la restricción que decide.</p>

<h2>Deja que el optimizador absorba la decisión</h2>
<p>Aquí es donde la herramienta hace el trabajo pesado: cuando <a href="/setup/">creas un proyecto</a>, el Fashionista pondera las características para tu clase, tu elemento y tu versión exacta del juego, porque una característica que gana combates en una versión puede ser peso muerto en otra. Los estilos predefinidos (glass cannon, tanque, equilibrado) inclinan esos pesos hacia tu forma de jugar, y <a href="/guides/tuning-your-weights/">todo se puede reajustar</a> cuando conozcas tus prioridades.</p>

<h2>Haz una audición a tu lista corta</h2>
<p>Los builds son gratis y toman un minuto. Preselecciona dos o tres clases, genera un build para cada una al nivel que realmente juegas y <a href="/guides/comparing-builds/">compara los resultados lado a lado</a>. Ver lo que cada clase lleva y alcanza de verdad a tu nivel responde mejor la pregunta que cualquier ranking escrito para la versión de otro.</p>

<p><em>¿Indeciso? <a href="/setup/">Crea un proyecto</a> por candidata y deja que los sets aboguen por ellas.</em></p>
''',
            },
            'pt': {
                'title': 'Escolhendo sua classe no Dofus, versão por versão',
                'desc': "Iop ou Cra, Retro ou Touch: por que a melhor classe depende da versão de Dofus que você joga, e como testar uma classe com um build otimizado antes.",
                'lead': "A maioria dos guias de classe abre com uma tier list. Este abre com um aviso: a melhor classe depende de qual Dofus você joga, e o mesmo nome raramente se joga igual duas vezes.",
                'body': '''
<h2>Escolha um papel, não uma posição</h2>
<p>Tier lists envelhecem mal; papéis, não. Decida o que você quer fazer turno após turno: atacar de longe (Cra), explodir no corpo a corpo (Iop), curar e proteger (Eniripsa), travar o mapa (Feca), trocar a própria vida por dano (Sacrier) ou jogar sujo com armadilhas e invisibilidade (Sram). Você vai passar centenas de horas nesse papel: parta do que te diverte e depois veja como a sua versão o trata.</p>

<h2>A mesma classe não é o mesmo jogo</h2>
<p>Kits, feitiços e balanceamento mudam conforme a <a href="/guides/versions-explained/">versão de Dofus</a>. Dofus Retro (1.29) é o caso extremo: o equipamento da época é rígido, vitalidade e sabedoria pesam muito, e o Sacrier clássico se joga como uma esponja de vitalidade quase imortal, não como atacante. Dofus Touch congelou o próprio ramo do jogo e o balanceia em separado: algumas classes brilham lá por caminhos que já não existem em outras versões. Dofus 3 rebalanceia com frequência, então a meta moderna segue mudando. Se um amigo jura por uma classe, pergunte primeiro qual versão ele joga antes de copiar.</p>

<h2>O elemento é metade da escolha</h2>
<p>Dentro de uma classe, a bifurcação real é a via elemental: um build de fogo e um de ar da mesma classe se equipam de forma totalmente diferente e muitas vezes também se jogam diferente. Ficar mono elemento ou dividir é assunto próprio, tratado em <a href="/guides/mono-vs-multi-element/">mono ou multi elemento</a>. Na dúvida, escolha a via que o equipamento da sua versão realmente sustenta no seu nível: essa costuma ser a restrição que decide.</p>

<h2>Deixe o otimizador absorver a decisão</h2>
<p>É aqui que a ferramenta faz o trabalho pesado: quando você <a href="/setup/">cria um projeto</a>, o Fashionista pondera os atributos para a sua classe, o seu elemento e a sua versão exata do jogo, porque um atributo que ganha lutas numa versão pode ser peso morto em outra. Os estilos predefinidos (glass cannon, tanque, equilibrado) inclinam esses pesos para o seu jeito de jogar, e <a href="/guides/tuning-your-weights/">tudo pode ser reajustado</a> quando você conhecer as suas prioridades.</p>

<h2>Faça um teste com sua lista curta</h2>
<p>Builds são grátis e levam um minuto. Selecione duas ou três classes, gere um build para cada uma no nível que você realmente joga e <a href="/guides/comparing-builds/">compare os resultados lado a lado</a>. Ver o que cada classe realmente veste e alcança no seu nível responde melhor à pergunta do que qualquer ranking escrito para a versão de outra pessoa.</p>

<p><em>Indeciso? <a href="/setup/">Crie um projeto</a> por candidata e deixe os sets defenderem cada uma.</em></p>
''',
            },
            'de': {
                'title': 'Die Klassenwahl in Dofus, Version für Version',
                'desc': "Iop oder Crâ, Retro oder Touch: warum die beste Klasse von deiner Dofus-Version abhängt, und wie du eine Klasse erst mit einem optimierten Build testest.",
                'lead': "Die meisten Klassenguides beginnen mit einer Tierlist. Dieser beginnt mit einer Warnung: Die beste Klasse hängt davon ab, welches Dofus du spielst, und derselbe Name spielt sich selten zweimal gleich.",
                'body': '''
<h2>Wähle eine Rolle, keinen Rang</h2>
<p>Tierlists altern schlecht; Rollen nicht. Entscheide, was du Zug um Zug tun willst: aus der Distanz treffen (Crâ), im Nahkampf explodieren (Iop), heilen und schützen (Eniripsa), die Karte verriegeln (Féca), das eigene Leben gegen Schaden tauschen (Sacrieur) oder mit Fallen und Unsichtbarkeit tricksen (Sram). In dieser Rolle wirst du Hunderte Stunden verbringen: Geh von dem aus, was dir Spass macht, und schau dann, wie deine Version sie behandelt.</p>

<h2>Dieselbe Klasse ist nicht dasselbe Spiel</h2>
<p>Ausrüstung, Zauber und Balancing unterscheiden sich je nach <a href="/guides/versions-explained/">Dofus-Version</a>. Dofus Retro (1.29) ist der Extremfall: Die Ausrüstung der Ära ist starr, Vitalität und Weisheit wiegen enorm, und der klassische Sacrieur wird als kaum totzukriegender Vitalitätsschwamm gespielt, nicht als Schadensklasse. Dofus Touch hat seinen eigenen Zweig des Spiels eingefroren und balanciert ihn separat: Manche Klassen glänzen dort auf Wegen, die es anderswo nicht mehr gibt. Dofus 3 balanciert regelmässig nach, die moderne Meta bleibt also in Bewegung. Wenn ein Freund auf eine Klasse schwört, frag zuerst, welche Version er spielt, bevor du ihn kopierst.</p>

<h2>Das Element ist die halbe Entscheidung</h2>
<p>Innerhalb einer Klasse ist die echte Weggabelung der Elementarpfad: Ein Feuer-Build und ein Luft-Build derselben Klasse rüsten sich völlig anders aus und spielen sich oft auch anders. Ob mono oder verteilt, ist ein eigenes Thema und wird in <a href="/guides/mono-vs-multi-element/">Mono oder Multi Element</a> behandelt. Im Zweifel nimm den Pfad, den die Ausrüstung deiner Version auf deiner Stufe wirklich trägt: Das ist meist die Einschränkung, die entscheidet.</p>

<h2>Lass den Optimierer die Entscheidung abfedern</h2>
<p>Hier übernimmt das Werkzeug die schwere Arbeit: Wenn du <a href="/setup/">ein Projekt erstellst</a>, gewichtet der Fashionista die Werte für deine Klasse, dein Element und deine exakte Spielversion, denn ein Wert, der in einer Version Kämpfe gewinnt, kann in einer anderen totes Gewicht sein. Stil-Presets (Glaskanone, tanky, ausgewogen) neigen diese Gewichte zu deiner Spielweise, und <a href="/guides/tuning-your-weights/">alles lässt sich nachjustieren</a>, sobald du deine Prioritäten kennst.</p>

<h2>Lass deine Favoriten vorspielen</h2>
<p>Builds sind kostenlos und dauern eine Minute. Nimm zwei oder drei Klassen in die engere Wahl, erzeuge für jede einen Build auf der Stufe, die du wirklich spielst, und <a href="/guides/comparing-builds/">vergleiche die Ergebnisse nebeneinander</a>. Zu sehen, was jede Klasse auf deiner Stufe realistisch trägt und erreicht, beantwortet die Frage besser als jedes Ranking, das für die Version von jemand anderem geschrieben wurde.</p>

<p><em>Unentschlossen? <a href="/setup/">Erstell pro Kandidatin ein Projekt</a> und lass die Sets für sie sprechen.</em></p>
''',
            },
        },
    },
    # ------------------------------------------------------------------ #
    'beginner-mistakes': {
        'published': '2026-07-22',
        'i18n': {
            'en': {
                'title': 'Six beginner mistakes that quietly ruin your builds',
                'desc': "Most bad builds die one of the same six deaths: stat greed, ignored AP, dream items, wasted vitality... How to spot each trap and dodge it with the optimizer.",
                'lead': "Most bad builds don't fail in some exotic way. They die one of the same six deaths, and every one of them is avoidable before it costs you a single kama.",
                'body': '''
<h2>1. Chasing the biggest totals</h2>
<p>A set with +900 total stats in things you don't use loses to one with +600 in exactly the right places. The optimizer maximizes whatever you tell it to value, so the classic beginner move is to leave every slider high and get back a build that is impressively mediocre at everything. Decide what actually wins your fights and say so. That is the whole craft of <a href="/guides/tuning-your-weights/">setting your weights</a>.</p>

<h2>2. Optimizing damage before AP and MP</h2>
<p>Damage feels like the goal, but action points and movement points decide what you can even do in a turn. An extra spell cast beats a slightly bigger hit almost every time. Set your AP and MP targets first, as hard requirements rather than wishes, then let the tool squeeze the most damage out of what's left. If you're not sure what each stat is even for, the <a href="/guides/stats-explained/">stats guide</a> ranks them honestly.</p>

<h2>3. Building around items you'll never afford</h2>
<p>The mathematically perfect set is worthless if it costs three years of farming. When the suggestion includes something outside your budget, don't screenshot it and sigh: <strong>forbid</strong> the item and tailor again, and the optimizer will find the best set that exists without it. A build you can actually equip this week beats a museum piece. The full workflow is in <a href="/guides/understanding-your-solution/">understanding your solution</a>.</p>

<h2>4. Overpaying for vitality</h2>
<p>Raw HP is the most reassuring number on the sheet, which is exactly why it gets overvalued. Vitality doesn't remove your enemies, it only lets you lose more slowly, unless soaking hits is genuinely your job. Weight it for the content you play: higher when enemies focus you and nobody heals you, lower when you sit at range or a healer has your back. If your damage output is anemic, no amount of HP fixes that.</p>

<h2>5. Splashing every element at once</h2>
<p>Items can rarely be the best in four elements at the same time, so every element you add dilutes the others. Mono-element builds hit harder in their lane; multi-element buys flexibility at a real price and usually needs higher-end gear to work. Pick deliberately, not by accident: the trade-offs are laid out in <a href="/guides/mono-vs-multi-element/">mono versus multi element</a>.</p>

<h2>6. Copying a build from another version</h2>
<p>Dofus 3, the beta, Dofus 2, Retro and Touch are five different games. An item that is core in one may not exist in another, or exists with different stats, and the rules around scrolls and characteristics differ too. A build guide written for someone else's version is a trap in yours. Optimize in the version you actually play, and if you're unsure what runs where, see <a href="/guides/versions-explained/">versions explained</a>.</p>

<h2>The setting everyone forgets: your scrolls</h2>
<p>A new project assumes your characteristics are fully scrolled, 100 in each. If your character isn't, the tool is optimizing a slightly richer character than yours: totals, item conditions you meet and the best way to distribute your points all shift. Open your project's characteristics page and set your real scroll state, it takes ten seconds and every suggestion after that fits your actual character.</p>

<h2>What you do not have to worry about</h2>
<p>The game's fussy legality rules are already enforced for you: item conditions are checked before an item is ever suggested, set bonuses are counted properly, and version caps like trophy limits are respected. Your job is taste and honesty about how you play. The arithmetic is covered. If you still want to read an item card like a pro, start with <a href="/guides/reading-an-item/">reading an item</a>.</p>

<p><em>Recognized yourself in one of these? <a href="/quickstart/">Rebuild in two minutes</a> and see what changes.</em></p>
''',
            },
            'fr': {
                'title': 'Six pièges de débutant qui plombent tes stuffs en douce',
                'desc': "Les mauvais stuffs meurent des six mêmes morts : gloutonnerie de stats, PA ignorés, items de rêve, vita surpayée... Comment repérer chaque piège et l'éviter.",
                'lead': "La plupart des mauvais stuffs n'échouent pas de façon exotique. Ils meurent d'une des six mêmes morts, et chacune s'évite avant de te coûter le moindre kama.",
                'body': '''
<h2>1. Courir après les plus gros totaux</h2>
<p>Un set à +900 de stats totales dans des trucs que tu n'utilises pas perd contre un set à +600 pile aux bons endroits. L'optimiseur maximise ce que tu lui dis de valoriser : le réflexe classique du débutant, c'est de laisser tous les curseurs à fond et de récupérer un stuff remarquablement moyen partout. Décide ce qui gagne vraiment tes combats et dis-le. C'est tout l'art de <a href="/guides/tuning-your-weights/">régler tes poids</a>.</p>

<h2>2. Optimiser les dégâts avant les PA et les PM</h2>
<p>Les dégâts ont l'air d'être le but, mais ce sont les points d'action et de mouvement qui décident de ce que tu peux faire dans un tour. Un sort de plus par tour bat presque toujours un coup un peu plus gros. Fixe d'abord tes objectifs de PA et de PM, comme des exigences dures et pas des souhaits, puis laisse l'outil presser un maximum de dégâts de ce qui reste. Et si tu ne sais pas à quoi sert chaque carac, le <a href="/guides/stats-explained/">guide des stats</a> les classe honnêtement.</p>

<h2>3. Construire autour d'items que tu n'auras jamais</h2>
<p>Le set mathématiquement parfait ne vaut rien s'il coûte trois ans de farm. Quand la proposition contient un truc hors budget, ne fais pas une capture d'écran en soupirant : <strong>interdis</strong> l'item et retaille, l'optimiseur trouvera le meilleur set qui existe sans lui. Un stuff que tu peux vraiment équiper cette semaine bat une pièce de musée. Tout le déroulé est dans <a href="/guides/understanding-your-solution/">comprendre ta solution</a>.</p>

<h2>4. Surpayer la vitalité</h2>
<p>Les PV bruts sont le chiffre le plus rassurant de la fiche, et c'est exactement pour ça qu'on les surévalue. La vita ne fait pas disparaître tes ennemis, elle te fait juste perdre plus lentement, sauf si encaisser est vraiment ton rôle. Pondère-la selon ton contenu : plus haut quand on te focus et que personne ne te soigne, plus bas quand tu joues à distance ou qu'un soigneur te couvre. Si tes dégâts sont anémiques, aucun total de PV ne rattrapera ça.</p>

<h2>5. Taper dans tous les éléments à la fois</h2>
<p>Un item est rarement le meilleur dans quatre éléments en même temps : chaque élément que tu ajoutes dilue les autres. Le mono-élément tape plus fort dans son couloir ; le multi achète de la souplesse à un vrai prix et demande en général du matos plus haut de gamme pour fonctionner. Choisis exprès, pas par accident : les compromis sont posés dans <a href="/guides/mono-vs-multi-element/">mono ou multi élément</a>.</p>

<h2>6. Copier un build d'une autre version</h2>
<p>Dofus 3, la bêta, Dofus 2, Retro et Touch sont cinq jeux différents. Un item central dans l'un peut ne pas exister dans l'autre, ou exister avec d'autres stats, et les règles de parchotage et de caracs changent aussi. Un guide de build écrit pour la version de quelqu'un d'autre est un piège dans la tienne. Optimise dans la version que tu joues vraiment, et si tu ne sais plus qui joue quoi, va voir <a href="/guides/versions-explained/">les versions expliquées</a>.</p>

<h2>Le réglage que tout le monde oublie : tes parchemins</h2>
<p>Un nouveau projet suppose tes caracs parchotées à fond, 100 partout. Si ton perso ne l'est pas, l'outil optimise un personnage un peu plus riche que le tien : les totaux, les conditions d'items que tu remplis et la meilleure répartition de tes points bougent tous. Ouvre la page caractéristiques de ton projet et mets ton vrai parchotage, ça prend dix secondes et toutes les propositions suivantes collent à ton vrai perso.</p>

<h2>Ce dont tu n'as pas à te soucier</h2>
<p>Les règles tatillonnes du jeu sont déjà appliquées pour toi : les conditions d'items sont vérifiées avant même qu'un item soit proposé, les bonus de panoplie sont comptés proprement, et les plafonds de version comme les limites de trophées sont respectés. Ton boulot, c'est le goût et l'honnêteté sur ta façon de jouer. L'arithmétique est couverte. Et si tu veux quand même lire une fiche d'item comme un pro, commence par <a href="/guides/reading-an-item/">lire un item</a>.</p>

<p><em>Tu t'es reconnu dans un de ces pièges ? <a href="/quickstart/">Refais ton build en deux minutes</a> et regarde ce qui change.</em></p>
''',
            },
            'es': {
                'title': 'Seis errores de novato que arruinan tus builds sin avisar',
                'desc': "Los builds malos mueren de las mismas seis muertes: avaricia de stats, PA ignorados, ítems soñados, vitalidad sobrepagada... Cómo ver y esquivar cada trampa.",
                'lead': "La mayoría de los builds malos no fallan de forma exótica. Mueren de una de las mismas seis muertes, y todas se pueden evitar antes de que te cuesten una sola kama.",
                'body': '''
<h2>1. Perseguir los totales más grandes</h2>
<p>Un set con +900 stats totales en cosas que no usas pierde contra uno con +600 justo donde importa. El optimizador maximiza lo que tú le digas que valore: el clásico movimiento de novato es dejar todos los deslizadores altos y recibir un build impresionantemente mediocre en todo. Decide qué gana de verdad tus combates y dilo. Ese es todo el arte de <a href="/guides/tuning-your-weights/">ajustar tus pesos</a>.</p>

<h2>2. Optimizar el daño antes que los PA y los PM</h2>
<p>El daño parece la meta, pero los puntos de acción y de movimiento deciden qué puedes hacer siquiera en un turno. Un hechizo más casi siempre gana a un golpe un poco más grande. Fija primero tus objetivos de PA y PM, como requisitos duros y no como deseos, y deja que la herramienta exprima el máximo daño de lo que quede. Y si no tienes claro para qué sirve cada stat, la <a href="/guides/stats-explained/">guía de características</a> las ordena con honestidad.</p>

<h2>3. Construir alrededor de ítems que nunca tendrás</h2>
<p>El set matemáticamente perfecto no vale nada si cuesta tres años de farmeo. Cuando la sugerencia incluya algo fuera de tu presupuesto, no hagas una captura y suspires: <strong>prohíbe</strong> el ítem y vuelve a optimizar, y el optimizador encontrará el mejor set que exista sin él. Un build que puedas equipar esta semana gana a una pieza de museo. El flujo completo está en <a href="/guides/understanding-your-solution/">entender tu solución</a>.</p>

<h2>4. Pagar de más por la vitalidad</h2>
<p>Los PdV brutos son el número más tranquilizador de la ficha, y justo por eso se sobrevaloran. La vitalidad no elimina a tus enemigos, solo te deja perder más despacio, salvo que aguantar golpes sea de verdad tu papel. Pondérala según tu contenido: más alta cuando te enfocan y nadie te cura, más baja cuando juegas a distancia o un sanador te cubre. Si tu daño es anémico, ninguna cantidad de PdV lo arregla.</p>

<h2>5. Repartirte entre todos los elementos a la vez</h2>
<p>Un ítem rara vez es el mejor en cuatro elementos al mismo tiempo: cada elemento que añades diluye los demás. El mono elemento pega más fuerte en su carril; el multi compra flexibilidad a un precio real y suele exigir equipo de gama más alta para funcionar. Elige a propósito, no por accidente: los pros y contras están en <a href="/guides/mono-vs-multi-element/">mono contra multi elemento</a>.</p>

<h2>6. Copiar un build de otra versión</h2>
<p>Dofus 3, la beta, Dofus 2, Retro y Touch son cinco juegos distintos. Un ítem central en uno puede no existir en otro, o existir con otras stats, y las reglas de pergaminos y características también cambian. Una guía de build escrita para la versión de otro es una trampa en la tuya. Optimiza en la versión que juegas de verdad, y si no sabes qué corre dónde, mira <a href="/guides/versions-explained/">las versiones explicadas</a>.</p>

<h2>El ajuste que todo el mundo olvida: tus pergaminos</h2>
<p>Un proyecto nuevo asume tus características pergamineadas al máximo, 100 en cada una. Si tu personaje no lo está, la herramienta optimiza un personaje algo más rico que el tuyo: los totales, las condiciones de ítems que cumples y la mejor forma de repartir tus puntos se mueven. Abre la página de características de tu proyecto y pon tu estado real de pergaminos, tarda diez segundos y todas las sugerencias siguientes encajarán con tu personaje real.</p>

<h2>De qué no tienes que preocuparte</h2>
<p>Las reglas quisquillosas del juego ya se aplican por ti: las condiciones de los ítems se comprueban antes de sugerirte nada, los bonus de panoplia se cuentan bien y los topes por versión, como los límites de trofeos, se respetan. Tu trabajo es el criterio y la honestidad sobre cómo juegas. La aritmética está cubierta. Y si aun así quieres leer una ficha de ítem como un pro, empieza por <a href="/guides/reading-an-item/">leer un ítem</a>.</p>

<p><em>¿Te has reconocido en alguna de estas trampas? <a href="/quickstart/">Rehaz tu build en dos minutos</a> y mira qué cambia.</em></p>
''',
            },
            'pt': {
                'title': 'Seis erros de iniciante que estragam seus builds em silêncio',
                'desc': "Builds ruins morrem das mesmas seis mortes: ganância de stats, PA ignorados, itens dos sonhos, vitalidade cara demais... Como ver cada armadilha e desviar.",
                'lead': "A maioria dos builds ruins não falha de um jeito exótico. Eles morrem de uma das mesmas seis mortes, e todas dá para evitar antes que custem uma única kama.",
                'body': '''
<h2>1. Correr atrás dos maiores totais</h2>
<p>Um set com +900 stats totais em coisas que você não usa perde para um com +600 exatamente nos lugares certos. O otimizador maximiza o que você mandar ele valorizar: o clássico movimento de iniciante é deixar todos os controles no alto e receber um build impressionantemente mediano em tudo. Decida o que ganha de verdade as suas lutas e diga isso. Essa é toda a arte de <a href="/guides/tuning-your-weights/">ajustar seus pesos</a>.</p>

<h2>2. Otimizar o dano antes dos PA e PM</h2>
<p>O dano parece ser a meta, mas são os pontos de ação e de movimento que decidem o que você consegue sequer fazer num turno. Um feitiço a mais quase sempre vale mais que um golpe um pouco maior. Defina primeiro suas metas de PA e PM, como exigências duras e não desejos, e deixe a ferramenta espremer o máximo de dano do que sobrar. E se você não sabe para que serve cada stat, o <a href="/guides/stats-explained/">guia de características</a> as classifica com honestidade.</p>

<h2>3. Construir em volta de itens que você nunca vai ter</h2>
<p>O set matematicamente perfeito não vale nada se custa três anos de farm. Quando a sugestão incluir algo fora do seu orçamento, não tire print suspirando: <strong>proíba</strong> o item e otimize de novo, e o otimizador vai achar o melhor set que existe sem ele. Um build que você consegue equipar esta semana ganha de uma peça de museu. O fluxo completo está em <a href="/guides/understanding-your-solution/">entendendo sua solução</a>.</p>

<h2>4. Pagar caro demais pela vitalidade</h2>
<p>PV bruto é o número mais reconfortante da ficha, e é exatamente por isso que ele é supervalorizado. Vitalidade não elimina seus inimigos, só deixa você perder mais devagar, a menos que aguentar pancada seja de fato o seu papel. Dê a ela um peso honesto para o seu conteúdo: mais alto quando focam você e ninguém cura, mais baixo quando você joga de longe ou um curandeiro te cobre. Se o seu dano é anêmico, nenhuma quantidade de PV resolve.</p>

<h2>5. Espalhar em todos os elementos ao mesmo tempo</h2>
<p>Um item raramente é o melhor em quatro elementos ao mesmo tempo: cada elemento que você adiciona dilui os outros. Mono elemento bate mais forte na própria pista; multi compra flexibilidade por um preço real e costuma exigir equipamento de nível mais alto para funcionar. Escolha de propósito, não por acidente: os prós e contras estão em <a href="/guides/mono-vs-multi-element/">mono contra multi elemento</a>.</p>

<h2>6. Copiar um build de outra versão</h2>
<p>Dofus 3, o beta, Dofus 2, Retro e Touch são cinco jogos diferentes. Um item central em um pode nem existir no outro, ou existir com outras stats, e as regras de pergaminhos e características também mudam. Um guia de build escrito para a versão de outra pessoa é uma armadilha na sua. Otimize na versão que você joga de verdade, e se não souber o que roda onde, veja <a href="/guides/versions-explained/">as versões explicadas</a>.</p>

<h2>O ajuste que todo mundo esquece: seus pergaminhos</h2>
<p>Um projeto novo assume suas características totalmente pergaminhadas, 100 em cada. Se o seu personagem não está, a ferramenta otimiza um personagem um pouco mais rico que o seu: os totais, as condições de itens que você cumpre e a melhor distribuição dos seus pontos mudam. Abra a página de características do seu projeto e coloque seu estado real de pergaminhos, leva dez segundos e todas as sugestões seguintes vão servir no seu personagem de verdade.</p>

<h2>Com o que você não precisa se preocupar</h2>
<p>As regras chatas do jogo já são aplicadas por você: as condições dos itens são verificadas antes de qualquer sugestão, os bônus de panóplia são contados direito e os tetos por versão, como os limites de troféus, são respeitados. O seu trabalho é gosto e honestidade sobre como você joga. A aritmética está coberta. E se ainda quiser ler a ficha de um item como um pro, comece por <a href="/guides/reading-an-item/">lendo um item</a>.</p>

<p><em>Se reconheceu em alguma dessas armadilhas? <a href="/quickstart/">Refaça seu build em dois minutos</a> e veja o que muda.</em></p>
''',
            },
            'de': {
                'title': 'Sechs Anfängerfehler, die dein Build leise ruinieren',
                'desc': "Schlechte Builds sterben einen von sechs immer gleichen Toden: Wertegier, ignorierte AP, Traum-Items, überbezahlte Vitalität... So erkennst du jede Falle.",
                'lead': "Die meisten schlechten Builds scheitern nicht auf exotische Weise. Sie sterben einen von sechs immer gleichen Toden, und jeder davon lässt sich vermeiden, bevor er dich auch nur eine Kama kostet.",
                'body': '''
<h2>1. Den größten Summen hinterherjagen</h2>
<p>Ein Set mit +900 Gesamtwerten in Dingen, die du nicht nutzt, verliert gegen eines mit +600 genau an den richtigen Stellen. Der Optimierer maximiert, was immer du ihm als wertvoll angibst: Der klassische Anfängerzug ist, alle Regler oben zu lassen und ein Build zurückzubekommen, das beeindruckend mittelmäßig in allem ist. Entscheide, was deine Kämpfe wirklich gewinnt, und sag es. Genau das ist die Kunst beim <a href="/guides/tuning-your-weights/">Einstellen deiner Gewichte</a>.</p>

<h2>2. Schaden optimieren, bevor AP und BP stehen</h2>
<p>Schaden fühlt sich wie das Ziel an, aber Aktions- und Bewegungspunkte entscheiden, was du in einer Runde überhaupt tun kannst. Ein zusätzlicher Zauber schlägt fast immer einen etwas größeren Treffer. Setz zuerst deine AP- und BP-Ziele, als harte Anforderungen statt als Wünsche, und lass das Werkzeug dann aus dem Rest den maximalen Schaden herausquetschen. Und wenn du nicht sicher bist, wofür ein Wert überhaupt gut ist: Der <a href="/guides/stats-explained/">Werte-Guide</a> ordnet sie ehrlich ein.</p>

<h2>3. Um Items bauen, die du nie haben wirst</h2>
<p>Das mathematisch perfekte Set ist wertlos, wenn es drei Jahre Farmen kostet. Wenn der Vorschlag etwas außerhalb deines Budgets enthält, mach keinen Screenshot und seufz: <strong>Verbiete</strong> das Item und optimiere neu, und der Optimierer findet das beste Set, das es ohne dieses Item gibt. Ein Build, das du diese Woche wirklich anziehen kannst, schlägt ein Museumsstück. Der komplette Ablauf steht in <a href="/guides/understanding-your-solution/">deine Lösung verstehen</a>.</p>

<h2>4. Zu viel für Vitalität bezahlen</h2>
<p>Rohe LP sind die beruhigendste Zahl auf dem Bogen, und genau deshalb werden sie überbewertet. Vitalität lässt deine Gegner nicht verschwinden, sie lässt dich nur langsamer verlieren, außer Einstecken ist wirklich deine Aufgabe. Gewichte sie ehrlich für deinen Inhalt: höher, wenn du fokussiert wirst und dich niemand heilt, niedriger, wenn du auf Distanz spielst oder ein Heiler hinter dir steht. Wenn dein Schaden blutleer ist, rettet dich keine LP-Menge.</p>

<h2>5. Auf alle Elemente gleichzeitig setzen</h2>
<p>Ein Item ist selten in vier Elementen gleichzeitig das beste: Jedes Element, das du dazunimmst, verwässert die anderen. Mono-Element schlägt härter in seiner Spur; Multi kauft Flexibilität zu einem echten Preis und braucht meist höherwertige Ausrüstung, um zu funktionieren. Wähle absichtlich, nicht aus Versehen: Die Abwägungen stehen in <a href="/guides/mono-vs-multi-element/">Mono gegen Multi</a>.</p>

<h2>6. Ein Build aus einer anderen Version kopieren</h2>
<p>Dofus 3, die Beta, Dofus 2, Retro und Touch sind fünf verschiedene Spiele. Ein Item, das in einer Version zentral ist, existiert in einer anderen vielleicht gar nicht oder mit anderen Werten, und auch die Regeln für Rollen und Charakteristiken unterscheiden sich. Ein Build-Guide für die Version von jemand anderem ist in deiner eine Falle. Optimiere in der Version, die du wirklich spielst, und wenn du nicht weißt, was wo läuft, schau in <a href="/guides/versions-explained/">die Versionen erklärt</a>.</p>

<h2>Die Einstellung, die alle vergessen: deine Rollen</h2>
<p>Ein neues Projekt nimmt an, dass deine Charakteristiken voll gerollt sind, 100 in jeder. Wenn dein Charakter das nicht ist, optimiert das Werkzeug einen etwas reicheren Charakter als deinen: Die Summen, die Item-Bedingungen, die du erfüllst, und die beste Verteilung deiner Punkte verschieben sich alle. Öffne die Charakteristiken-Seite deines Projekts und trag deinen echten Rollen-Stand ein, das dauert zehn Sekunden, und jeder Vorschlag danach passt zu deinem echten Charakter.</p>

<h2>Worum du dich nicht kümmern musst</h2>
<p>Die pingeligen Regeln des Spiels werden schon für dich durchgesetzt: Item-Bedingungen werden geprüft, bevor ein Item überhaupt vorgeschlagen wird, Set-Boni werden richtig gezählt, und Versions-Obergrenzen wie Trophäen-Limits werden eingehalten. Dein Job ist Geschmack und Ehrlichkeit darüber, wie du spielst. Das Rechnen ist abgedeckt. Und wenn du trotzdem eine Item-Karte wie ein Profi lesen willst, fang mit <a href="/guides/reading-an-item/">ein Item lesen</a> an.</p>

<p><em>Dich in einer dieser Fallen wiedererkannt? <a href="/quickstart/">Bau dein Build in zwei Minuten neu</a> und schau, was sich ändert.</em></p>
''',
            },
        },
    },
    # ------------------------------------------------------------------ #
    'scrolls-and-characteristics': {
        'published': '2026-07-22',
        'i18n': {
            'en': {
                'title': 'Scrolls and characteristics: set your base stats right',
                'desc': "Scrolls raise your base stats for good, and the optimizer assumes you are fully scrolled. How scrolling works, per Dofus version, and why it matters.",
                'lead': "Scrolls quietly change every number the optimizer hands you, and a new project assumes you already have all of them. Getting your scroll setup right is a two-minute job that makes every suggestion fit your real character.",
                'body': '''
<h2>What a scroll actually does</h2>
<p>A scroll (parchemin) permanently raises one base characteristic. Read a Strength scroll and you keep that Strength forever, with no points spent, once per character. Because it is free stat, most players eventually scroll their main characteristics all the way to the cap. That is exactly why the optimizer treats a fully scrolled character as the default starting point.</p>

<h2>The optimizer assumes you are fully scrolled</h2>
<p>A new project starts as if your characteristics are scrolled to the maximum. If yours are not, the tool is optimizing a slightly richer character than the one you actually play: your totals, the <a href="/guides/reading-an-item/">item conditions you meet</a>, and the best way to distribute your points all shift. Open your project's characteristics page and set your real scroll level for each stat. It takes ten seconds, and every suggestion after that fits your actual character.</p>

<h2>The version twist: each Dofus version plays by its own rules</h2>
<p>Scrolling is one of the places the five versions genuinely differ, so a habit from one can quietly mislead you in another.</p>
<ul>
<li><strong>Modern Dofus (Dofus 3, the beta and Dofus 2) and Dofus Touch:</strong> scrolled points are tracked separately from the points you invest, so your scrolls never make your invested points more expensive. Modern Dofus adopted this in October 2018; Touch uses the same rule.</li>
<li><strong>Dofus Retro (1.29):</strong> the old rule still applies. Scrolls count as ordinary points on the cost curve, so a character scrolled to 100 in a characteristic already pays the expensive tier for its very first invested point. Scrolling there is a real strategic choice, not a free lunch.</li>
<li><strong>How high you can scroll differs too:</strong> 100 in most versions, 101 in Retro, and up to 150 on Touch since the Dedale update.</li>
</ul>
<p>If you are not sure which rules your version follows, the <a href="/guides/versions-explained/">versions guide</a> lays out what makes each one its own game.</p>

<h2>If you have not scrolled yet</h2>
<p>You can still plan around it. Set your real scroll state, build, and the optimizer works with the character you have today rather than an idealized one. Later, when you scroll more, update the number and tailor again: you will often free up invested points and unlock items you could not wear before. Scrolling your main damage characteristic first is the usual advice, but weight it against the content you play, the same way you would <a href="/guides/stats-explained/">value any other stat</a>.</p>

<p><em>Not sure where your character stands? <a href="/setup/">Open your project</a>, set your scrolls and tailor again to see your real build.</em></p>
''',
            },
            'fr': {
                'title': 'Parchemins et caractéristiques : bien régler tes stats de base',
                'desc': "Les parchemins montent tes stats de base à vie, et l'optimiseur te suppose parchoté à fond. Comment ça marche selon la version de Dofus, et pourquoi ça compte.",
                'lead': "Les parchemins changent en douce chaque chiffre que l'outil te donne, et un nouveau projet suppose que tu les as déjà tous. Régler ton parchotage, c'est deux minutes qui font coller chaque proposition à ton vrai perso.",
                'body': '''
<h2>Ce que fait vraiment un parchemin</h2>
<p>Un parchemin monte définitivement une caractéristique de base. Tu lis un parchemin de Force et tu gardes cette Force à vie, sans dépenser de points, une fois par personnage. Comme c'est de la stat gratuite, la plupart des joueurs finissent par parchoter leurs caracs principales jusqu'au plafond. C'est exactement pour ça que l'optimiseur prend un perso parchoté à fond comme point de départ par défaut.</p>

<h2>L'optimiseur te suppose parchoté à fond</h2>
<p>Un nouveau projet démarre comme si tes caracs étaient parchotées au maximum. Si ce n'est pas le cas, l'outil optimise un perso un peu plus riche que celui que tu joues vraiment : tes totaux, les <a href="/guides/reading-an-item/">conditions d'items que tu remplis</a> et la meilleure répartition de tes points bougent tous. Ouvre la page caractéristiques de ton projet et mets ton vrai niveau de parchotage pour chaque stat. Ça prend dix secondes, et toutes les propositions suivantes collent à ton vrai perso.</p>

<h2>Le piège des versions : chaque Dofus a ses propres règles</h2>
<p>Le parchotage est un des endroits où les cinq versions diffèrent vraiment, donc une habitude prise sur l'une peut t'induire en erreur sur une autre sans que tu t'en rendes compte.</p>
<ul>
<li><strong>Dofus moderne (Dofus 3, la bêta et Dofus 2) et Dofus Touch :</strong> les points de parchotage sont comptés séparément des points que tu investis, donc tes parchemins ne rendent jamais tes points investis plus chers. Le Dofus moderne a adopté cette règle en octobre 2018 ; Touch applique la même.</li>
<li><strong>Dofus Retro (1.29) :</strong> l'ancienne règle tient toujours. Les parchemins comptent comme des points normaux sur la courbe de coût, donc un perso parchoté à 100 dans une carac paie déjà le palier cher pour son tout premier point investi. Là-bas, parchoter est un vrai choix stratégique, pas un cadeau.</li>
<li><strong>Le plafond de parchotage change aussi :</strong> 100 dans la plupart des versions, 101 en Retro, et jusqu'à 150 sur Touch depuis la mise à jour Dédale.</li>
</ul>
<p>Si tu ne sais pas quelles règles suit ta version, le <a href="/guides/versions-explained/">guide des versions</a> détaille ce qui fait de chacune un jeu à part.</p>

<h2>Si tu n'as pas encore parchoté</h2>
<p>Tu peux quand même t'organiser autour. Mets ton vrai parchotage, construis, et l'outil travaille avec le perso que tu as aujourd'hui plutôt qu'un perso idéalisé. Plus tard, quand tu parchotes plus, mets à jour le chiffre et retaille : tu vas souvent libérer des points investis et débloquer des items que tu ne pouvais pas porter. Parchoter d'abord ta carac de dégâts principale, c'est le conseil classique, mais pondère-le selon ton contenu, comme tu le ferais pour <a href="/guides/stats-explained/">n'importe quelle autre stat</a>.</p>

<p><em>Pas sûr d'où en est ton perso ? <a href="/setup/">Ouvre ton projet</a>, mets tes parchemins et retaille pour voir ton vrai build.</em></p>
''',
            },
            'es': {
                'title': 'Pergaminos y características: ajusta bien tus stats de base',
                'desc': "Los pergaminos suben tus stats de base para siempre, y el optimizador te supone pergamineado al máximo. Cómo funciona según la versión y por qué importa.",
                'lead': "Los pergaminos cambian en silencio cada número que te da la herramienta, y un proyecto nuevo asume que ya los tienes todos. Ajustar tu pergamineo es cosa de dos minutos que hace que cada sugerencia encaje con tu personaje real.",
                'body': '''
<h2>Qué hace de verdad un pergamino</h2>
<p>Un pergamino sube de forma permanente una característica de base. Lees un pergamino de Fuerza y conservas esa Fuerza para siempre, sin gastar puntos, una vez por personaje. Como es stat gratis, la mayoría de jugadores acaba pergamineando sus características principales hasta el tope. Por eso el optimizador toma un personaje pergamineado al máximo como punto de partida por defecto.</p>

<h2>El optimizador te supone pergamineado al máximo</h2>
<p>Un proyecto nuevo empieza como si tus características estuvieran pergamineadas al máximo. Si las tuyas no lo están, la herramienta optimiza un personaje algo más rico que el que juegas de verdad: tus totales, las <a href="/guides/reading-an-item/">condiciones de ítems que cumples</a> y la mejor forma de repartir tus puntos se mueven. Abre la página de características de tu proyecto y pon tu nivel real de pergamineo en cada stat. Tarda diez segundos, y todas las sugerencias siguientes encajan con tu personaje real.</p>

<h2>El truco de las versiones: cada Dofus juega con sus propias reglas</h2>
<p>El pergamineo es uno de los sitios donde las cinco versiones difieren de verdad, así que una costumbre de una puede engañarte en otra sin que te des cuenta.</p>
<ul>
<li><strong>Dofus moderno (Dofus 3, la beta y Dofus 2) y Dofus Touch:</strong> los puntos de pergamino se cuentan aparte de los que inviertes, así que tus pergaminos nunca encarecen tus puntos invertidos. El Dofus moderno adoptó esto en octubre de 2018; Touch usa la misma regla.</li>
<li><strong>Dofus Retro (1.29):</strong> sigue valiendo la regla antigua. Los pergaminos cuentan como puntos normales en la curva de coste, así que un personaje pergamineado a 100 en una característica ya paga el tramo caro en su primerísimo punto invertido. Ahí, pergaminear es una decisión estratégica real, no un regalo.</li>
<li><strong>El tope de pergamineo también cambia:</strong> 100 en la mayoría de versiones, 101 en Retro y hasta 150 en Touch desde la actualización Dédalo.</li>
</ul>
<p>Si no sabes qué reglas sigue tu versión, la <a href="/guides/versions-explained/">guía de versiones</a> explica qué hace de cada una un juego aparte.</p>

<h2>Si aún no has pergamineado</h2>
<p>Igual puedes planificar con ello en cuenta. Pon tu pergamineo real, construye, y la herramienta trabaja con el personaje que tienes hoy en vez de uno idealizado. Más adelante, cuando pergaminees más, actualiza el número y vuelve a optimizar: a menudo liberarás puntos invertidos y desbloquearás ítems que antes no podías llevar. Pergaminear primero tu característica de daño principal es el consejo habitual, pero pondéralo según el contenido que juegas, igual que <a href="/guides/stats-explained/">valorarías cualquier otra stat</a>.</p>

<p><em>¿No sabes cómo está tu personaje? <a href="/setup/">Abre tu proyecto</a>, pon tus pergaminos y vuelve a optimizar para ver tu build real.</em></p>
''',
            },
            'pt': {
                'title': 'Pergaminhos e características: acerte suas stats de base',
                'desc': "Pergaminhos sobem suas stats de base para sempre, e o otimizador assume você totalmente pergaminhado. Como funciona por versão de Dofus e por que importa.",
                'lead': "Pergaminhos mudam em silêncio cada número que a ferramenta te dá, e um projeto novo assume que você já tem todos. Acertar seu pergaminho leva dois minutos e faz cada sugestão servir no seu personagem real.",
                'body': '''
<h2>O que um pergaminho faz de verdade</h2>
<p>Um pergaminho sobe permanentemente uma característica de base. Você lê um pergaminho de Força e mantém aquela Força para sempre, sem gastar pontos, uma vez por personagem. Como é stat de graça, a maioria dos jogadores acaba pergaminhando suas características principais até o teto. É exatamente por isso que o otimizador toma um personagem totalmente pergaminhado como ponto de partida padrão.</p>

<h2>O otimizador assume você totalmente pergaminhado</h2>
<p>Um projeto novo começa como se suas características estivessem pergaminhadas ao máximo. Se as suas não estão, a ferramenta otimiza um personagem um pouco mais rico que o que você joga de fato: seus totais, as <a href="/guides/reading-an-item/">condições de itens que você cumpre</a> e a melhor forma de distribuir seus pontos mudam. Abra a página de características do seu projeto e coloque seu nível real de pergaminho em cada stat. Leva dez segundos, e todas as sugestões seguintes vão servir no seu personagem real.</p>

<h2>A pegadinha das versões: cada Dofus joga com as próprias regras</h2>
<p>O pergaminho é um dos pontos em que as cinco versões realmente diferem, então um hábito de uma pode te enganar em outra sem você perceber.</p>
<ul>
<li><strong>Dofus moderno (Dofus 3, o beta e Dofus 2) e Dofus Touch:</strong> os pontos de pergaminho são contados separadamente dos que você investe, então seus pergaminhos nunca encarecem seus pontos investidos. O Dofus moderno adotou isso em outubro de 2018; o Touch usa a mesma regra.</li>
<li><strong>Dofus Retro (1.29):</strong> a regra antiga ainda vale. Pergaminhos contam como pontos normais na curva de custo, então um personagem pergaminhado a 100 numa característica já paga a faixa cara no primeiríssimo ponto investido. Ali, pergaminhar é uma decisão estratégica de verdade, não um presente.</li>
<li><strong>O teto de pergaminho também muda:</strong> 100 na maioria das versões, 101 no Retro e até 150 no Touch desde a atualização Dédalo.</li>
</ul>
<p>Se você não sabe quais regras a sua versão segue, o <a href="/guides/versions-explained/">guia das versões</a> explica o que faz de cada uma um jogo à parte.</p>

<h2>Se você ainda não pergaminhou</h2>
<p>Dá para planejar com isso em mente mesmo assim. Coloque seu pergaminho real, monte, e a ferramenta trabalha com o personagem que você tem hoje em vez de um idealizado. Depois, quando pergaminhar mais, atualize o número e otimize de novo: você costuma liberar pontos investidos e desbloquear itens que não podia usar. Pergaminhar primeiro sua característica de dano principal é o conselho de sempre, mas pondere conforme o conteúdo que você joga, do mesmo jeito que <a href="/guides/stats-explained/">avaliaria qualquer outra stat</a>.</p>

<p><em>Não sabe como está seu personagem? <a href="/setup/">Abra seu projeto</a>, coloque seus pergaminhos e otimize de novo para ver seu build real.</em></p>
''',
            },
            'de': {
                'title': 'Rollen und Charakteristiken: deine Grundwerte richtig setzen',
                'desc': "Rollen heben deine Grundwerte dauerhaft, und der Optimierer nimmt dich als voll gerollt an. Wie das je nach Dofus-Version funktioniert und warum es zählt.",
                'lead': "Rollen verändern leise jede Zahl, die dir das Werkzeug gibt, und ein neues Projekt nimmt an, dass du sie alle schon hast. Deinen Roll-Stand richtig zu setzen dauert zwei Minuten und lässt jeden Vorschlag zu deinem echten Charakter passen.",
                'body': '''
<h2>Was eine Rolle wirklich macht</h2>
<p>Eine Rolle (Parchemin) hebt dauerhaft eine Grundcharakteristik. Du liest eine Stärke-Rolle und behältst diese Stärke für immer, ohne Punkte auszugeben, einmal pro Charakter. Weil es Gratis-Wert ist, rollen die meisten Spieler ihre Hauptcharakteristiken irgendwann bis zur Obergrenze. Genau deshalb nimmt der Optimierer einen voll gerollten Charakter als Standard-Ausgangspunkt.</p>

<h2>Der Optimierer nimmt dich als voll gerollt an</h2>
<p>Ein neues Projekt startet, als wären deine Charakteristiken auf das Maximum gerollt. Wenn deine das nicht sind, optimiert das Werkzeug einen etwas reicheren Charakter als den, den du wirklich spielst: deine Summen, die <a href="/guides/reading-an-item/">Item-Bedingungen, die du erfüllst</a>, und die beste Punkteverteilung verschieben sich alle. Öffne die Charakteristiken-Seite deines Projekts und trag deinen echten Roll-Stand für jeden Wert ein. Das dauert zehn Sekunden, und jeder Vorschlag danach passt zu deinem echten Charakter.</p>

<h2>Der Versions-Haken: jede Dofus-Version hat eigene Regeln</h2>
<p>Rollen ist einer der Punkte, an denen sich die fünf Versionen wirklich unterscheiden, also kann dich eine Gewohnheit aus der einen in der anderen leise in die Irre führen.</p>
<ul>
<li><strong>Modernes Dofus (Dofus 3, die Beta und Dofus 2) und Dofus Touch:</strong> gerollte Punkte werden getrennt von deinen investierten Punkten gezählt, also machen deine Rollen deine investierten Punkte nie teurer. Das moderne Dofus übernahm das im Oktober 2018; Touch nutzt dieselbe Regel.</li>
<li><strong>Dofus Retro (1.29):</strong> die alte Regel gilt weiter. Rollen zählen als normale Punkte auf der Kostenkurve, also zahlt ein auf 100 in einer Charakteristik gerollter Charakter schon für seinen allerersten investierten Punkt die teure Stufe. Dort ist Rollen eine echte strategische Entscheidung, kein Geschenk.</li>
<li><strong>Auch die Obergrenze unterscheidet sich:</strong> 100 in den meisten Versionen, 101 in Retro und bis zu 150 auf Touch seit dem Dädalus-Update.</li>
</ul>
<p>Wenn du nicht sicher bist, welchen Regeln deine Version folgt, erklärt der <a href="/guides/versions-explained/">Versionen-Guide</a>, was jede zu einem eigenen Spiel macht.</p>

<h2>Wenn du noch nicht gerollt hast</h2>
<p>Du kannst trotzdem darum herum planen. Trag deinen echten Roll-Stand ein, bau, und das Werkzeug arbeitet mit dem Charakter, den du heute hast, statt mit einem idealisierten. Später, wenn du mehr rollst, aktualisiere die Zahl und optimiere erneut: oft werden investierte Punkte frei und du schaltest Items frei, die du vorher nicht tragen konntest. Zuerst deine Haupt-Schadenscharakteristik zu rollen ist der übliche Rat, aber gewichte ihn nach dem Inhalt, den du spielst, genauso wie du <a href="/guides/stats-explained/">jeden anderen Wert bewerten</a> würdest.</p>

<p><em>Nicht sicher, wo dein Charakter steht? <a href="/setup/">Öffne dein Projekt</a>, setz deine Rollen und optimiere erneut, um dein echtes Build zu sehen.</em></p>
''',
            },
        },
    },
    # ------------------------------------------------------------------ #
    'resistance-explained': {
        'published': '2026-07-22',
        'i18n': {
            'en': {
                'title': 'How much resistance you actually need',
                'desc': "Percent resistance caps at 50% in every Dofus version, so stacking more is usually wasted. Fixed vs percent, the cap, and when surplus still helps.",
                'lead': "Resistance is the most misunderstood defensive stat in Dofus. More is not always better, and there is a hard ceiling that quietly wastes anything you stack past it.",
                'body': '''
<h2>Two kinds of resistance</h2>
<p>Dofus has two separate defensive stats with the same name. <strong>Fixed</strong> (linear) resistance subtracts a flat amount from every hit you take. <strong>Percent</strong> resistance reduces the damage by a percentage. They stack, and the fixed part is applied first, then the percentage. Fixed resistance shines against lots of small hits; percent shines against big ones. Most gear gives percent, which is where the confusion starts.</p>

<h2>The 50% ceiling</h2>
<p>Percent elemental resistance is <strong>hard-capped at 50%</strong> for players, and this is true in every version of the game: Dofus 3, the beta, Dofus 2, Dofus Touch and Dofus Retro (1.29) alike. Once an element sits at 50%, more percent resistance in that element does nothing against normal damage. So a set that reads +65% Fire resist is really only using 50 of it. The optimizer knows this and will not waste your build chasing percent resist past the useful ceiling, which is why it sometimes stops adding resist gear that looks like it should help.</p>

<h2>When surplus still helps</h2>
<p>There is one situation where stacking past 50% pays off: <strong>vulnerability</strong>. In PvP, and with some monster mechanics, your resistances get lowered by debuffs. A buffer above 50% keeps you sitting at the cap even after a -10% vulnerability, so competitive PvP players deliberately overstack one or two elements. Fixed resistance, by contrast, has no cap at all, so every point of it is always doing something, especially against chip damage and multi-hit spells.</p>

<h2>How to weight it in the tool</h2>
<p>For PvM, put weight on percent resist for the elements that actually threaten you and stop worrying once the build reaches the cap. For PvP, push it higher on purpose for the vulnerability buffer, and give fixed resist some weight too. You do not enter target numbers item by item: you tell the tool how much resistance is worth to you in the <a href="/guides/tuning-your-weights/">weights</a>, the same way you would <a href="/guides/stats-explained/">value any other stat</a>, and it finds the set that fits.</p>

<p><em>Not sure your defence is pulling its weight? <a href="/quickstart/">Build a set</a>, crank the resist weights and see what the optimizer keeps.</em></p>
''',
            },
            'fr': {
                'title': 'De combien de résistance tu as vraiment besoin',
                'desc': "La résistance en pourcentage plafonne à 50 % dans toutes les versions : au-delà c'est gaspillé. Fixe vs pourcentage, le plafond, et quand le surplus sert.",
                'lead': "La résistance est la stat défensive la plus mal comprise de Dofus. Plus n'est pas toujours mieux, et il y a un plafond dur qui gaspille en silence tout ce que tu empiles au-delà.",
                'body': '''
<h2>Deux types de résistance</h2>
<p>Dofus a deux stats défensives distinctes qui portent le même nom. La résistance <strong>fixe</strong> (linéaire) retire un montant fixe à chaque coup que tu prends. La résistance en <strong>pourcentage</strong> réduit les dégâts d'un certain pourcentage. Elles se cumulent, et la partie fixe s'applique d'abord, le pourcentage ensuite. La fixe brille contre plein de petits coups ; le pourcentage brille contre les gros. La plupart du stuff donne du pourcentage, et c'est là que naît la confusion.</p>

<h2>Le plafond de 50 %</h2>
<p>La résistance élémentaire en pourcentage est <strong>plafonnée à 50 %</strong> pour les joueurs, et c'est vrai dans toutes les versions du jeu : Dofus 3, la bêta, Dofus 2, Dofus Touch et Dofus Retro (1.29) pareil. Une fois un élément à 50 %, ajouter du pourcentage dans cet élément ne fait plus rien contre les dégâts normaux. Donc un stuff affiché +65 % de résistance Feu n'en utilise réellement que 50. L'optimiseur le sait et ne gaspille pas ton build à courir après du pourcentage au-delà du plafond utile : c'est pour ça qu'il arrête parfois de mettre des items resist qui semblent utiles.</p>

<h2>Quand le surplus sert encore</h2>
<p>Il y a une situation où dépasser 50 % paie : la <strong>vulnérabilité</strong>. En PvP, et avec certaines mécaniques de monstres, tes résistances sont baissées par des debuffs. Un buffer au-dessus de 50 % te maintient au plafond même après une vulnérabilité de -10 %, donc les joueurs de PvP compétitif sur-empilent volontairement un ou deux éléments. La résistance fixe, elle, n'a aucun plafond : chaque point sert toujours à quelque chose, surtout contre les dégâts qui grignotent et les sorts multi-coups.</p>

<h2>Comment la pondérer dans l'outil</h2>
<p>En PvM, mets du poids sur le pourcentage de résistance des éléments qui te menacent vraiment et arrête de t'en soucier une fois le plafond atteint. En PvP, pousse-le plus haut exprès pour le buffer de vulnérabilité, et donne aussi du poids à la résistance fixe. Tu n'entres pas des cibles item par item : tu dis à l'outil combien la résistance vaut pour toi dans les <a href="/guides/tuning-your-weights/">poids</a>, comme tu le ferais pour <a href="/guides/stats-explained/">n'importe quelle autre stat</a>, et il trouve le set qui colle.</p>

<p><em>Pas sûr que ta défense soit rentable ? <a href="/quickstart/">Fais un stuff</a>, monte les poids de résistance et regarde ce que l'optimiseur garde.</em></p>
''',
            },
            'es': {
                'title': 'Cuánta resistencia necesitas de verdad',
                'desc': "La resistencia en porcentaje tiene tope del 50 % en todas las versiones: acumular más suele ser inútil. Fija vs porcentaje y cuándo el excedente ayuda.",
                'lead': "La resistencia es la stat defensiva peor entendida de Dofus. Más no siempre es mejor, y hay un techo duro que desperdicia en silencio todo lo que apiles por encima.",
                'body': '''
<h2>Dos tipos de resistencia</h2>
<p>Dofus tiene dos stats defensivas distintas con el mismo nombre. La resistencia <strong>fija</strong> (lineal) resta una cantidad fija a cada golpe que recibes. La resistencia en <strong>porcentaje</strong> reduce el daño en un porcentaje. Se acumulan, y la parte fija se aplica primero y el porcentaje después. La fija brilla contra muchos golpes pequeños; el porcentaje brilla contra los grandes. La mayoría del equipo da porcentaje, y ahí empieza la confusión.</p>

<h2>El techo del 50 %</h2>
<p>La resistencia elemental en porcentaje tiene un <strong>tope del 50 %</strong> para los jugadores, y esto vale en todas las versiones del juego: Dofus 3, la beta, Dofus 2, Dofus Touch y Dofus Retro (1.29) igual. Una vez que un elemento está al 50 %, más porcentaje en ese elemento no hace nada contra el daño normal. Así que un equipo que pone +65 % de resistencia de Fuego solo usa 50 de verdad. El optimizador lo sabe y no desperdicia tu build persiguiendo porcentaje por encima del techo útil: por eso a veces deja de añadir equipo de resistencia que parece que debería ayudar.</p>

<h2>Cuándo el excedente sí ayuda</h2>
<p>Hay una situación en la que pasar del 50 % compensa: la <strong>vulnerabilidad</strong>. En PvP, y con algunas mecánicas de monstruos, tus resistencias bajan por debuffs. Un margen por encima del 50 % te mantiene en el tope incluso tras una vulnerabilidad de -10 %, así que en el PvP competitivo se sobreacumulan a propósito uno o dos elementos. La resistencia fija, en cambio, no tiene tope: cada punto siempre hace algo, sobre todo contra el daño que desgasta y los hechizos de varios golpes.</p>

<h2>Cómo ponderarla en la herramienta</h2>
<p>En PvM, da peso al porcentaje de resistencia de los elementos que de verdad te amenazan y deja de preocuparte una vez alcanzado el tope. En PvP, súbelo a propósito por el margen de vulnerabilidad, y da algo de peso también a la resistencia fija. No metes objetivos objeto a objeto: le dices a la herramienta cuánto vale la resistencia para ti en los <a href="/guides/tuning-your-weights/">pesos</a>, igual que <a href="/guides/stats-explained/">valorarías cualquier otra stat</a>, y ella encuentra el set que encaja.</p>

<p><em>¿No sabes si tu defensa rinde? <a href="/quickstart/">Monta un set</a>, sube los pesos de resistencia y mira qué conserva el optimizador.</em></p>
''',
            },
            'pt': {
                'title': 'Quanta resistência você realmente precisa',
                'desc': "A resistência em porcentagem tem teto de 50% em todas as versões: acumular mais é desperdício. Fixa vs porcentagem e quando o excedente ajuda.",
                'lead': "A resistência é a stat defensiva mais mal compreendida de Dofus. Mais nem sempre é melhor, e existe um teto rígido que desperdiça em silêncio tudo o que você empilha além dele.",
                'body': '''
<h2>Dois tipos de resistência</h2>
<p>Dofus tem duas stats defensivas distintas com o mesmo nome. A resistência <strong>fixa</strong> (linear) subtrai um valor fixo de cada golpe que você recebe. A resistência em <strong>porcentagem</strong> reduz o dano por uma porcentagem. Elas se somam, e a parte fixa é aplicada primeiro, a porcentagem depois. A fixa brilha contra muitos golpes pequenos; a porcentagem brilha contra os grandes. A maioria do equipamento dá porcentagem, e é aí que começa a confusão.</p>

<h2>O teto de 50%</h2>
<p>A resistência elemental em porcentagem tem <strong>teto de 50%</strong> para os jogadores, e isso vale em todas as versões do jogo: Dofus 3, o beta, Dofus 2, Dofus Touch e Dofus Retro (1.29) igual. Quando um elemento está em 50%, mais porcentagem nesse elemento não faz nada contra o dano normal. Então um equipamento que mostra +65% de resistência de Fogo só usa 50 de verdade. O otimizador sabe disso e não desperdiça seu build atrás de porcentagem além do teto útil: é por isso que às vezes ele para de adicionar equipamento de resistência que parece que deveria ajudar.</p>

<h2>Quando o excedente ainda ajuda</h2>
<p>Há uma situação em que passar de 50% compensa: a <strong>vulnerabilidade</strong>. No PvP, e com algumas mecânicas de monstros, suas resistências são reduzidas por debuffs. Uma margem acima de 50% te mantém no teto mesmo depois de uma vulnerabilidade de -10%, então no PvP competitivo os jogadores sobrecarregam de propósito um ou dois elementos. A resistência fixa, por outro lado, não tem teto: cada ponto sempre faz algo, principalmente contra o dano que corrói e feitiços de vários golpes.</p>

<h2>Como ponderar na ferramenta</h2>
<p>No PvM, dê peso à porcentagem de resistência dos elementos que de fato te ameaçam e pare de se preocupar quando o build atinge o teto. No PvP, aumente de propósito pela margem de vulnerabilidade, e dê algum peso também à resistência fixa. Você não insere alvos item a item: você diz à ferramenta quanto a resistência vale para você nos <a href="/guides/tuning-your-weights/">pesos</a>, do mesmo jeito que <a href="/guides/stats-explained/">avaliaria qualquer outra stat</a>, e ela encontra o set que encaixa.</p>

<p><em>Não sabe se sua defesa está valendo a pena? <a href="/quickstart/">Monte um set</a>, aumente os pesos de resistência e veja o que o otimizador mantém.</em></p>
''',
            },
            'de': {
                'title': 'Wie viel Resistenz du wirklich brauchst',
                'desc': "Prozent-Resistenz ist in jeder Dofus-Version bei 50% gedeckelt, mehr stapeln bringt meist nichts. Fest vs Prozent, die Grenze und wann Überschuss doch hilft.",
                'lead': "Resistenz ist der am meisten missverstandene Verteidigungswert in Dofus. Mehr ist nicht immer besser, und es gibt eine harte Grenze, die alles darüber leise verschwendet.",
                'body': '''
<h2>Zwei Arten von Resistenz</h2>
<p>Dofus hat zwei getrennte Verteidigungswerte mit demselben Namen. <strong>Feste</strong> (lineare) Resistenz zieht von jedem Treffer einen festen Betrag ab. <strong>Prozentuale</strong> Resistenz senkt den Schaden um einen Prozentsatz. Sie stapeln sich, und der feste Teil wird zuerst angewendet, der Prozentsatz danach. Feste Resistenz glänzt gegen viele kleine Treffer; Prozent glänzt gegen große. Die meiste Ausrüstung gibt Prozent, und da fängt die Verwirrung an.</p>

<h2>Die 50%-Grenze</h2>
<p>Prozentuale Elementarresistenz ist für Spieler <strong>hart bei 50% gedeckelt</strong>, und das gilt in jeder Version des Spiels: Dofus 3, der Beta, Dofus 2, Dofus Touch und Dofus Retro (1.29) gleichermaßen. Sobald ein Element bei 50% liegt, bringt mehr Prozent in diesem Element gegen normalen Schaden nichts. Eine Ausrüstung mit +65% Feuerresistenz nutzt also wirklich nur 50 davon. Der Optimierer weiß das und verschwendet dein Build nicht damit, Prozent-Resistenz über die nützliche Grenze zu jagen, weshalb er manchmal aufhört, Resistenz-Ausrüstung hinzuzufügen, die zu helfen scheint.</p>

<h2>Wann Überschuss doch hilft</h2>
<p>Es gibt eine Situation, in der ein Stapeln über 50% sich lohnt: <strong>Verwundbarkeit</strong>. Im PvP und bei manchen Monster-Mechaniken werden deine Resistenzen durch Debuffs gesenkt. Ein Puffer über 50% hält dich selbst nach einer -10%-Verwundbarkeit an der Grenze, deshalb stapeln kompetitive PvP-Spieler bewusst ein oder zwei Elemente über. Feste Resistenz dagegen hat gar keine Grenze, also tut jeder Punkt davon immer etwas, besonders gegen Dauerschaden und Mehrfachtreffer-Zauber.</p>

<h2>Wie du sie im Werkzeug gewichtest</h2>
<p>Für PvM leg Gewicht auf Prozent-Resistenz der Elemente, die dich wirklich bedrohen, und mach dir keine Sorgen mehr, sobald das Build die Grenze erreicht. Für PvP schieb sie bewusst höher für den Verwundbarkeits-Puffer, und gib auch fester Resistenz etwas Gewicht. Du gibst keine Zielwerte Item für Item ein: du sagst dem Werkzeug in den <a href="/guides/tuning-your-weights/">Gewichten</a>, wie viel dir Resistenz wert ist, genauso wie du <a href="/guides/stats-explained/">jeden anderen Wert bewerten</a> würdest, und es findet das passende Set.</p>

<p><em>Nicht sicher, ob deine Verteidigung sich lohnt? <a href="/quickstart/">Bau ein Set</a>, dreh die Resistenz-Gewichte hoch und schau, was der Optimierer behält.</em></p>
''',
            },
        },
    },

    # ------------------------------------------------------------------ #
    # Version neutral: every version has per-element monster resistances,
    # so no numbers and no modern-only stats.
    'monster-weaknesses': {
        'published': '2026-07-23',
        'i18n': {
            'en': {
                'title': "Monster weaknesses: hit the element that hurts",
                'desc': "Every monster resists some elements and takes extra from another. How to find a weakness in the bestiary and turn it into a harder-hitting build.",
                'lead': "Every monster resists some elements and folds to another. Here is how to find a weakness in the bestiary, and how to turn it into real damage.",
                'body': '''
<h2>Same spell, very different damage</h2>
<p>Monsters do not take damage equally. Each one carries its own resistances to earth, fire, air and water (and neutral), so the same attack can lose half its punch against the wrong target and land full force against the right one. Before blaming your gear or your spells, check what you were hitting: picking targets by element is the cheapest damage boost in the game, in every version of Dofus.</p>

<h2>Reading a monster's card</h2>
<p>Open a monster in the <a href="/encyclopedia/monsters/">bestiary</a>: its card lists resistances element by element, and when one element clearly hurts it more than the rest, that weakness is highlighted. You can also filter the whole bestiary by weakness, which answers the practical question: which monsters should my earth build farm? Keep in mind that the same monster often resists more in its stronger versions, so a family that melts at low level can shrug off that element later on. (Dofus 2 is the exception here: we have no reliable monster stats for that version, so its bestiary does not show resistances.)</p>

<h2>Turning a weakness into a build</h2>
<p>If the monsters you farm share a weakness your class can hit, lean into it: weight that element and its characteristic (Strength for earth, Intelligence for fire, Agility for air, Chance for water) high in the optimizer and let it chase the gear that pushes that element. A <a href="/guides/mono-vs-multi-element/">focused build</a> multiplies what the weakness already gives you. That is how farming builds are born: not made for everything, made for the dungeon you run twenty times.</p>

<h2>When you cannot match the weakness</h2>
<p>You will not regear for every fight, and some classes are locked into their element. The good news: most of the win is simply avoiding the monster's strongest resistance. Hitting its second-best element is usually fine; feeding your damage into the element it was built to shrug off is what stings. In a team, hand the weak element to whoever already hits it, and remember the same logic in reverse: the elements monsters attack with decide which of <a href="/guides/resistance-explained/">your own resistances</a> matter.</p>

<p><em>Pick a dungeon you grind, look up its monsters in the <a href="/encyclopedia/monsters/">bestiary</a>, then <a href="/quickstart/">build a set</a> that leans into their weakness.</em></p>
''',
            },
            'fr': {
                'title': "Faiblesses des monstres : tape l'élément qui fait mal",
                'desc': "Chaque monstre résiste à certains éléments et prend très cher sur un autre. Comment repérer une faiblesse dans le bestiaire et en faire un build qui cogne.",
                'lead': "Chaque monstre résiste à certains éléments et plie face à un autre. Voilà comment repérer une faiblesse dans le bestiaire, et comment la transformer en vrais dégâts.",
                'body': '''
<h2>Même sort, dégâts très différents</h2>
<p>Les monstres n'encaissent pas tous pareil. Chacun a ses propres résistances en terre, feu, air et eau (et neutre), donc la même attaque peut perdre la moitié de sa force contre la mauvaise cible et taper plein pot contre la bonne. Avant d'accuser ton stuff ou tes sorts, regarde ce que tu frappais : choisir ses cibles par élément est le boost de dégâts le moins cher du jeu, dans toutes les versions de Dofus.</p>

<h2>Lire la fiche d'un monstre</h2>
<p>Ouvre un monstre dans le <a href="/encyclopedia/monsters/">bestiaire</a> : sa fiche liste les résistances élément par élément, et quand un élément lui fait clairement plus mal que les autres, cette faiblesse est mise en évidence. Tu peux aussi filtrer tout le bestiaire par faiblesse, ce qui répond à la vraie question : quels monstres mon build terre devrait-il farmer ? Garde en tête qu'un même monstre résiste souvent plus dans ses versions plus fortes : une famille qui fond à bas niveau peut encaisser cet élément plus tard. (Dofus 2 est l'exception ici : on n'a pas de stats de monstres fiables pour cette version, donc son bestiaire n'affiche pas les résistances.)</p>

<h2>Transformer une faiblesse en build</h2>
<p>Si les monstres que tu farmes partagent une faiblesse que ta classe peut exploiter, fonce : mets un gros poids sur cet élément et sa caractéristique (Force pour la terre, Intelligence pour le feu, Agilité pour l'air, Chance pour l'eau) dans l'optimiseur et laisse-le chercher le stuff qui booste cet élément. Un <a href="/guides/mono-vs-multi-element/">build mono-élément</a> multiplie ce que la faiblesse te donne déjà. C'est comme ça que naissent les builds de farm : pas faits pour tout, faits pour le donjon que tu refais vingt fois.</p>

<h2>Quand tu ne peux pas viser la faiblesse</h2>
<p>Tu ne vas pas te rééquiper pour chaque combat, et certaines classes sont bloquées sur leur élément. La bonne nouvelle : l'essentiel du gain, c'est simplement d'éviter la plus grosse résistance du monstre. Taper son deuxième meilleur élément passe en général très bien ; envoyer tes dégâts dans l'élément qu'il est fait pour encaisser, c'est ça qui pique. En équipe, laisse l'élément faible à celui qui le tape déjà, et pense à la logique inverse : les éléments avec lesquels les monstres attaquent déterminent lesquelles de <a href="/guides/resistance-explained/">tes résistances</a> comptent vraiment.</p>

<p><em>Choisis un donjon que tu enchaînes, regarde ses monstres dans le <a href="/encyclopedia/monsters/">bestiaire</a>, puis <a href="/quickstart/">fais un stuff</a> qui tape dans leur faiblesse.</em></p>
''',
            },
            'es': {
                'title': "Debilidades de los monstruos: pega en el elemento que duele",
                'desc': "Cada monstruo resiste unos elementos y sufre con otro. Cómo encontrar una debilidad en el bestiario y convertirla en un build que pega más fuerte.",
                'lead': "Cada monstruo resiste unos elementos y se derrite con otro. Aquí tienes cómo encontrar una debilidad en el bestiario y convertirla en daño de verdad.",
                'body': '''
<h2>Mismo hechizo, daño muy distinto</h2>
<p>Los monstruos no encajan el daño por igual. Cada uno tiene sus propias resistencias a tierra, fuego, aire y agua (y neutral), así que el mismo ataque puede perder la mitad de su fuerza contra el objetivo equivocado y entrar a tope contra el correcto. Antes de culpar a tu equipo o a tus hechizos, mira a qué le estabas pegando: elegir objetivos por elemento es la mejora de daño más barata del juego, en todas las versiones de Dofus.</p>

<h2>Leer la ficha de un monstruo</h2>
<p>Abre un monstruo en el <a href="/encyclopedia/monsters/">bestiario</a>: su ficha muestra las resistencias elemento a elemento, y cuando uno le duele claramente más que el resto, esa debilidad aparece resaltada. También puedes filtrar todo el bestiario por debilidad, lo que responde a la pregunta práctica: ¿qué monstruos debería farmear mi build de tierra? Ten en cuenta que un mismo monstruo a menudo resiste más en sus versiones más fuertes: una familia que se derrite a bajo nivel puede aguantar ese mismo elemento más adelante. (Dofus 2 es la excepción: no tenemos estadísticas fiables de monstruos para esa versión, así que su bestiario no muestra resistencias.)</p>

<h2>Convertir una debilidad en un build</h2>
<p>Si los monstruos que farmeas comparten una debilidad que tu clase puede explotar, apuesta por ella: dale un peso alto a ese elemento y a su característica (Fuerza para tierra, Inteligencia para fuego, Agilidad para aire, Suerte para agua) en el optimizador y deja que persiga el equipo que potencia ese elemento. Un <a href="/guides/mono-vs-multi-element/">build concentrado</a> multiplica lo que la debilidad ya te da. Así nacen los builds de farmeo: no hechos para todo, hechos para la mazmorra que repites veinte veces.</p>

<h2>Cuando no puedes apuntar a la debilidad</h2>
<p>No vas a reequiparte para cada combate, y algunas clases están ancladas a su elemento. La buena noticia: la mayor parte de la ganancia está en evitar la resistencia más alta del monstruo. Pegar en su segundo mejor elemento suele ir bien; meter tu daño en el elemento que está hecho para encajar es lo que sale caro. En equipo, déjale el elemento débil a quien ya lo pega, y recuerda la lógica inversa: los elementos con los que atacan los monstruos deciden cuáles de <a href="/guides/resistance-explained/">tus propias resistencias</a> importan.</p>

<p><em>Elige una mazmorra que repitas, busca sus monstruos en el <a href="/encyclopedia/monsters/">bestiario</a> y <a href="/quickstart/">monta un set</a> que explote su debilidad.</em></p>
''',
            },
            'pt': {
                'title': "Fraquezas dos monstros: bata no elemento que dói",
                'desc': "Cada monstro resiste a uns elementos e sofre com outro. Como achar uma fraqueza no bestiário e transformá-la num build que bate mais forte.",
                'lead': "Cada monstro resiste a uns elementos e derrete com outro. Veja como achar uma fraqueza no bestiário e como transformá-la em dano de verdade.",
                'body': '''
<h2>Mesmo feitiço, dano bem diferente</h2>
<p>Os monstros não tomam dano do mesmo jeito. Cada um tem suas próprias resistências a terra, fogo, ar e água (e neutro), então o mesmo ataque pode perder metade da força contra o alvo errado e entrar inteiro contra o certo. Antes de culpar seu equipamento ou seus feitiços, olhe no que você estava batendo: escolher alvos por elemento é o aumento de dano mais barato do jogo, em todas as versões de Dofus.</p>

<h2>Ler a ficha de um monstro</h2>
<p>Abra um monstro no <a href="/encyclopedia/monsters/">bestiário</a>: a ficha lista as resistências elemento por elemento, e quando um deles machuca claramente mais que os outros, essa fraqueza aparece destacada. Você também pode filtrar o bestiário inteiro por fraqueza, o que responde à pergunta prática: quais monstros meu build de terra deveria farmar? Lembre que um mesmo monstro muitas vezes resiste mais nas versões mais fortes: uma família que derrete em nível baixo pode aguentar esse mesmo elemento mais adiante. (Dofus 2 é a exceção: não temos estatísticas confiáveis dos monstros para essa versão, então o bestiário dela não mostra resistências.)</p>

<h2>Transformar uma fraqueza em build</h2>
<p>Se os monstros que você farma têm uma fraqueza em comum que sua classe consegue atingir, aposte nela: dê peso alto a esse elemento e à característica dele (Força para terra, Inteligência para fogo, Agilidade para ar, Sorte para água) no otimizador e deixe ele caçar o equipamento que impulsiona esse elemento. Um <a href="/guides/mono-vs-multi-element/">build concentrado</a> multiplica o que a fraqueza já te dá. É assim que nascem os builds de farm: não feitos para tudo, feitos para a masmorra que você repete vinte vezes.</p>

<h2>Quando não dá para mirar na fraqueza</h2>
<p>Você não vai se reequipar para cada luta, e algumas classes ficam presas ao próprio elemento. A boa notícia: a maior parte do ganho está em evitar a resistência mais alta do monstro. Bater no segundo melhor elemento costuma servir; jogar seu dano no elemento que ele foi feito para aguentar é o que custa caro. Em grupo, deixe o elemento fraco com quem já bate nele, e lembre da lógica inversa: os elementos com que os monstros atacam decidem quais das <a href="/guides/resistance-explained/">suas próprias resistências</a> importam.</p>

<p><em>Escolha uma masmorra que você repete, veja os monstros dela no <a href="/encyclopedia/monsters/">bestiário</a> e <a href="/quickstart/">monte um set</a> que explore a fraqueza deles.</em></p>
''',
            },
            'de': {
                'title': "Monster-Schwächen: hau auf das Element, das wehtut",
                'desc': "Jedes Monster steckt manche Elemente weg und leidet unter einem anderen. Wie du im Bestiarium Schwächen findest und daraus ein Build machst, das härter trifft.",
                'lead': "Jedes Monster steckt manche Elemente weg und knickt bei einem anderen ein. Hier siehst du, wie du im Bestiarium Schwächen findest und daraus echten Schaden machst.",
                'body': '''
<h2>Gleicher Zauber, ganz anderer Schaden</h2>
<p>Monster stecken Schaden nicht gleich weg. Jedes hat eigene Resistenzen gegen Erde, Feuer, Luft und Wasser (und Neutral), also kann derselbe Angriff gegen das falsche Ziel die halbe Wucht verlieren und beim richtigen voll einschlagen. Bevor du deiner Ausrüstung oder deinen Zaubern die Schuld gibst, schau, worauf du da gehauen hast: Ziele nach Element zu wählen ist der billigste Schadensboost im Spiel, in jeder Version von Dofus.</p>

<h2>Den Steckbrief eines Monsters lesen</h2>
<p>Öffne ein Monster im <a href="/encyclopedia/monsters/">Bestiarium</a>: sein Steckbrief listet die Resistenzen Element für Element, und wenn ihm ein Element deutlich mehr wehtut als der Rest, ist diese Schwäche hervorgehoben. Du kannst das ganze Bestiarium auch nach Schwäche filtern, was die praktische Frage beantwortet: welche Monster sollte mein Erd-Build farmen? Denk daran, dass dasselbe Monster in seinen stärkeren Varianten oft mehr aushält: eine Familie, die auf niedriger Stufe schmilzt, kann dasselbe Element später wegstecken. (Dofus 2 ist die Ausnahme: für diese Version haben wir keine verlässlichen Monsterwerte, deshalb zeigt ihr Bestiarium keine Resistenzen.)</p>

<h2>Aus einer Schwäche ein Build machen</h2>
<p>Wenn die Monster, die du farmst, eine Schwäche teilen, die deine Klasse treffen kann, zieh es durch: gewichte dieses Element und seinen Wert (Stärke für Erde, Intelligenz für Feuer, Flinkheit für Luft, Glück für Wasser) im Optimierer hoch und lass ihn die Ausrüstung suchen, die das Element pusht. Ein <a href="/guides/mono-vs-multi-element/">fokussiertes Build</a> multipliziert, was die Schwäche dir schon schenkt. So entstehen Farm-Builds: nicht für alles gemacht, sondern für den Dungeon, den du zwanzigmal läufst.</p>

<h2>Wenn du die Schwäche nicht treffen kannst</h2>
<p>Du rüstest nicht für jeden Kampf um, und manche Klassen sind auf ihr Element festgelegt. Die gute Nachricht: der größte Gewinn liegt schon darin, die stärkste Resistenz des Monsters zu meiden. Sein zweitbestes Element zu treffen ist meist völlig in Ordnung; deinen Schaden in das Element zu stecken, das es wegstecken soll, das kostet. Im Team überlass das schwache Element dem, der es ohnehin trifft, und denk an die umgekehrte Logik: die Elemente, mit denen Monster angreifen, entscheiden, welche <a href="/guides/resistance-explained/">deiner eigenen Resistenzen</a> zählen.</p>

<p><em>Such dir einen Dungeon, den du ständig läufst, schau seine Monster im <a href="/encyclopedia/monsters/">Bestiarium</a> nach und <a href="/quickstart/">bau ein Set</a>, das ihre Schwäche voll ausnutzt.</em></p>
''',
            },
        },
    },

    # ------------------------------------------------------------------ #
    # The six dofus slots hold three different families in the modern game and
    # only Dofus in Retro. Every figure below is counted from our own item
    # tables (type 9), so it moves with the data instead of being asserted:
    # 320 items on Dofus 3 and the beta, 266 on Touch, 17 on Retro. The
    # example items are read from the same tables.
    'dofus-and-trophies': {
        'published': '2026-08-11',
        'i18n': {
            'en': {
                'title': 'Dofus and trophies: how to fill your six slots',
                'desc': "Six slots, and in modern Dofus three different families competing for them: trophies, Dofus and Prysmaradites. What goes where, and what it costs you.",
                'lead': "Every character has six of these slots, and in the modern game they are the most crowded decision in your build. Here is what can go in them and how to choose.",
                'body': '''
<h2>Six slots, three families</h2>
<p>Your character carries <strong>six</strong> of these slots, in every version of the game. What you can put in them is where the versions part ways. In Dofus 3, the beta and Dofus 2 there are over three hundred candidates, and they come in three families: <strong>trophies</strong>, <strong>Dofus</strong> proper, and <strong>Prysmaradites</strong>. On Dofus Touch the same three families exist with its own roster.</p>

<h2>Trophies: a flat stat, then a price</h2>
<p>Trophies arrive in tiers. The small ones ask for level 50 and give a plain bonus with no downside: a Minor Acrobat is simply +15 Agility. The next tier, at level 100, doubles it: an Acrobat is +30 Agility, still free of any cost. From the level 150 tier the deal changes, and this is where players get caught: an Arcanist gives +6% spell damage but takes <strong>6% melee resistance and 6% ranged resistance</strong> with it. The stronger the trophy, the more it asks back.</p>

<h2>Dofus and Prysmaradites: the expensive end</h2>
<p>The Dofus themselves sit at level 180 and are broad rather than sharp: an Ivory Dofus adds 4% resistance in all five elements, an Ice Dofus adds 25 damage in all five. They are the quest reward at the end of very long chains, and they are worth a slot for exactly that breadth. Prysmaradites, at level 200, go back to trading: a Caraprys hands you 2 summons and takes <strong>1 MP</strong>. Losing an MP is not a rounding error, so a Prysmaradite has to earn its slot against a Dofus that costs you nothing.</p>

<h2>Dofus Retro plays a much simpler game</h2>
<p>Retro has <strong>no trophies and no Prysmaradites at all</strong>. Its six slots are filled from seventeen items, and twelve of those are the classic level 6 Dofus: Emerald, Turquoise, Crimson, Vulbis, Ochre, Ivory, Cawwot, Ebony, Kaliptus and the rest. There is no tier ladder and no trade-off family to weigh. If you learned the modern trophy game, none of that thinking transfers to Retro, and the reverse is just as true.</p>

<h2>Let the optimizer weigh the trade</h2>
<p>This is a slot where counting by hand goes wrong fast, because the drawbacks are in different currencies from the gains: is 6% spell damage worth 6% melee resistance? Is 2 summons worth an MP? The optimizer already knows every candidate and every penalty attached to it, and it weighs them against your own priorities rather than against a tier list. Set what you care about, run it, and read what it put in those six slots.</p>

<p><em>Curious what the six slots should hold for your character? <a href="/setup/">Build it here.</a></em></p>
''',
            },
            'fr': {
                'title': 'Dofus et trophées : comment remplir tes six emplacements',
                'desc': "Six emplacements, et sur le Dofus moderne trois familles qui se les disputent : trophées, Dofus et Prysmaradites. Ce qui va où, et ce que ça te coûte.",
                'lead': "Chaque personnage a six de ces emplacements, et sur le jeu moderne c'est la décision la plus disputée de ton build. Voilà ce qui peut y aller et comment choisir.",
                'body': '''
<h2>Six emplacements, trois familles</h2>
<p>Ton personnage porte <strong>six</strong> de ces emplacements, dans toutes les versions du jeu. Ce que tu peux y mettre, en revanche, sépare les versions. Sur Dofus 3, la beta et Dofus 2, plus de trois cents candidats se présentent, répartis en trois familles : les <strong>trophées</strong>, les <strong>Dofus</strong> eux-mêmes, et les <strong>Prysmaradites</strong>. Dofus Touch a les mêmes trois familles avec son propre catalogue.</p>

<h2>Les trophées : une stat sèche, puis une facture</h2>
<p>Les trophées arrivent par paliers. Les petits demandent le niveau 50 et donnent un bonus simple, sans contrepartie : un Acrobate mineur, c'est +15 Agilité, point. Le palier suivant, au niveau 100, double la mise : un Acrobate donne +30 Agilité, toujours sans coût. À partir du palier 150, le marché change, et c'est là que les joueurs se font avoir : un Arcaniste donne +6% de dommages aux sorts mais emporte avec lui <strong>6% de résistance mêlée et 6% de résistance distance</strong>. Plus le trophée est fort, plus il réclame en échange.</p>

<h2>Dofus et Prysmaradites : le haut du panier</h2>
<p>Les Dofus eux-mêmes sont au niveau 180, et ils sont larges plutôt que pointus : un Dofus Ivoire ajoute 4% de résistance dans les cinq éléments, un Dofus Glace ajoute 25 dommages dans les cinq. Ce sont les récompenses de très longues quêtes, et c'est exactement cette largeur qui justifie un emplacement. Les Prysmaradites, au niveau 200, reviennent au troc : un Caraprys te donne 2 invocations et te prend <strong>1 PM</strong>. Perdre un PM n'est pas un détail, donc un Prysmaradite doit mériter sa place face à un Dofus qui, lui, ne coûte rien.</p>

<h2>Dofus Retro joue à un jeu bien plus simple</h2>
<p>Retro n'a <strong>ni trophées ni Prysmaradites</strong>. Ses six emplacements se remplissent parmi dix-sept objets, dont douze sont les Dofus classiques de niveau 6 : Émeraude, Turquoise, Pourpre, Vulbis, Ocre, Ivoire, Cawotte, Ébène, Kaliptus et les autres. Pas d'échelle de paliers, pas de famille à contrepartie à peser. Si tu as appris le jeu des trophées sur le moderne, rien de ce raisonnement ne se transpose sur Retro, et l'inverse est tout aussi vrai.</p>

<h2>Laisse l'optimiseur peser l'échange</h2>
<p>C'est un emplacement où le calcul à la main dérape vite, parce que les contreparties ne sont pas dans la même monnaie que les gains : est-ce que 6% de dommages aux sorts valent 6% de résistance mêlée ? Est-ce que 2 invocations valent un PM ? L'optimiseur connaît déjà chaque candidat et chaque malus qui y est attaché, et il les pèse selon tes propres priorités plutôt que selon une tier list. Règle ce qui compte pour toi, lance, et regarde ce qu'il a mis dans ces six emplacements.</p>

<p><em>Curieux de savoir ce que devraient porter tes six emplacements ? <a href="/setup/">Construis-le ici.</a></em></p>
''',
            },
            'es': {
                'title': 'Dofus y trofeos: cómo llenar tus seis huecos',
                'desc': "Seis huecos y, en el Dofus moderno, tres familias que se los disputan: trofeos, Dofus y Prysmaradites. Qué va en cada uno y qué te cuesta.",
                'lead': "Todo personaje tiene seis de estos huecos y, en el juego moderno, son la decisión más disputada de tu build. Esto es lo que puede ir en ellos y cómo elegir.",
                'body': '''
<h2>Seis huecos, tres familias</h2>
<p>Tu personaje lleva <strong>seis</strong> de estos huecos en todas las versiones del juego. Lo que puedes meter en ellos es donde las versiones se separan. En Dofus 3, la beta y Dofus 2 hay más de trescientos candidatos, repartidos en tres familias: <strong>trofeos</strong>, <strong>Dofus</strong> propiamente dichos y <strong>Prysmaradites</strong>. Dofus Touch tiene esas mismas tres familias con su propio catálogo.</p>

<h2>Los trofeos: una estadística seca y luego la factura</h2>
<p>Los trofeos llegan por niveles. Los pequeños piden nivel 50 y dan un bonus simple, sin contrapartida: un Acróbata menor son +15 de Agilidad y ya está. El siguiente escalón, en el nivel 100, dobla la apuesta: un Acróbata da +30 de Agilidad, todavía sin coste. A partir del escalón 150 el trato cambia, y ahí es donde pican los jugadores: un Arcanista da +6% de daño de hechizos pero se lleva por delante <strong>un 6% de resistencia cuerpo a cuerpo y un 6% de resistencia a distancia</strong>. Cuanto más fuerte es el trofeo, más pide a cambio.</p>

<h2>Dofus y Prysmaradites: la parte cara</h2>
<p>Los Dofus están en el nivel 180 y son amplios más que afilados: un Dofus Marfil añade un 4% de resistencia en los cinco elementos, un Dofus Hielo añade 25 de daño en los cinco. Son la recompensa de cadenas de misiones larguísimas, y esa amplitud es justo lo que justifica un hueco. Los Prysmaradites, en el nivel 200, vuelven al trueque: un Caraprys te da 2 invocaciones y te quita <strong>1 PM</strong>. Perder un PM no es un detalle, así que un Prysmaradite tiene que ganarse el hueco frente a un Dofus que no te cuesta nada.</p>

<h2>Dofus Retro juega a algo mucho más sencillo</h2>
<p>Retro no tiene <strong>ni trofeos ni Prysmaradites</strong>. Sus seis huecos se llenan con diecisiete objetos, y doce de ellos son los Dofus clásicos de nivel 6: Esmeralda, Turquesa, Púrpura, Vulbis, Ocre, Marfil, Cawotte, Ébano, Kaliptus y compañía. No hay escalera de niveles ni familia con contrapartida que sopesar. Si aprendiste el juego de los trofeos en el moderno, nada de ese razonamiento se traslada a Retro, y al revés igual.</p>

<h2>Deja que el optimizador pese el intercambio</h2>
<p>Es un hueco donde echar cuentas a mano se tuerce enseguida, porque las contrapartidas no están en la misma moneda que las ganancias: ¿vale un 6% de daño de hechizos lo que cuesta un 6% de resistencia cuerpo a cuerpo? ¿Valen 2 invocaciones un PM? El optimizador ya conoce cada candidato y cada penalización que lleva pegada, y los pesa según tus prioridades y no según una tier list. Ajusta lo que te importa, ejecútalo y mira qué ha puesto en esos seis huecos.</p>

<p><em>¿Con curiosidad por lo que deberían llevar tus seis huecos? <a href="/setup/">Constrúyelo aquí.</a></em></p>
''',
            },
            'pt': {
                'title': 'Dofus e troféus: como preencher seus seis espaços',
                'desc': "Seis espaços e, no Dofus moderno, três famílias disputando: troféus, Dofus e Prysmaradites. O que vai em cada um e quanto custa.",
                'lead': "Todo personagem tem seis desses espaços e, no jogo moderno, são a decisão mais disputada do seu build. Aqui está o que pode entrar neles e como escolher.",
                'body': '''
<h2>Seis espaços, três famílias</h2>
<p>Seu personagem carrega <strong>seis</strong> desses espaços, em todas as versões do jogo. O que dá para colocar neles é onde as versões se separam. No Dofus 3, no beta e no Dofus 2 há mais de trezentos candidatos, divididos em três famílias: <strong>troféus</strong>, <strong>Dofus</strong> propriamente ditos e <strong>Prysmaradites</strong>. O Dofus Touch tem as mesmas três famílias com o catálogo dele.</p>

<h2>Troféus: um atributo seco e depois a conta</h2>
<p>Os troféus vêm em degraus. Os pequenos pedem nível 50 e dão um bônus simples, sem contrapartida: um Acrobata menor são +15 de Agilidade e pronto. O degrau seguinte, no nível 100, dobra a aposta: um Acrobata dá +30 de Agilidade, ainda sem custo. A partir do degrau 150 o acordo muda, e é aí que os jogadores se dão mal: um Arcanista dá +6% de dano de feitiços mas leva junto <strong>6% de resistência corpo a corpo e 6% de resistência à distância</strong>. Quanto mais forte o troféu, mais ele cobra de volta.</p>

<h2>Dofus e Prysmaradites: a ponta cara</h2>
<p>Os Dofus ficam no nível 180 e são largos em vez de afiados: um Dofus Marfim soma 4% de resistência nos cinco elementos, um Dofus Gelo soma 25 de dano nos cinco. São a recompensa de cadeias de missões longuíssimas, e é exatamente essa largura que justifica um espaço. Os Prysmaradites, no nível 200, voltam à troca: um Caraprys te dá 2 invocações e tira <strong>1 PM</strong>. Perder um PM não é detalhe, então um Prysmaradite precisa merecer o espaço diante de um Dofus que não custa nada.</p>

<h2>O Dofus Retro joga um jogo bem mais simples</h2>
<p>O Retro não tem <strong>troféus nem Prysmaradites</strong>. Seus seis espaços são preenchidos entre dezessete itens, e doze deles são os Dofus clássicos de nível 6: Esmeralda, Turquesa, Púrpura, Vulbis, Ocre, Marfim, Cawotte, Ébano, Kaliptus e companhia. Não há escada de degraus nem família com contrapartida para pesar. Se você aprendeu o jogo dos troféus no moderno, nada desse raciocínio se transfere para o Retro, e o contrário também não.</p>

<h2>Deixe o otimizador pesar a troca</h2>
<p>É um espaço em que a conta na mão desanda rápido, porque as contrapartidas não estão na mesma moeda que os ganhos: 6% de dano de feitiços valem 6% de resistência corpo a corpo? 2 invocações valem um PM? O otimizador já conhece cada candidato e cada penalidade colada nele, e os pesa pelas suas prioridades em vez de por uma tier list. Ajuste o que importa para você, rode e veja o que ele colocou nesses seis espaços.</p>

<p><em>Curioso sobre o que seus seis espaços deveriam levar? <a href="/setup/">Monte aqui.</a></em></p>
''',
            },
            'de': {
                'title': 'Dofus und Trophäen: wie du deine sechs Plätze füllst',
                'desc': "Sechs Plätze, und im modernen Dofus streiten sich drei Familien darum: Trophäen, Dofus und Prysmaradite. Was wohin gehört und was es dich kostet.",
                'lead': "Jeder Charakter hat sechs dieser Plätze, und im modernen Spiel sind sie die umkämpfteste Entscheidung deines Builds. Hier steht, was hineinkann und wie du wählst.",
                'body': '''
<h2>Sechs Plätze, drei Familien</h2>
<p>Dein Charakter trägt in jeder Version <strong>sechs</strong> dieser Plätze. Was hineindarf, trennt die Versionen. In Dofus 3, im Beta und in Dofus 2 bewerben sich über dreihundert Gegenstände, verteilt auf drei Familien: <strong>Trophäen</strong>, die <strong>Dofus</strong> selbst und die <strong>Prysmaradite</strong>. Dofus Touch hat dieselben drei Familien mit eigenem Angebot.</p>

<h2>Trophäen: ein trockener Wert, dann die Rechnung</h2>
<p>Trophäen kommen in Stufen. Die kleinen verlangen Stufe 50 und geben einen schlichten Bonus ohne Gegenleistung: ein Kleiner Akrobat sind +15 Flinkheit, mehr nicht. Die nächste Stufe, auf 100, verdoppelt das: ein Akrobat gibt +30 Flinkheit, weiterhin kostenlos. Ab der Stufe 150 ändert sich der Handel, und genau da tappen Spieler hinein: ein Arkanist gibt +6% Zauberschaden, nimmt aber <strong>6% Nahkampfresistenz und 6% Fernkampfresistenz</strong> mit. Je stärker die Trophäe, desto mehr fordert sie zurück.</p>

<h2>Dofus und Prysmaradite: das teure Ende</h2>
<p>Die Dofus selbst liegen auf Stufe 180 und sind breit statt spitz: ein Elfenbein-Dofus gibt 4% Resistenz in allen fünf Elementen, ein Eis-Dofus 25 Schaden in allen fünf. Sie sind die Belohnung sehr langer Questketten, und genau diese Breite rechtfertigt einen Platz. Die Prysmaradite auf Stufe 200 kehren zum Tauschhandel zurück: ein Caraprys gibt dir 2 Beschwörungen und nimmt <strong>1 BP</strong>. Ein BP zu verlieren ist keine Kleinigkeit, also muss sich ein Prysmaradit seinen Platz gegen ein Dofus verdienen, das dich nichts kostet.</p>

<h2>Dofus Retro spielt ein deutlich einfacheres Spiel</h2>
<p>Retro hat <strong>weder Trophäen noch Prysmaradite</strong>. Seine sechs Plätze werden aus siebzehn Gegenständen gefüllt, zwölf davon die klassischen Dofus der Stufe 6: Smaragd, Türkis, Purpur, Vulbis, Ocker, Elfenbein, Cawotte, Ebenholz, Kaliptus und die übrigen. Keine Stufenleiter, keine Familie mit Gegenleistung zum Abwägen. Wer das Trophäenspiel im modernen Dofus gelernt hat, kann davon nichts nach Retro mitnehmen, und umgekehrt genauso wenig.</p>

<h2>Lass den Optimierer den Tausch abwägen</h2>
<p>Hier geht Kopfrechnen schnell schief, weil die Nachteile in einer anderen Währung stehen als die Gewinne: sind 6% Zauberschaden 6% Nahkampfresistenz wert? Sind 2 Beschwörungen ein BP wert? Der Optimierer kennt jeden Kandidaten und jeden Malus daran bereits und wägt sie nach deinen Prioritäten ab statt nach einer Tier-Liste. Stell ein, was dir wichtig ist, lass ihn laufen und schau, was er auf diese sechs Plätze gelegt hat.</p>

<p><em>Neugierig, was auf deine sechs Plätze gehört? <a href="/setup/">Bau es hier.</a></em></p>
''',
            },
        },
    },

    # ------------------------------------------------------------------ #
    # Transcendence runes are a modern-client system: Dofus 3, the beta and
    # Dofus 2 have them, Touch and Retro do not, and those two do not even
    # share a smithmagic ruleset with each other. So this guide carries three
    # contents. Source: the rune catalogue the site itself ships
    # (forgemagie_transcendance.json, 81 runes over three ranks) and the rules
    # the forgemagie tool enforces.
    'transcendence-runes': {
        'published': '2026-08-12',
        'version_groups': {'touch': 'touch', 'retro': 'retro'},
        'i18n_by_group': {
            'modern': {
                'en': {
                    'title': 'Transcendence runes: the last stat, and the last one you get',
                    'desc': 'Transcendence runes never fail, but they only land on an untouched item and they lock it forever. When to spend one, and on what.',
                    'lead': 'A transcendence rune is the one forgemagie that cannot fail. The price is that it goes on a clean item and closes it for good, so it is the last decision you make on a piece.',
                    'body': '''
<h2>What they are</h2>
<p>Transcendence runes add one bonus to an item at <strong>100% success</strong>. There are 81 of them on the modern client, over three ranks: Ta, Pata and Rata. Rank decides the size, so Rune Ta Ine gives +10 Intelligence, Pata Ine +15 and Rata Ine +20. Almost every useful line has one: the four elements, Power, Vitality, damage and resistance per element, critical damage, AP and MP reduction and resistance, lock, dodge, initiative, pods and heals.</p>

<h2>The two rules that decide everything</h2>
<p>A transcendence rune only lands on an item that has <strong>never been smithmagicked</strong>. If the piece already carries an over, the rune refuses it, and you have to strip the over first. And once the rune is on, the item is <strong>locked</strong>: no further forgemagie, ever. Not a smaller over, not a fix, nothing.</p>
<p>So the order is fixed. Either you forgemagie a piece and never transcend it, or you transcend it and never touch it again. There is no third path.</p>

<h2>Which piece deserves one</h2>
<p>Because the item has to be clean, the natural target is a piece you were going to leave alone: an item whose rolls are already good enough, or one where the over you wanted is too expensive to chase. Spending a rune on a piece you would have overed anyway costs you the over.</p>
<p>Weight matters too. A Rata rune is the heaviest of its family, and heavy runes are the expensive ones. If the +15 from a Pata closes the gap you actually needed, the Rata is money spent on a number you will not feel.</p>

<h2>Reading it as a budget</h2>
<p>The honest way to see a transcendence rune is as one guaranteed bonus per item, bought once, never revisited. That makes it excellent at finishing a build and poor at experimenting with one. Settle the build first, then transcend.</p>

<p><em>The <a href="/forgemagie/">forgemagie simulator</a> lists every rune by stat and refuses the ones your item cannot take. Not sure which piece is already final? <a href="/setup/">Solve the build first.</a></em></p>
''',
                },
                'fr': {
                    'title': 'Runes de transcendance : le dernier stat, et le dernier choix',
                    'desc': 'Les runes de transcendance ne ratent jamais, mais elles ne se posent que sur un objet vierge et le verrouillent. Quand en dépenser une, et sur quoi.',
                    'lead': "Une rune de transcendance, c'est la seule forgemagie qui ne peut pas rater. Le prix : elle se pose sur un objet propre et le referme définitivement. C'est donc la dernière décision que tu prends sur une pièce.",
                    'body': '''
<h2>Ce que c'est</h2>
<p>Une rune de transcendance ajoute un bonus à un objet avec <strong>100 % de réussite</strong>. Il en existe 81 sur le client moderne, réparties en trois rangs : Ta, Pata et Rata. Le rang décide de la taille : la Rune Ta Ine donne +10 Intelligence, la Pata Ine +15 et la Rata Ine +20. Presque toutes les lignes utiles y sont : les quatre éléments, la Puissance, la Vitalité, les dommages et les résistances par élément, les dommages critiques, le retrait et la résistance PA et PM, le tacle, la fuite, l'initiative, les pods et les soins.</p>

<h2>Les deux règles qui décident de tout</h2>
<p>Une rune de transcendance ne se pose que sur un objet <strong>jamais forgemagié</strong>. Si la pièce porte déjà un over, la rune la refuse : il faut d'abord retirer l'over. Et une fois la rune posée, l'objet est <strong>verrouillé</strong> : plus aucune forgemagie, jamais. Ni un petit over, ni une retouche, rien.</p>
<p>L'ordre est donc figé. Soit tu forgemagies une pièce et tu ne la transcendes jamais, soit tu la transcendes et tu n'y touches plus. Il n'y a pas de troisième voie.</p>

<h2>Quelle pièce mérite une rune</h2>
<p>Comme l'objet doit être vierge, la cible naturelle est une pièce que tu comptais laisser tranquille : un objet dont les jets sont déjà assez bons, ou un objet dont l'over visé coûte trop cher à courir. Dépenser une rune sur une pièce que tu aurais overée de toute façon, c'est perdre l'over.</p>
<p>Le poids compte aussi. Une Rata est la plus lourde de sa famille, et les runes lourdes sont les chères. Si les +15 d'une Pata comblent le trou dont tu avais vraiment besoin, la Rata est de l'argent mis dans un chiffre que tu ne sentiras pas.</p>

<h2>Le voir comme un budget</h2>
<p>La façon honnête de voir une rune de transcendance : un bonus garanti par objet, acheté une fois, jamais repris. Ça la rend excellente pour finir un build, et mauvaise pour en essayer un. Fige le build d'abord, transcende ensuite.</p>

<p><em>Le <a href="/forgemagie/">simulateur de forgemagie</a> liste chaque rune par caractéristique et refuse celles que ton objet ne peut pas prendre. Tu ne sais pas quelle pièce est déjà définitive ? <a href="/setup/">Calcule le build d'abord.</a></em></p>
''',
                },
                'es': {
                    'title': 'Runas de transcendencia: la última stat, y la última decisión',
                    'desc': 'Las runas de transcendencia nunca fallan, pero solo entran en un objeto virgen y lo bloquean. Cuándo gastar una, y en qué pieza.',
                    'lead': 'Una runa de transcendencia es la única forjamagia que no puede fallar. El precio: entra en un objeto limpio y lo cierra para siempre, así que es la última decisión que tomas sobre esa pieza.',
                    'body': '''
<h2>Qué son</h2>
<p>Una runa de transcendencia añade un bono a un objeto con <strong>100 % de éxito</strong>. Hay 81 en el cliente moderno, repartidas en tres rangos: Ta, Pata y Rata. El rango decide el tamaño: la Runa Ta Ine da +10 de Inteligencia, la Pata Ine +15 y la Rata Ine +20. Están casi todas las líneas útiles: los cuatro elementos, la Potencia, la Vitalidad, los daños y las resistencias por elemento, los daños críticos, la reducción y la resistencia a PA y PM, la placada, la huida, la iniciativa, los pods y las curas.</p>

<h2>Las dos reglas que lo deciden todo</h2>
<p>Una runa de transcendencia solo entra en un objeto <strong>nunca forjamagiado</strong>. Si la pieza ya lleva un over, la runa la rechaza: primero hay que quitar el over. Y una vez puesta la runa, el objeto queda <strong>bloqueado</strong>: nada de forjamagia, nunca más. Ni un over pequeño, ni un retoque, nada.</p>
<p>El orden queda fijo. O forjamagias una pieza y no la transciendes nunca, o la transciendes y no la vuelves a tocar. No hay tercera vía.</p>

<h2>Qué pieza merece una</h2>
<p>Como el objeto tiene que estar limpio, el objetivo natural es una pieza que ibas a dejar en paz: un objeto cuyas tiradas ya son suficientes, o uno cuyo over deseado sale demasiado caro de perseguir. Gastar una runa en una pieza que ibas a overear de todos modos es perder el over.</p>
<p>El peso también cuenta. Una Rata es la más pesada de su familia, y las runas pesadas son las caras. Si los +15 de una Pata tapan el hueco que de verdad necesitabas, la Rata es dinero puesto en una cifra que no vas a notar.</p>

<h2>Verlo como un presupuesto</h2>
<p>La forma honesta de ver una runa de transcendencia: un bono garantizado por objeto, comprado una vez y nunca revisado. Eso la hace excelente para rematar una build y mala para experimentar con ella. Cierra la build primero y transciende después.</p>

<p><em>El <a href="/forgemagie/">simulador de forjamagia</a> lista cada runa por característica y rechaza las que tu objeto no puede aceptar. ¿No sabes qué pieza ya es definitiva? <a href="/setup/">Calcula la build primero.</a></em></p>
''',
                },
                'pt': {
                    'title': 'Runas de transcendência: o último atributo, e a última decisão',
                    'desc': 'As runas de transcendência nunca falham, mas só entram num item virgem e o bloqueiam. Quando gastar uma, e em que peça.',
                    'lead': 'Uma runa de transcendência é a única forjamagia que não pode falhar. O preço: entra num item limpo e fecha-o de vez, por isso é a última decisão que tomas sobre aquela peça.',
                    'body': '''
<h2>O que são</h2>
<p>Uma runa de transcendência acrescenta um bónus a um item com <strong>100 % de sucesso</strong>. Existem 81 no cliente moderno, em três patamares: Ta, Pata e Rata. O patamar decide o tamanho: a Runa Ta Ine dá +10 de Inteligência, a Pata Ine +15 e a Rata Ine +20. Estão lá quase todas as linhas úteis: os quatro elementos, a Potência, a Vitalidade, os danos e as resistências por elemento, os danos críticos, a remoção e a resistência a PA e PM, o bloqueio, a fuga, a iniciativa, os pods e as curas.</p>

<h2>As duas regras que decidem tudo</h2>
<p>Uma runa de transcendência só entra num item <strong>nunca forjamagiado</strong>. Se a peça já leva um over, a runa recusa: é preciso tirar o over primeiro. E assim que a runa entra, o item fica <strong>bloqueado</strong>: nunca mais nenhuma forjamagia. Nem um over pequeno, nem um retoque, nada.</p>
<p>A ordem fica fixa. Ou forjamagias uma peça e nunca a transcendes, ou transcendes e não lhe voltas a tocar. Não há terceira via.</p>

<h2>Que peça merece uma</h2>
<p>Como o item tem de estar limpo, o alvo natural é uma peça que ias deixar em paz: um item cujos valores já chegam, ou um cujo over desejado sai caro demais para perseguir. Gastar uma runa numa peça que ias overar de qualquer forma é perder o over.</p>
<p>O peso também conta. Uma Rata é a mais pesada da sua família, e as runas pesadas são as caras. Se os +15 de uma Pata tapam o buraco de que precisavas mesmo, a Rata é dinheiro posto num número que não vais sentir.</p>

<h2>Vê-la como um orçamento</h2>
<p>A forma honesta de ver uma runa de transcendência: um bónus garantido por item, comprado uma vez e nunca revisto. Isso torna-a excelente para acabar uma build e má para experimentar com ela. Fecha a build primeiro, transcende depois.</p>

<p><em>O <a href="/forgemagie/">simulador de forjamagia</a> lista cada runa por característica e recusa as que o teu item não pode aceitar. Não sabes que peça já é definitiva? <a href="/setup/">Calcula a build primeiro.</a></em></p>
''',
                },
                'de': {
                    'title': 'Transzendenzrunen: der letzte Wert, und die letzte Entscheidung',
                    'desc': 'Transzendenzrunen scheitern nie, gehen aber nur auf ein unberührtes Item und sperren es danach. Wann sich eine lohnt, und auf welchem Teil.',
                    'lead': 'Eine Transzendenzrune ist die einzige Schmiedemagie, die nicht scheitern kann. Der Preis: Sie geht auf ein sauberes Item und schließt es endgültig ab. Sie ist also die letzte Entscheidung für dieses Teil.',
                    'body': '''
<h2>Was sie sind</h2>
<p>Eine Transzendenzrune legt einen Bonus mit <strong>100 % Erfolg</strong> auf ein Item. Auf dem modernen Client gibt es 81 davon, in drei Stufen: Ta, Pata und Rata. Die Stufe bestimmt die Größe: Rune Ta Ine gibt +10 Intelligenz, Pata Ine +15 und Rata Ine +20. Fast jede nützliche Zeile ist dabei: die vier Elemente, Kraft, Vitalität, Schaden und Widerstand je Element, kritischer Schaden, AP und BP Entzug und Widerstand, Fesseln, Ausweichen, Initiative, Pods und Heilung.</p>

<h2>Die zwei Regeln, an denen alles hängt</h2>
<p>Eine Transzendenzrune geht nur auf ein Item, das <strong>nie schmiedemagisch bearbeitet</strong> wurde. Trägt das Teil schon einen Over, verweigert die Rune den Dienst: erst muss der Over runter. Und sobald die Rune sitzt, ist das Item <strong>gesperrt</strong>: keine Schmiedemagie mehr, nie wieder. Kein kleiner Over, keine Korrektur, nichts.</p>
<p>Die Reihenfolge steht damit fest. Entweder du bearbeitest ein Teil schmiedemagisch und transzendierst es nie, oder du transzendierst es und rührst es nicht mehr an. Einen dritten Weg gibt es nicht.</p>

<h2>Welches Teil eine verdient</h2>
<p>Weil das Item sauber sein muss, ist das natürliche Ziel ein Teil, das du ohnehin in Ruhe lassen wolltest: eines, dessen Werte schon reichen, oder eines, dessen gewünschter Over zu teuer zu jagen ist. Eine Rune auf ein Teil zu setzen, das du sowieso geovert hättest, kostet dich den Over.</p>
<p>Auch das Gewicht zählt. Eine Rata ist die schwerste ihrer Familie, und schwere Runen sind die teuren. Wenn die +15 einer Pata die Lücke schließen, die dir wirklich gefehlt hat, ist die Rata Geld in einer Zahl, die du nicht spürst.</p>

<h2>Als Budget lesen</h2>
<p>Ehrlich betrachtet ist eine Transzendenzrune ein garantierter Bonus pro Item, einmal gekauft und nie wieder angefasst. Das macht sie stark zum Abschließen eines Builds und schwach zum Ausprobieren. Erst den Build festzurren, dann transzendieren.</p>

<p><em>Der <a href="/forgemagie/">Schmiedemagie-Simulator</a> listet jede Rune nach Wert und lehnt die ab, die dein Item nicht nehmen kann. Du weißt nicht, welches Teil schon endgültig ist? <a href="/setup/">Rechne zuerst den Build.</a></em></p>
''',
                },
            },
            'touch': {
                'en': {
                    'title': 'Transcendence runes on Dofus Touch: why you will not find them',
                    'desc': 'Dofus Touch has no transcendence runes. Its end game is classic smithmagic with its own rune weights. What that changes for your build.',
                    'lead': 'If you came looking for transcendence runes on Touch, the short answer is that they do not exist here. Touch froze its own branch of the game before that system arrived.',
                    'body': '''
<h2>They are a modern-client system</h2>
<p>Transcendence runes belong to Dofus 3, the beta and Dofus 2. Dofus Touch split off earlier and is balanced on its own, so its smithmagic has no 100% guaranteed rune and no lock. Nothing on Touch closes an item permanently.</p>

<h2>What Touch has instead</h2>
<p>On Touch the end game is classic smithmagic: you push a line with runes, you accept a failure rate, and you can keep going as long as the item survives. That is slower and riskier than a guaranteed bonus, but it is also reversible in a way transcendence never is. A Touch item is never final.</p>

<h2>What it changes for your build</h2>
<p>Practically, it means you can gear first and refine forever. There is no piece you have to leave untouched, and no decision you cannot walk back. Plan your overs around what you can afford to fail, not around a one-shot purchase.</p>

<p><em>The <a href="/touch/forgemagie/">Touch forgemagie simulator</a> uses the Touch rune weights, not the modern ones. Curious how the versions differ? <a href="/guides/versions-explained/">Here is the map.</a></em></p>
''',
                },
                'fr': {
                    'title': 'Runes de transcendance sur Dofus Touch : pourquoi tu ne les trouveras pas',
                    'desc': "Dofus Touch n'a pas de runes de transcendance. Son end game, c'est la forgemagie classique avec ses propres poids. Ce que ça change pour ton build.",
                    'lead': "Si tu cherches les runes de transcendance sur Touch, la réponse courte est qu'elles n'existent pas ici. Touch a gelé sa propre branche du jeu avant l'arrivée de ce système.",
                    'body': '''
<h2>C'est un système du client moderne</h2>
<p>Les runes de transcendance appartiennent à Dofus 3, à la bêta et à Dofus 2. Dofus Touch s'est séparé plus tôt et s'équilibre à part : sa forgemagie n'a aucune rune garantie à 100 % et aucun verrou. Rien, sur Touch, ne referme un objet définitivement.</p>

<h2>Ce que Touch a à la place</h2>
<p>Sur Touch, l'end game c'est la forgemagie classique : tu pousses une ligne à coups de runes, tu acceptes un taux d'échec, et tu peux continuer tant que l'objet tient. C'est plus lent et plus risqué qu'un bonus garanti, mais c'est aussi réversible comme la transcendance ne le sera jamais. Un objet Touch n'est jamais fini.</p>

<h2>Ce que ça change pour ton build</h2>
<p>Concrètement, tu peux t'équiper d'abord et affiner sans fin. Aucune pièce que tu dois laisser vierge, aucune décision sur laquelle tu ne peux pas revenir. Planifie tes overs selon ce que tu peux te permettre de rater, pas selon un achat unique.</p>

<p><em>Le <a href="/touch/forgemagie/">simulateur de forgemagie Touch</a> utilise les poids de runes de Touch, pas ceux du moderne. Tu veux voir ce qui sépare les versions ? <a href="/guides/versions-explained/">La carte est ici.</a></em></p>
''',
                },
                'es': {
                    'title': 'Runas de transcendencia en Dofus Touch: por qué no las vas a encontrar',
                    'desc': 'Dofus Touch no tiene runas de transcendencia. Su end game es la forjamagia clásica con sus propios pesos. Qué cambia eso para tu build.',
                    'lead': 'Si viniste buscando runas de transcendencia en Touch, la respuesta corta es que aquí no existen. Touch congeló su propia rama del juego antes de que llegara ese sistema.',
                    'body': '''
<h2>Es un sistema del cliente moderno</h2>
<p>Las runas de transcendencia son de Dofus 3, de la beta y de Dofus 2. Dofus Touch se separó antes y se equilibra por su cuenta: su forjamagia no tiene ninguna runa garantizada al 100 % ni ningún bloqueo. En Touch nada cierra un objeto para siempre.</p>

<h2>Qué tiene Touch en su lugar</h2>
<p>En Touch el end game es la forjamagia clásica: empujas una línea a base de runas, aceptas un porcentaje de fallo y puedes seguir mientras el objeto aguante. Es más lento y más arriesgado que un bono garantizado, pero también es reversible como la transcendencia nunca lo será. Un objeto de Touch nunca está terminado.</p>

<h2>Qué cambia para tu build</h2>
<p>En la práctica, puedes equiparte primero y pulir sin final. No hay ninguna pieza que debas dejar virgen, ni ninguna decisión sobre la que no puedas volver. Planifica tus overs según lo que puedas permitirte fallar, no según una compra única.</p>

<p><em>El <a href="/touch/forgemagie/">simulador de forjamagia de Touch</a> usa los pesos de runas de Touch, no los modernos. ¿Quieres ver qué separa a las versiones? <a href="/guides/versions-explained/">El mapa está aquí.</a></em></p>
''',
                },
                'pt': {
                    'title': 'Runas de transcendência no Dofus Touch: porque não as vais encontrar',
                    'desc': 'O Dofus Touch não tem runas de transcendência. O seu end game é a forjamagia clássica com pesos próprios. O que isso muda na tua build.',
                    'lead': 'Se vieste à procura de runas de transcendência no Touch, a resposta curta é que aqui não existem. O Touch congelou o seu próprio ramo do jogo antes de esse sistema chegar.',
                    'body': '''
<h2>É um sistema do cliente moderno</h2>
<p>As runas de transcendência são do Dofus 3, da beta e do Dofus 2. O Dofus Touch separou-se antes e é equilibrado à parte: a sua forjamagia não tem nenhuma runa garantida a 100 % nem nenhum bloqueio. No Touch nada fecha um item para sempre.</p>

<h2>O que o Touch tem em vez disso</h2>
<p>No Touch o end game é a forjamagia clássica: empurras uma linha à custa de runas, aceitas uma taxa de falha e podes continuar enquanto o item aguentar. É mais lento e mais arriscado do que um bónus garantido, mas também é reversível como a transcendência nunca será. Um item do Touch nunca está acabado.</p>

<h2>O que muda na tua build</h2>
<p>Na prática, podes equipar-te primeiro e afinar sem fim. Não há nenhuma peça que tenhas de deixar virgem, nem nenhuma decisão sem volta. Planeia os teus overs pelo que podes dar-te ao luxo de falhar, não por uma compra única.</p>

<p><em>O <a href="/touch/forgemagie/">simulador de forjamagia do Touch</a> usa os pesos de runas do Touch, não os modernos. Queres ver o que separa as versões? <a href="/guides/versions-explained/">O mapa está aqui.</a></em></p>
''',
                },
                'de': {
                    'title': 'Transzendenzrunen auf Dofus Touch: warum du sie nicht findest',
                    'desc': 'Dofus Touch hat keine Transzendenzrunen. Sein Endgame ist klassische Schmiedemagie mit eigenen Gewichten. Was das für deinen Build ändert.',
                    'lead': 'Wenn du wegen Transzendenzrunen auf Touch hier bist: Die kurze Antwort ist, dass es sie hier nicht gibt. Touch hat seinen eigenen Zweig des Spiels eingefroren, bevor dieses System kam.',
                    'body': '''
<h2>Ein System des modernen Clients</h2>
<p>Transzendenzrunen gehören zu Dofus 3, zur Beta und zu Dofus 2. Dofus Touch hat sich früher abgespalten und wird getrennt ausbalanciert: Seine Schmiedemagie kennt keine Rune mit 100 % Erfolg und keine Sperre. Auf Touch schließt nichts ein Item endgültig ab.</p>

<h2>Was Touch stattdessen hat</h2>
<p>Auf Touch ist das Endgame klassische Schmiedemagie: Du treibst eine Zeile mit Runen hoch, nimmst eine Fehlerquote in Kauf und kannst weitermachen, solange das Item durchhält. Das ist langsamer und riskanter als ein garantierter Bonus, dafür umkehrbar, wie es Transzendenz nie sein wird. Ein Touch-Item ist nie fertig.</p>

<h2>Was das für deinen Build ändert</h2>
<p>Praktisch heißt das: erst ausrüsten, dann endlos verfeinern. Es gibt kein Teil, das du unberührt lassen musst, und keine Entscheidung ohne Rückweg. Plane deine Over nach dem, was du dir zu verpatzen leisten kannst, nicht nach einem einmaligen Kauf.</p>

<p><em>Der <a href="/touch/forgemagie/">Touch-Schmiedemagie-Simulator</a> nutzt die Runengewichte von Touch, nicht die modernen. Neugierig, was die Versionen trennt? <a href="/guides/versions-explained/">Hier ist die Übersicht.</a></em></p>
''',
                },
            },
            'retro': {
                'en': {
                    'title': 'Transcendence runes on Dofus Retro: they do not exist in 1.29',
                    'desc': 'Dofus Retro is the 1.29 game, from long before transcendence runes. Its smithmagic is the original one. What that means when you gear up.',
                    'lead': 'Transcendence runes are not part of Dofus Retro. The 1.29 client predates them by years, and its smithmagic is the original system, with none of the modern safety nets.',
                    'body': '''
<h2>Retro is the older game, not a lighter one</h2>
<p>Dofus Retro is 1.29, frozen deliberately. Transcendence runes arrived on the modern client long after that point, so there is nothing to look for here: no guaranteed rune, no locked item, no permanent bonus bought in one go.</p>

<h2>What smithmagic is on 1.29</h2>
<p>Retro keeps the original system: runes, a real failure rate, and an item that degrades when you push it too far. Every point above the natural roll is paid for in attempts, and nothing about it is guaranteed. That is the whole game on 1.29, and it is why era gear stays valuable.</p>

<h2>What it means for your build</h2>
<p>Since no bonus is ever locked in, the decision that matters on Retro is which base item to chase, not which rune to finish it with. Get the piece and the rolls right first; the rest is patience.</p>

<p><em>The <a href="/retro/forgemagie/">Retro forgemagie simulator</a> runs on the 1.29 rules. Want the full picture of what separates the versions? <a href="/guides/versions-explained/">Start here.</a></em></p>
''',
                },
                'fr': {
                    'title': "Runes de transcendance sur Dofus Retro : elles n'existent pas en 1.29",
                    'desc': "Dofus Retro, c'est le jeu 1.29, bien avant les runes de transcendance. Sa forgemagie est celle d'origine. Ce que ça implique quand tu t'équipes.",
                    'lead': "Les runes de transcendance ne font pas partie de Dofus Retro. Le client 1.29 leur est antérieur de plusieurs années, et sa forgemagie est le système d'origine, sans aucun des filets modernes.",
                    'body': '''
<h2>Retro est le jeu plus ancien, pas une version allégée</h2>
<p>Dofus Retro, c'est la 1.29, gelée volontairement. Les runes de transcendance sont arrivées sur le client moderne bien après : il n'y a donc rien à chercher ici. Pas de rune garantie, pas d'objet verrouillé, pas de bonus définitif acheté d'un coup.</p>

<h2>Ce qu'est la forgemagie en 1.29</h2>
<p>Retro garde le système d'origine : des runes, un vrai taux d'échec, et un objet qui se dégrade quand tu le pousses trop loin. Chaque point au-dessus du jet naturel se paie en tentatives, et rien n'y est garanti. C'est tout le jeu en 1.29, et c'est pour ça que l'équipement d'époque garde sa valeur.</p>

<h2>Ce que ça veut dire pour ton build</h2>
<p>Comme aucun bonus n'est jamais figé, la décision qui compte sur Retro, c'est quel objet de base courir, pas quelle rune viendra le finir. Trouve la bonne pièce et les bons jets d'abord ; le reste, c'est de la patience.</p>

<p><em>Le <a href="/retro/forgemagie/">simulateur de forgemagie Retro</a> tourne sur les règles 1.29. Tu veux le tableau complet de ce qui sépare les versions ? <a href="/guides/versions-explained/">Commence ici.</a></em></p>
''',
                },
                'es': {
                    'title': 'Runas de transcendencia en Dofus Retro: no existen en 1.29',
                    'desc': 'Dofus Retro es el juego 1.29, mucho antes de las runas de transcendencia. Su forjamagia es la original. Qué implica eso cuando te equipas.',
                    'lead': 'Las runas de transcendencia no forman parte de Dofus Retro. El cliente 1.29 es años anterior, y su forjamagia es el sistema original, sin ninguna de las redes de seguridad modernas.',
                    'body': '''
<h2>Retro es el juego antiguo, no una versión recortada</h2>
<p>Dofus Retro es la 1.29, congelada a propósito. Las runas de transcendencia llegaron al cliente moderno mucho después, así que aquí no hay nada que buscar: ninguna runa garantizada, ningún objeto bloqueado, ningún bono definitivo comprado de una vez.</p>

<h2>Qué es la forjamagia en 1.29</h2>
<p>Retro conserva el sistema original: runas, un porcentaje de fallo real y un objeto que se degrada cuando lo empujas demasiado. Cada punto por encima de la tirada natural se paga en intentos, y nada está garantizado. Ese es todo el juego en 1.29, y por eso el equipo de época mantiene su valor.</p>

<h2>Qué significa para tu build</h2>
<p>Como ningún bono queda fijado nunca, la decisión que importa en Retro es qué objeto base perseguir, no con qué runa rematarlo. Acierta primero con la pieza y con las tiradas; lo demás es paciencia.</p>

<p><em>El <a href="/retro/forgemagie/">simulador de forjamagia de Retro</a> corre con las reglas 1.29. ¿Quieres el cuadro completo de lo que separa a las versiones? <a href="/guides/versions-explained/">Empieza aquí.</a></em></p>
''',
                },
                'pt': {
                    'title': 'Runas de transcendência no Dofus Retro: não existem no 1.29',
                    'desc': 'O Dofus Retro é o jogo 1.29, muito antes das runas de transcendência. A sua forjamagia é a original. O que isso implica quando te equipas.',
                    'lead': 'As runas de transcendência não fazem parte do Dofus Retro. O cliente 1.29 é anterior em vários anos, e a sua forjamagia é o sistema original, sem nenhuma das redes de segurança modernas.',
                    'body': '''
<h2>O Retro é o jogo antigo, não uma versão reduzida</h2>
<p>O Dofus Retro é o 1.29, congelado de propósito. As runas de transcendência chegaram ao cliente moderno muito depois, por isso aqui não há nada a procurar: nenhuma runa garantida, nenhum item bloqueado, nenhum bónus definitivo comprado de uma vez.</p>

<h2>O que é a forjamagia no 1.29</h2>
<p>O Retro mantém o sistema original: runas, uma taxa de falha real e um item que se degrada quando o forças demais. Cada ponto acima do valor natural paga-se em tentativas, e nada é garantido. É esse o jogo todo no 1.29, e é por isso que o equipamento da época mantém o valor.</p>

<h2>O que significa para a tua build</h2>
<p>Como nenhum bónus fica fixo, a decisão que conta no Retro é que item base perseguir, não com que runa o acabar. Acerta primeiro na peça e nos valores; o resto é paciência.</p>

<p><em>O <a href="/retro/forgemagie/">simulador de forjamagia do Retro</a> corre com as regras 1.29. Queres o quadro completo do que separa as versões? <a href="/guides/versions-explained/">Começa aqui.</a></em></p>
''',
                },
                'de': {
                    'title': 'Transzendenzrunen auf Dofus Retro: in 1.29 gibt es sie nicht',
                    'desc': 'Dofus Retro ist das Spiel 1.29, lange vor den Transzendenzrunen. Seine Schmiedemagie ist die ursprüngliche. Was das beim Ausrüsten bedeutet.',
                    'lead': 'Transzendenzrunen gehören nicht zu Dofus Retro. Der Client 1.29 ist Jahre älter, und seine Schmiedemagie ist das ursprüngliche System, ohne die modernen Sicherheitsnetze.',
                    'body': '''
<h2>Retro ist das ältere Spiel, keine abgespeckte Fassung</h2>
<p>Dofus Retro ist 1.29, absichtlich eingefroren. Transzendenzrunen kamen erst lange danach auf den modernen Client, hier gibt es also nichts zu suchen: keine garantierte Rune, kein gesperrtes Item, keinen dauerhaften Bonus auf einen Schlag.</p>

<h2>Was Schmiedemagie in 1.29 ist</h2>
<p>Retro behält das ursprüngliche System: Runen, eine echte Fehlerquote und ein Item, das leidet, wenn du es zu weit treibst. Jeder Punkt über dem natürlichen Wurf wird in Versuchen bezahlt, und garantiert ist nichts. Das ist das ganze Spiel in 1.29, und deshalb behält die Ausrüstung der Epoche ihren Wert.</p>

<h2>Was das für deinen Build bedeutet</h2>
<p>Weil nie ein Bonus festgeschrieben wird, zählt auf Retro die Frage, welchem Grundteil du nachjagst, nicht welche Rune es abschließt. Erst das Teil und die Würfe treffen, der Rest ist Geduld.</p>

<p><em>Der <a href="/retro/forgemagie/">Retro-Schmiedemagie-Simulator</a> läuft nach den Regeln von 1.29. Willst du das ganze Bild der Unterschiede? <a href="/guides/versions-explained/">Fang hier an.</a></em></p>
''',
                },
            },
        },
    },
}



def _lang(code):
    """Normalize a Django language code (e.g. 'fr-fr') to one we ship."""
    if not code:
        return 'en'
    code = code.split('-')[0].lower()
    return code if code in ('en', 'fr', 'es', 'pt', 'de') else 'en'


def ordered_slugs():
    """Every guide slug, hub display order first. ORDER drives the order, but
    a slug missing from it must still be listed everywhere (hub, sitemap):
    the crafting guide shipped unlisted for a morning because only its page
    existed, nothing linked it."""
    return ORDER + [slug for slug in GUIDES if slug not in ORDER]


# A few guides describe a mechanic that is a genuinely different SYSTEM per game
# version (critical hits: Retro's 1/X + Agility vs the modern percentage). Those
# guides carry 'i18n_by_group' instead of 'i18n': one full content per system,
# selected from the version the reader is on. Versions that share a system share
# one canonical page (so distinct systems each rank, without duplicate content).
_DEFAULT_GUIDE_GROUP = 'modern'
_GROUP_CANONICAL_VERSION = {'modern': 'dofus3', 'touch': 'touch',
                            'retro': 'retro'}


def _guide_group(guide, game_version):
    """The content group for a per-version guide, or None when the guide is the
    same across every version."""
    if 'i18n_by_group' not in guide:
        return None
    return (guide.get('version_groups') or {}).get(
        game_version, _DEFAULT_GUIDE_GROUP)


def _guide_i18n(guide, game_version):
    group = _guide_group(guide, game_version)
    return guide['i18n_by_group'][group] if group is not None else guide['i18n']


def _guide_block(guide, lang, game_version):
    by_lang = _guide_i18n(guide, game_version)
    return by_lang.get(lang) or by_lang['en']


def is_version_specific(slug):
    """True when this guide's content depends on the game version."""
    guide = GUIDES.get(slug)
    return bool(guide and 'i18n_by_group' in guide)


def guide_canonical_version(slug, game_version='dofus3'):
    """The version whose URL is canonical for this guide at this version. A plain
    guide is always canonical at the global (dofus3) /guides/ URL; a per-version
    guide is canonical at its system's representative version, so each system is
    one indexable page and versions sharing a system do not duplicate it."""
    guide = GUIDES.get(slug)
    group = _guide_group(guide, game_version) if guide else None
    if group is None:
        return 'dofus3'
    return _GROUP_CANONICAL_VERSION.get(group, 'dofus3')


def canonical_versions(slug):
    """Every distinct version whose URL is a canonical guide page: always dofus3
    (the global /guides/ URL), plus each other system's representative for a
    per-version guide. The sitemap emits one entry per system so both pages get
    discovered and indexed."""
    guide = GUIDES.get(slug)
    if not guide or 'i18n_by_group' not in guide:
        return ['dofus3']
    seen = []
    for version in ('dofus3', 'beta', 'dofus2', 'touch', 'retro'):
        canonical = guide_canonical_version(slug, version)
        if canonical not in seen:
            seen.append(canonical)
    return seen


def list_guides(language_code, game_version='dofus3'):
    """Return [{slug, title, desc}] in display order for a language/version."""
    lang = _lang(language_code)
    out = []
    for slug in ordered_slugs():
        block = _guide_block(GUIDES[slug], lang, game_version)
        out.append({
            'slug': slug,
            'title': block['title'],
            'desc': block['desc'],
        })
    return out


def _version_specific_slugs():
    return [slug for slug in GUIDES if 'i18n_by_group' in GUIDES[slug]]


def _localize_body_links(body, game_version):
    """A body link to a version-specific guide (e.g. critical hits) must keep the
    reader on their version, or a Retro reader would be sent to the modern crit
    page. Rewrite those links to the current version prefix; links to plain,
    global guides are left on /guides/ (they read the same everywhere)."""
    if game_version == 'dofus3':
        return body
    for slug in _version_specific_slugs():
        body = body.replace(
            'href="/guides/%s/"' % slug,
            'href="/%s/guides/%s/"' % (game_version, slug))
    return body


def get_guide(slug, language_code, game_version='dofus3'):
    """Return {slug, title, desc, lead, body} or None if slug unknown."""
    guide = GUIDES.get(slug)
    if not guide:
        return None
    lang = _lang(language_code)
    block = _guide_block(guide, lang, game_version)
    data = {'slug': slug, 'published': guide['published']}
    data.update(block)
    data['body'] = _localize_body_links(data['body'], game_version)
    return data


def iter_content_blocks():
    """Yield (slug, variant, lang, block) for every localized content block,
    covering plain guides (variant None) and per-version guides (variant = the
    group name). Guards and audits iterate this so version-specific content is
    never skipped."""
    for slug, guide in GUIDES.items():
        if 'i18n_by_group' in guide:
            for group, by_lang in guide['i18n_by_group'].items():
                for lang, block in by_lang.items():
                    yield slug, group, lang, block
        else:
            for lang, block in guide['i18n'].items():
                yield slug, None, lang, block
