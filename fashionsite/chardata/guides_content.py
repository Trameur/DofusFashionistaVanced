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

ORDER = ['getting-started', 'how-it-works', 'stats-explained', 'game-modes', 'versions-explained']


GUIDES = {
    # ------------------------------------------------------------------ #
    'getting-started': {
        'i18n': {
            'en': {
                'title': 'Your first Dofus build, step by step',
                'desc': "You picked a class, you're staring at a wall of items, and you have no clue which belt actually fits. Here's how to go from nothing to a full optimized set in a few minutes.",
                'lead': "You picked a class, you're staring at a wall of items, and you have no clue which belt actually fits. That's exactly what the Fashionista is for.",
                'body': '''
<h2>1. Start a project</h2>
<p>Hit <a href="/setup/">Create a project</a>, pick your class, your level and the Dofus version you play. That's the whole setup. If you'd rather not fiddle with anything, two shortcuts get you a build almost instantly:</p>
<ul>
<li><a href="/quickstart/">Quick start</a> — answer three quick questions and you get a set.</li>
<li><a href="/smartbuild/">Smart build</a> — literally describe what you want in plain words ("agility Sram level 200, 11 AP, max range") and it sets things up for you.</li>
</ul>

<h2>2. Tell it what you actually want</h2>
<p>This is where most people overthink it. The wizard gives you sliders: AP, MP, range, the element you hit with, vitality, and so on. You're not entering numbers item by item — you're telling the tool how much each stat is <strong>worth to you</strong>. Want a glass cannon? Crank damage and element, leave vitality low. Doing Kolossium? Push resistance and lock your AP/MP. You can always come back and nudge a slider later.</p>

<h2>3. Read the suggestion (and push back on it)</h2>
<p>The tool spits out a full set — weapon, armor, rings, cloak, dofus, the lot. It won't always be what you pictured, and that's fine. Three things you'll use constantly:</p>
<ul>
<li><strong>Forbid</strong> an item you can't afford or don't have — it'll find the next best thing.</li>
<li><strong>Lock</strong> an item you already own so the build is built around it.</li>
<li><strong>Tailor a new set</strong> after any change to re-run the optimization.</li>
</ul>

<h2>4. Save it, share it, compare it</h2>
<p>Make a free account to keep your projects. Every build gets a share link you can drop in your guild chat, and you can throw two or more builds into the <a href="/choose_compare_sets/">comparison</a> to see them side by side. Simple as that — you're done.</p>

<p><em>New here? The fastest way to learn is to just <a href="/quickstart/">make one build</a> and tweak it.</em></p>
''',
            },
            'fr': {
                'title': 'Ton premier stuff Dofus, étape par étape',
                'desc': "T'as choisi ta classe, t'as une montagne d'items devant les yeux et aucune idée de quelle ceinture coller. Voilà comment passer de zéro à un stuff complet et optimisé en quelques minutes.",
                'lead': "T'as choisi ta classe, t'as une montagne d'items devant les yeux et aucune idée de quelle ceinture coller. C'est exactement à ça que sert la Fashionista.",
                'body': '''
<h2>1. Crée un projet</h2>
<p>Clique sur <a href="/setup/">Créer un projet</a>, choisis ta classe, ton niveau et la version de Dofus que tu joues. C'est toute la config. Et si t'as la flemme de régler quoi que ce soit, deux raccourcis te sortent un stuff quasi instantanément :</p>
<ul>
<li><a href="/quickstart/">Démarrage rapide</a> — trois questions et t'as un set.</li>
<li><a href="/smartbuild/">Build intelligent</a> — tu décris littéralement ce que tu veux en français ("Sram agi niveau 200, 11 PA, portée max") et il te prépare tout.</li>
</ul>

<h2>2. Dis-lui vraiment ce que tu veux</h2>
<p>C'est là que la plupart des gens se prennent la tête pour rien. L'assistant te donne des curseurs : PA, PM, portée, l'élément avec lequel tu tapes, la vita, etc. Tu ne rentres pas les items un par un — tu dis à l'outil combien chaque carac <strong>vaut pour toi</strong>. Tu veux un build full dégâts ? Monte les dégâts et l'élément, laisse la vita en bas. Tu fais du Kolizéum ? Pousse la résistance et verrouille tes PA/PM. Tu pourras toujours revenir bouger un curseur après.</p>

<h2>3. Lis la proposition (et conteste-la)</h2>
<p>L'outil te sort un stuff complet — arme, panoplie, anneaux, cape, dofus, tout. Ça ne sera pas toujours ce que t'avais en tête, et c'est normal. Trois trucs que tu vas utiliser non-stop :</p>
<ul>
<li><strong>Interdire</strong> un item que tu peux pas te payer ou que t'as pas — il te trouvera le suivant.</li>
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
<li><a href="/quickstart/">Inicio rápido</a> — tres preguntas y tienes un set.</li>
<li><a href="/smartbuild/">Build inteligente</a> — describe lo que quieres con tus palabras ("Sram de agilidad nivel 200, 11 PA, alcance máximo") y te lo prepara solo.</li>
</ul>

<h2>2. Dile lo que quieres de verdad</h2>
<p>Aquí es donde la mayoría se complica sin necesidad. El asistente te da deslizadores: PA, PM, alcance, el elemento con el que pegas, vitalidad y demás. No metes los ítems uno a uno: le dices a la herramienta cuánto <strong>vale para ti</strong> cada característica. ¿Quieres un build de cristal? Sube daño y elemento, deja la vita baja. ¿Haces Koliseo? Sube la resistencia y bloquea tus PA/PM. Siempre puedes volver y mover un deslizador después.</p>

<h2>3. Lee la sugerencia (y llévale la contraria)</h2>
<p>La herramienta te saca un set completo — arma, panoplia, anillos, capa, dofus, todo. No siempre será lo que imaginabas, y no pasa nada. Tres cosas que vas a usar todo el rato:</p>
<ul>
<li><strong>Prohibir</strong> un ítem que no te puedes pagar o no tienes — te buscará el siguiente mejor.</li>
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
                'desc': "Você escolheu a classe, tem uma parede de itens na frente e nenhuma ideia de qual cinto encaixa. Veja como sair do zero até um set completo e otimizado em poucos minutos.",
                'lead': "Você escolheu a classe, tem uma parede de itens na frente e nenhuma ideia de qual cinto encaixa de verdade. É exatamente para isso que a Fashionista serve.",
                'body': '''
<h2>1. Crie um projeto</h2>
<p>Clique em <a href="/setup/">Criar um projeto</a>, escolha sua classe, seu nível e a versão de Dofus que você joga. É toda a configuração. E se você estiver com preguiça de ajustar qualquer coisa, dois atalhos entregam um build quase na hora:</p>
<ul>
<li><a href="/quickstart/">Início rápido</a> — três perguntas e você tem um set.</li>
<li><a href="/smartbuild/">Build inteligente</a> — descreva o que você quer com suas palavras ("Sram de agilidade nível 200, 11 PA, alcance máximo") e ele monta tudo pra você.</li>
</ul>

<h2>2. Diga o que você realmente quer</h2>
<p>É aqui que a maioria complica à toa. O assistente te dá controles deslizantes: PA, PM, alcance, o elemento com que você bate, vitalidade e por aí vai. Você não coloca os itens um por um — você diz pra ferramenta quanto cada atributo <strong>vale pra você</strong>. Quer um build de vidro? Aumenta dano e elemento, deixa a vita lá embaixo. Joga Koliseu? Sobe a resistência e trava seus PA/PM. Dá sempre pra voltar e mexer num controle depois.</p>

<h2>3. Leia a sugestão (e discorde dela)</h2>
<p>A ferramenta solta um set completo — arma, conjunto, anéis, capa, dofus, tudo. Nem sempre vai ser o que você imaginou, e tudo bem. Três coisas que você vai usar o tempo todo:</p>
<ul>
<li><strong>Proibir</strong> um item que você não pode pagar ou não tem — ela acha o próximo melhor.</li>
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
                'desc': "Klasse gewählt, eine Wand voller Items vor dir, und keine Ahnung, welcher Gürtel eigentlich passt. So kommst du in ein paar Minuten von null zum fertigen, optimierten Set.",
                'lead': "Klasse gewählt, eine Wand voller Items vor dir, und keine Ahnung, welcher Gürtel eigentlich passt. Genau dafür ist die Fashionista da.",
                'body': '''
<h2>1. Leg ein Projekt an</h2>
<p>Klick auf <a href="/setup/">Projekt erstellen</a>, wähl deine Klasse, dein Level und die Dofus-Version, die du spielst. Mehr Einrichtung gibt's nicht. Und wenn du gar nichts einstellen willst, bringen dich zwei Abkürzungen fast sofort zum Build:</p>
<ul>
<li><a href="/quickstart/">Schnellstart</a> — drei Fragen, fertig ist das Set.</li>
<li><a href="/smartbuild/">Smart Build</a> — beschreib einfach in Worten, was du willst ("Agi-Sram Level 200, 11 AP, maximale Reichweite") und es richtet alles für dich ein.</li>
</ul>

<h2>2. Sag ihm, was du wirklich willst</h2>
<p>Hier machen es sich die meisten unnötig kompliziert. Der Assistent gibt dir Regler: AP, BP, Reichweite, das Element, mit dem du haust, Vitalität und so weiter. Du trägst nicht Item für Item Zahlen ein — du sagst dem Tool, wie viel dir jeder Wert <strong>wert ist</strong>. Glaskanone? Schadens- und Element-Regler hoch, Vita niedrig lassen. Kolosseum? Resistenz hoch und AP/BP fixieren. Du kannst jederzeit zurück und einen Regler nachjustieren.</p>

<h2>3. Lies den Vorschlag (und widersprich ihm)</h2>
<p>Das Tool wirft ein komplettes Set aus — Waffe, Rüstung, Ringe, Umhang, Dofus, alles. Es wird nicht immer das sein, was du dir vorgestellt hast, und das ist okay. Drei Sachen, die du ständig brauchst:</p>
<ul>
<li>Ein Item <strong>verbieten</strong>, das du dir nicht leisten kannst oder nicht hast — es findet das nächstbeste.</li>
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
        'i18n': {
            'en': {
                'title': 'How the optimizer actually works',
                'desc': "Most build sites are a fancy spreadsheet: you drag items in, they add up the stats. The Fashionista works the other way round — you say what you want, it finds the items. Here's what happens under the hood.",
                'lead': "Most build sites are a fancy spreadsheet: you drag items in, they add up the stats. The Fashionista works the other way round — you say what you want, it finds the items.",
                'body': '''
<h2>It's an optimization problem, not a list</h2>
<p>When you set your sliders, you're handing the tool a <strong>score</strong> for every stat. Behind the scenes it then searches through thousands of legal item combinations and picks the one that racks up the highest total score — while respecting the hard rules of the game. That's a genuine mathematical optimization, the same family of math used for scheduling planes or packing trucks, just pointed at your Iop instead.</p>

<h2>Why weighting beats raw stats</h2>
<p>Say intelligence is worth 1 point to you and vitality 0.2. An item with +40 int and +100 vita scores 40 + 20 = 60. An item with +60 int and +30 vita scores 60 + 6 = 66, so it wins — even though it has less vita. Multiply that across twelve slots, set bonuses and dofus, and you get combinations no human bothers to check by hand. That's the whole point: you set the priorities, it does the boring part.</p>

<h2>The rules it never breaks</h2>
<p>Optimizing freely would be easy; optimizing <em>legally</em> is the hard bit. The solver keeps your build inside the lines:</p>
<ul>
<li>AP, MP and range targets you locked.</li>
<li>One item per slot, two different rings, real set bonuses.</li>
<li>Minimum stats you demanded (say "at least 3000 HP").</li>
<li>Items you forbade or locked, and conditions like level or class restrictions.</li>
</ul>

<h2>Why the result sometimes surprises you</h2>
<p>If the suggestion looks weird, it's usually telling you something: your weights are pulling against each other, or there simply isn't gear that hits everything at once. Drop a slider, raise another, forbid that one item you'll never farm, and re-run. After a couple of passes you'll have a set that's genuinely tuned to you — not a copy-paste meta build everyone else is wearing.</p>

<p><em>Want to see it happen? <a href="/setup/">Start a project</a> and watch it solve.</em></p>
''',
            },
            'fr': {
                'title': "Comment l'optimiseur fonctionne vraiment",
                'desc': "La plupart des sites de build, c'est un tableur déguisé : tu glisses des items, ça additionne. La Fashionista fait l'inverse — tu dis ce que tu veux, elle trouve les items. Voilà ce qui se passe sous le capot.",
                'lead': "La plupart des sites de build, c'est un tableur déguisé : tu glisses des items, ça additionne les stats. La Fashionista fait l'inverse — tu dis ce que tu veux, elle trouve les items.",
                'body': '''
<h2>C'est un problème d'optimisation, pas une liste</h2>
<p>Quand tu règles tes curseurs, tu donnes en fait un <strong>score</strong> à chaque carac. En coulisses, l'outil parcourt des milliers de combinaisons d'items valides et garde celle qui cumule le plus gros score total — tout en respectant les règles dures du jeu. C'est de la vraie optimisation mathématique, la même famille de maths qui sert à planifier des avions ou à remplir des camions, juste braquée sur ton Iop.</p>

<h2>Pourquoi pondérer bat les stats brutes</h2>
<p>Mettons que l'intelligence vaut 1 point pour toi et la vita 0,2. Un item +40 intel et +100 vita marque 40 + 20 = 60. Un item +60 intel et +30 vita marque 60 + 6 = 66, donc il gagne — alors qu'il a moins de vita. Multiplie ça sur douze emplacements, les bonus de panoplie et les dofus, et tu obtiens des combinaisons que personne ne s'amuse à vérifier à la main. C'est tout l'intérêt : tu poses les priorités, lui fait la partie chiante.</p>

<h2>Les règles qu'il ne casse jamais</h2>
<p>Optimiser librement, c'est facile ; optimiser <em>légalement</em>, c'est le vrai boulot. Le solveur garde ton build dans les clous :</p>
<ul>
<li>Les objectifs de PA, PM et portée que t'as verrouillés.</li>
<li>Un item par emplacement, deux anneaux différents, les vrais bonus de panoplie.</li>
<li>Les stats minimales que t'as exigées (genre "au moins 3000 PV").</li>
<li>Les items interdits ou verrouillés, et les conditions type niveau ou restriction de classe.</li>
</ul>

<h2>Pourquoi le résultat te surprend parfois</h2>
<p>Si la proposition a l'air bizarre, en général elle te dit quelque chose : tes poids se tirent dessus, ou il n'existe tout simplement pas de stuff qui coche tout d'un coup. Baisse un curseur, monte un autre, interdis cet item que tu farmeras jamais, et relance. Au bout de deux-trois passes, t'as un set vraiment réglé pour toi — pas un build meta copié-collé que tout le monde porte.</p>

<p><em>Envie de voir ça en vrai ? <a href="/setup/">Lance un projet</a> et regarde-le résoudre.</em></p>
''',
            },
            'es': {
                'title': 'Cómo funciona de verdad el optimizador',
                'desc': "La mayoría de las webs de builds son una hoja de cálculo con maquillaje: arrastras ítems y suman. La Fashionista hace lo contrario — tú dices qué quieres y ella encuentra los ítems. Esto es lo que pasa por dentro.",
                'lead': "La mayoría de las webs de builds son una hoja de cálculo con maquillaje: arrastras ítems y suman las estadísticas. La Fashionista hace lo contrario — tú dices qué quieres y ella encuentra los ítems.",
                'body': '''
<h2>Es un problema de optimización, no una lista</h2>
<p>Cuando ajustas los deslizadores, en realidad le das una <strong>puntuación</strong> a cada característica. Por detrás, la herramienta recorre miles de combinaciones de ítems válidas y se queda con la que más puntúa en total — respetando las reglas duras del juego. Es optimización matemática de verdad, la misma familia de mates que sirve para planificar aviones o llenar camiones, solo que apuntando a tu Yopuka.</p>

<h2>Por qué ponderar gana a las estadísticas en bruto</h2>
<p>Pongamos que la inteligencia vale 1 punto para ti y la vitalidad 0,2. Un ítem con +40 inteligencia y +100 vita puntúa 40 + 20 = 60. Uno con +60 inteligencia y +30 vita puntúa 60 + 6 = 66, así que gana — aunque tenga menos vita. Multiplica eso por doce ranuras, bonus de panoplia y dofus, y salen combinaciones que nadie se pone a comprobar a mano. Esa es la gracia: tú pones las prioridades, ella hace lo aburrido.</p>

<h2>Las reglas que nunca rompe</h2>
<p>Optimizar libremente es fácil; optimizar <em>de forma legal</em> es lo difícil. El solucionador mantiene tu build dentro de las líneas:</p>
<ul>
<li>Los objetivos de PA, PM y alcance que bloqueaste.</li>
<li>Un ítem por ranura, dos anillos distintos, bonus de panoplia reales.</li>
<li>Las estadísticas mínimas que exigiste (por ejemplo "al menos 3000 PV").</li>
<li>Los ítems que prohibiste o bloqueaste, y condiciones como nivel o restricción de clase.</li>
</ul>

<h2>Por qué el resultado a veces sorprende</h2>
<p>Si la sugerencia parece rara, normalmente te está diciendo algo: tus pesos tiran unos contra otros, o simplemente no existe equipo que lo cumpla todo a la vez. Baja un deslizador, sube otro, prohíbe ese ítem que no vas a farmear nunca, y vuelve a lanzar. Tras un par de pasadas tendrás un set afinado para ti de verdad — no un build meta copiado que lleva todo el mundo.</p>

<p><em>¿Quieres verlo en acción? <a href="/setup/">Empieza un proyecto</a> y míralo resolver.</em></p>
''',
            },
            'pt': {
                'title': 'Como o otimizador funciona de verdade',
                'desc': "A maioria dos sites de build é uma planilha disfarçada: você arrasta itens e ela soma. A Fashionista faz o contrário — você diz o que quer e ela acha os itens. Veja o que rola por baixo do capô.",
                'lead': "A maioria dos sites de build é uma planilha disfarçada: você arrasta itens e ela soma os atributos. A Fashionista faz o contrário — você diz o que quer e ela acha os itens.",
                'body': '''
<h2>É um problema de otimização, não uma lista</h2>
<p>Quando você ajusta os controles, na real você dá uma <strong>pontuação</strong> pra cada atributo. Por trás, a ferramenta percorre milhares de combinações de itens válidas e fica com a que soma a maior pontuação total — respeitando as regras duras do jogo. É otimização matemática de verdade, a mesma família de matemática que serve pra planejar voos ou encher caminhões, só que apontada pro seu Iop.</p>

<h2>Por que ponderar ganha dos atributos crus</h2>
<p>Digamos que inteligência vale 1 ponto pra você e vitalidade 0,2. Um item com +40 inteligência e +100 vita pontua 40 + 20 = 60. Um com +60 inteligência e +30 vita pontua 60 + 6 = 66, então ganha — mesmo tendo menos vita. Multiplica isso por doze slots, bônus de conjunto e dofus, e saem combinações que ninguém fica conferindo na mão. É essa a sacada: você define as prioridades, ela faz a parte chata.</p>

<h2>As regras que ela nunca quebra</h2>
<p>Otimizar livremente é fácil; otimizar <em>de forma válida</em> é a parte difícil. O solucionador mantém seu build dentro das linhas:</p>
<ul>
<li>As metas de PA, PM e alcance que você travou.</li>
<li>Um item por slot, dois anéis diferentes, bônus de conjunto reais.</li>
<li>Os atributos mínimos que você exigiu (tipo "pelo menos 3000 PV").</li>
<li>Os itens que você proibiu ou travou, e condições como nível ou restrição de classe.</li>
</ul>

<h2>Por que o resultado às vezes surpreende</h2>
<p>Se a sugestão parece estranha, geralmente ela está te dizendo algo: seus pesos estão puxando um contra o outro, ou simplesmente não existe equipamento que cumpra tudo de uma vez. Abaixa um controle, sobe outro, proíbe aquele item que você nunca vai farmar, e roda de novo. Depois de duas ou três passadas você tem um set realmente ajustado pra você — não um build meta copiado que todo mundo usa.</p>

<p><em>Quer ver acontecer? <a href="/setup/">Comece um projeto</a> e veja ele resolver.</em></p>
''',
            },
            'de': {
                'title': 'Wie der Optimierer wirklich arbeitet',
                'desc': "Die meisten Build-Seiten sind eine hübsche Tabelle: Du ziehst Items rein, sie addiert. Die Fashionista macht es andersrum — du sagst, was du willst, sie findet die Items. Hier ist, was unter der Haube passiert.",
                'lead': "Die meisten Build-Seiten sind eine hübsche Tabelle: Du ziehst Items rein, sie addiert die Werte. Die Fashionista macht es andersrum — du sagst, was du willst, sie findet die Items.",
                'body': '''
<h2>Es ist ein Optimierungsproblem, keine Liste</h2>
<p>Wenn du deine Regler einstellst, gibst du dem Tool im Grunde eine <strong>Punktzahl</strong> für jeden Wert. Im Hintergrund durchsucht es dann tausende erlaubte Item-Kombinationen und nimmt die mit der höchsten Gesamtpunktzahl — und hält sich dabei an die harten Regeln des Spiels. Das ist echte mathematische Optimierung, dieselbe Sorte Mathe, mit der man Flüge plant oder Lkw belädt, nur eben auf deinen Iop gerichtet.</p>

<h2>Warum Gewichten besser ist als rohe Werte</h2>
<p>Sagen wir, Intelligenz ist dir 1 Punkt wert und Vitalität 0,2. Ein Item mit +40 Int und +100 Vita kommt auf 40 + 20 = 60. Eins mit +60 Int und +30 Vita kommt auf 60 + 6 = 66, also gewinnt es — obwohl es weniger Vita hat. Rechne das über zwölf Plätze, Set-Boni und Dofus hoch, und du bekommst Kombinationen, die kein Mensch von Hand durchprobiert. Genau das ist der Punkt: Du setzt die Prioritäten, es macht den langweiligen Teil.</p>

<h2>Die Regeln, die es nie bricht</h2>
<p>Frei zu optimieren ist leicht; <em>regelkonform</em> zu optimieren ist die Kunst. Der Solver hält dein Build in der Spur:</p>
<ul>
<li>Die AP-, BP- und Reichweiten-Ziele, die du fixiert hast.</li>
<li>Ein Item pro Platz, zwei verschiedene Ringe, echte Set-Boni.</li>
<li>Die Mindestwerte, die du verlangt hast (etwa "mindestens 3000 LP").</li>
<li>Items, die du verboten oder gesperrt hast, und Bedingungen wie Level oder Klassenbeschränkung.</li>
</ul>

<h2>Warum dich das Ergebnis manchmal überrascht</h2>
<p>Wenn der Vorschlag seltsam aussieht, sagt er dir meistens etwas: Deine Gewichte ziehen gegeneinander, oder es gibt schlicht keine Ausrüstung, die alles auf einmal trifft. Regler runter, anderen hoch, das Item verbieten, das du eh nie farmst, und neu rechnen. Nach zwei, drei Durchläufen hast du ein Set, das wirklich auf dich abgestimmt ist — kein kopiertes Meta-Build, das alle anderen tragen.</p>

<p><em>Willst du es live sehen? <a href="/setup/">Starte ein Projekt</a> und schau ihm beim Lösen zu.</em></p>
''',
            },
        },
    },

    # ------------------------------------------------------------------ #
    'stats-explained': {
        'i18n': {
            'en': {
                'title': 'Dofus stats, and how much each one is worth',
                'desc': "AP, range, masteries, vitality, crits… Dofus throws a lot of numbers at you. Here's a no-nonsense rundown of what actually matters and how to weight it in a build.",
                'lead': "AP, range, masteries, vitality, crits… Dofus throws a lot of numbers at you. Here's a no-nonsense rundown of what actually matters and how to weight it.",
                'body': '''
<h2>The kingmakers: AP, MP and range</h2>
<p>These three decide what your character can even do on a turn. One more AP can mean a whole extra spell; one more MP is positioning and kiting; range makes or breaks half the classes in the game. They're scarce, every build fights over them, so in the tool you usually <strong>lock them to a target</strong> rather than weight them — "give me exactly 11 AP and 6 MP, then optimize the rest."</p>

<h2>Your element and mastery</h2>
<p>Your damage comes from one (or more) of Strength, Intelligence, Agility and Chance, paired with the matching elemental mastery. Pick the element your main spells scale with and lean into it — a focused mono-element build almost always out-damages a smeared multi-element one. Since the 3.6 characteristic rework, masteries carry even more of the weight, so they deserve a high slider on any damage build.</p>

<h2>Staying alive</h2>
<p>Vitality is raw HP and it's cheap to stack, but more isn't always better — 1000 extra HP you didn't need is a damage stat you threw away. Resistance (flat and %) is what actually keeps you up in PvP and tough fights. For Kolossium, weight resistance seriously; for mobbing PvM, you can often get away with less.</p>

<h2>The multipliers: Power, Damage, Crit</h2>
<p>Power boosts all your elemental damage at once and is almost always worth a high weight. Flat Damage (+dmg) is strongest on multi-hit, low-base spells; % damage scales with big hits. Critical hit rate is great <em>if</em> your crits actually add a meaningful bonus — check the spell before you chase it.</p>

<h2>The quiet ones: Wisdom, Prospecting, Initiative, Pods</h2>
<p>Not every build is about damage. Wisdom = XP and resistance to AP/MP loss; Prospecting = drop rate, gold for farmers; Initiative decides turn order; Pods are pure convenience. Give them a small weight when they matter to you and zero when they don't — the optimizer will only chase them if there's no real cost.</p>

<h2>The one rule</h2>
<p>Don't max everything. If every slider is at the top, you've told the tool that nothing matters, which is the same as telling it nothing. Pick your two or three real priorities, weight those high, and let the rest fall where it lands.</p>

<p><em>Ready to put numbers on it? <a href="/setup/">Build it here.</a></em></p>
''',
            },
            'fr': {
                'title': 'Les stats de Dofus, et combien chacune vaut',
                'desc': "PA, portée, maîtrises, vitalité, coups critiques… Dofus te balance un paquet de chiffres. Voilà un topo sans blabla sur ce qui compte vraiment et comment le pondérer dans un build.",
                'lead': "PA, portée, maîtrises, vitalité, coups critiques… Dofus te balance un paquet de chiffres. Voilà un topo sans blabla sur ce qui compte vraiment et comment le pondérer.",
                'body': '''
<h2>Les rois : PA, PM et portée</h2>
<p>Ces trois-là décident de ce que ton perso peut faire dans un tour, point. Un PA de plus, c'est parfois un sort entier en rab ; un PM de plus, c'est du placement et du kite ; la portée fait ou défait la moitié des classes du jeu. C'est rare, tous les builds se les arrachent, donc dans l'outil tu les <strong>verrouilles à un objectif</strong> plutôt que de les pondérer — "donne-moi exactement 11 PA et 6 PM, puis optimise le reste".</p>

<h2>Ton élément et ta maîtrise</h2>
<p>Tes dégâts viennent d'un (ou plusieurs) parmi Force, Intelligence, Agilité et Chance, couplés à la maîtrise élémentaire correspondante. Choisis l'élément sur lequel scalent tes sorts principaux et fonce dessus — un build mono-élément concentré tape presque toujours plus fort qu'un build multi-élément dilué. Depuis la refonte des caracs 3.6, les maîtrises pèsent encore plus lourd, donc elles méritent un gros curseur sur tout build dégâts.</p>

<h2>Rester en vie</h2>
<p>La vitalité, c'est des PV bruts et ça s'empile pas cher, mais plus n'est pas toujours mieux — 1000 PV en trop dont t'avais pas besoin, c'est une stat de dégâts jetée à la poubelle. La résistance (fixe et %) c'est ce qui te garde debout en PvP et dans les combats velus. Pour le Kolizéum, pondère la résistance sérieusement ; en PvM de mob, tu peux souvent t'en passer un peu.</p>

<h2>Les multiplicateurs : Puissance, Dommages, Critique</h2>
<p>La Puissance booste tous tes dégâts élémentaires d'un coup et mérite presque toujours un gros poids. Les Dommages fixes (+dom) sont rois sur les sorts multi-coups à faible base ; les dégâts en % scalent avec les gros coups. Le taux de critique est top <em>si</em> tes crits ajoutent vraiment un bonus qui compte — vérifie le sort avant de courir après.</p>

<h2>Les discrètes : Sagesse, Prospection, Initiative, Pods</h2>
<p>Tous les builds ne tournent pas autour des dégâts. Sagesse = XP et résistance à la perte de PA/PM ; Prospection = taux de drop, kamas pour les farmeurs ; l'Initiative décide de l'ordre des tours ; les Pods, c'est du confort pur. Mets-leur un petit poids quand ça t'importe et zéro sinon — l'optimiseur ne les chassera que si ça ne coûte rien.</p>

<h2>La seule règle</h2>
<p>Ne monte pas tout à fond. Si tous les curseurs sont au max, t'as dit à l'outil que rien ne compte, ce qui revient à ne rien lui dire. Choisis tes deux-trois vraies priorités, pondère-les haut, et laisse le reste tomber où il tombe.</p>

<p><em>Prêt à mettre des chiffres dessus ? <a href="/setup/">Construis-le ici.</a></em></p>
''',
            },
            'es': {
                'title': 'Las estadísticas de Dofus y cuánto vale cada una',
                'desc': "PA, alcance, dominios, vitalidad, críticos… Dofus te tira un montón de números. Aquí va un repaso sin rodeos de lo que importa de verdad y cómo ponderarlo en un build.",
                'lead': "PA, alcance, dominios, vitalidad, críticos… Dofus te tira un montón de números. Aquí va un repaso sin rodeos de lo que importa de verdad y cómo ponderarlo.",
                'body': '''
<h2>Los que mandan: PA, PM y alcance</h2>
<p>Estos tres deciden lo que tu personaje puede hacer en un turno, y punto. Un PA más a veces es un hechizo entero extra; un PM más es colocación y kiteo; el alcance hace o deshace a la mitad de las clases del juego. Son escasos, todos los builds se pelean por ellos, así que en la herramienta normalmente los <strong>bloqueas a un objetivo</strong> en vez de ponderarlos — "dame exactamente 11 PA y 6 PM, y luego optimiza el resto".</p>

<h2>Tu elemento y tu dominio</h2>
<p>Tu daño sale de uno (o varios) entre Fuerza, Inteligencia, Agilidad y Suerte, junto con el dominio elemental correspondiente. Elige el elemento con el que escalan tus hechizos principales y ve a por él — un build monoelemento concentrado casi siempre pega más que uno multielemento diluido. Desde el rework de características de 3.6, los dominios pesan aún más, así que merecen un deslizador alto en cualquier build de daño.</p>

<h2>Seguir vivo</h2>
<p>La vitalidad son PV en bruto y apilarla es barato, pero más no siempre es mejor — 1000 PV de más que no necesitabas es una estadística de daño tirada a la basura. La resistencia (fija y %) es lo que de verdad te mantiene en pie en PvP y en peleas duras. Para el Koliseo, pondera la resistencia en serio; en PvM de mobeo, muchas veces puedes ir con menos.</p>

<h2>Los multiplicadores: Potencia, Daños, Crítico</h2>
<p>La Potencia sube todo tu daño elemental de golpe y casi siempre merece un peso alto. Los Daños fijos (+daño) brillan en hechizos multigolpe de base baja; el daño en % escala con los golpazos. La tasa de crítico es genial <em>si</em> tus críticos suman un bonus que de verdad cuenta — mira el hechizo antes de ir a por ella.</p>

<h2>Las calladas: Sabiduría, Prospección, Iniciativa, Pods</h2>
<p>No todos los builds van de daño. Sabiduría = XP y resistencia a la pérdida de PA/PM; Prospección = tasa de drop, kamas para farmers; la Iniciativa decide el orden de turnos; los Pods son comodidad pura. Dales un peso pequeño cuando te importan y cero cuando no — el optimizador solo irá a por ellos si no cuesta nada.</p>

<h2>La única regla</h2>
<p>No lo subas todo al máximo. Si todos los deslizadores están arriba, le has dicho a la herramienta que nada importa, que es lo mismo que no decirle nada. Elige tus dos o tres prioridades reales, ponderalas alto, y deja que el resto caiga donde caiga.</p>

<p><em>¿Listo para ponerle números? <a href="/setup/">Constrúyelo aquí.</a></em></p>
''',
            },
            'pt': {
                'title': 'Os atributos de Dofus e quanto cada um vale',
                'desc': "PA, alcance, domínios, vitalidade, críticos… Dofus joga um monte de números em você. Aqui vai um resumo sem enrolação do que importa de verdade e como ponderar num build.",
                'lead': "PA, alcance, domínios, vitalidade, críticos… Dofus joga um monte de números em você. Aqui vai um resumo sem enrolação do que importa de verdade e como ponderar.",
                'body': '''
<h2>Os que mandam: PA, PM e alcance</h2>
<p>Esses três decidem o que seu personagem consegue fazer num turno, ponto. Um PA a mais às vezes é um feitiço inteiro extra; um PM a mais é posicionamento e kite; o alcance faz ou quebra metade das classes do jogo. São escassos, todo build briga por eles, então na ferramenta você geralmente os <strong>trava num objetivo</strong> em vez de ponderar — "me dá exatamente 11 PA e 6 PM, e depois otimiza o resto".</p>

<h2>Seu elemento e seu domínio</h2>
<p>Seu dano vem de um (ou mais) entre Força, Inteligência, Agilidade e Sorte, junto com o domínio elemental correspondente. Escolha o elemento com que seus feitiços principais escalam e vá fundo nele — um build mono-elemento concentrado quase sempre bate mais que um multi-elemento diluído. Desde a reformulação de características da 3.6, os domínios pesam ainda mais, então merecem um controle alto em qualquer build de dano.</p>

<h2>Continuar vivo</h2>
<p>Vitalidade é PV cru e empilhar é barato, mas mais nem sempre é melhor — 1000 PV a mais de que você não precisava é um atributo de dano jogado fora. Resistência (fixa e %) é o que de fato te mantém em pé no PvP e em lutas pesadas. Pro Koliseu, pondere resistência a sério; em PvM de mob, muitas vezes dá pra ir com menos.</p>

<h2>Os multiplicadores: Potência, Danos, Crítico</h2>
<p>A Potência aumenta todo o seu dano elemental de uma vez e quase sempre merece um peso alto. Danos fixos (+dano) brilham em feitiços multi-golpe de base baixa; dano em % escala com golpes grandes. A taxa de crítico é ótima <em>se</em> seus críticos somam um bônus que conta de verdade — confira o feitiço antes de correr atrás.</p>

<h2>Os quietos: Sabedoria, Prospecção, Iniciativa, Pods</h2>
<p>Nem todo build é sobre dano. Sabedoria = XP e resistência à perda de PA/PM; Prospecção = taxa de drop, kamas pros farmers; a Iniciativa decide a ordem dos turnos; os Pods são puro conforto. Dê um peso pequeno quando importam e zero quando não — o otimizador só vai atrás deles se não custar nada.</p>

<h2>A única regra</h2>
<p>Não suba tudo no máximo. Se todos os controles estão no topo, você disse pra ferramenta que nada importa, o que é o mesmo que não dizer nada. Escolha suas duas ou três prioridades reais, pondere alto, e deixe o resto cair onde cair.</p>

<p><em>Pronto pra colocar números nisso? <a href="/setup/">Monte aqui.</a></em></p>
''',
            },
            'de': {
                'title': 'Dofus-Werte und wie viel jeder wert ist',
                'desc': "AP, Reichweite, Beherrschungen, Vitalität, Kritische… Dofus wirft dir eine Menge Zahlen hin. Hier ist ein klarer Überblick, was wirklich zählt und wie du es im Build gewichtest.",
                'lead': "AP, Reichweite, Beherrschungen, Vitalität, Kritische… Dofus wirft dir eine Menge Zahlen hin. Hier ist ein klarer Überblick, was wirklich zählt und wie du es gewichtest.",
                'body': '''
<h2>Die Königsmacher: AP, BP und Reichweite</h2>
<p>Diese drei entscheiden, was deine Figur in einer Runde überhaupt tun kann. Ein AP mehr ist manchmal ein ganzer zusätzlicher Zauber; ein BP mehr ist Positionierung und Kiten; Reichweite macht oder bricht die Hälfte der Klassen im Spiel. Sie sind knapp, jedes Build kämpft darum, deshalb <strong>fixierst</strong> du sie im Tool meist auf ein Ziel, statt sie zu gewichten — "gib mir genau 11 AP und 6 BP, dann optimiere den Rest".</p>

<h2>Dein Element und deine Beherrschung</h2>
<p>Dein Schaden kommt aus einem (oder mehreren) von Stärke, Intelligenz, Beweglichkeit und Glück, zusammen mit der passenden Elementarbeherrschung. Wähl das Element, mit dem deine Hauptzauber skalieren, und zieh es durch — ein fokussiertes Mono-Element-Build macht fast immer mehr Schaden als ein verwässertes Multi-Element-Build. Seit dem Charakterwerte-Rework in 3.6 wiegen Beherrschungen noch schwerer, also verdienen sie in jedem Schadens-Build einen hohen Regler.</p>

<h2>Am Leben bleiben</h2>
<p>Vitalität ist rohes LP und billig zu stapeln, aber mehr ist nicht immer besser — 1000 LP zu viel, die du nicht gebraucht hast, sind ein weggeworfener Schadenswert. Resistenz (fix und %) ist das, was dich in PvP und harten Kämpfen wirklich oben hält. Fürs Kolosseum gewichte Resistenz ernsthaft; beim Mob-PvM kommst du oft mit weniger aus.</p>

<h2>Die Multiplikatoren: Stärke (Power), Schaden, Kritisch</h2>
<p>Power hebt deinen gesamten Elementarschaden auf einmal und verdient fast immer ein hohes Gewicht. Fixer Schaden (+Schaden) ist am stärksten bei Multi-Treffer-Zaubern mit niedriger Basis; %-Schaden skaliert mit großen Treffern. Kritische Trefferrate ist super, <em>wenn</em> deine Kritischen wirklich einen spürbaren Bonus draufpacken — schau den Zauber an, bevor du ihr hinterherjagst.</p>

<h2>Die Leisen: Weisheit, Prospektion, Initiative, Trageleistung</h2>
<p>Nicht jedes Build dreht sich um Schaden. Weisheit = EP und Widerstand gegen AP/BP-Verlust; Prospektion = Drop-Rate, Kamas für Farmer; Initiative entscheidet die Zugreihenfolge; Trageleistung ist purer Komfort. Gib ihnen ein kleines Gewicht, wenn sie dir wichtig sind, und null, wenn nicht — der Optimierer jagt ihnen nur nach, wenn es nichts kostet.</p>

<h2>Die eine Regel</h2>
<p>Stell nicht alles auf Maximum. Wenn jeder Regler oben ist, hast du dem Tool gesagt, dass nichts zählt — und das ist dasselbe, wie ihm gar nichts zu sagen. Wähl deine zwei, drei echten Prioritäten, gewichte die hoch, und lass den Rest fallen, wo er fällt.</p>

<p><em>Bereit, Zahlen draufzulegen? <a href="/setup/">Bau es hier.</a></em></p>
''',
            },
        },
    },

    # ------------------------------------------------------------------ #
    'versions-explained': {
        'i18n': {
            'en': {
                'title': 'Dofus 3, Beta, Dofus 2, Retro, Touch — which one are you on?',
                'desc': "One thing that sets the Fashionista apart: it covers five flavors of Dofus, not just the live one. Here's what each is, who plays it, and how to switch.",
                'lead': "One thing that sets the Fashionista apart: it covers five flavors of Dofus, not just the live one. Here's the quick map so you optimize on the right data.",
                'body': '''
<h2>Why this even matters</h2>
<p>Item stats, recipes and spells are different across versions. A build that's perfect on the live game can be nonsense on Retro, where half the items don't exist and the rules are old-school. So the first thing to get right is: which version are you actually playing? Pick it when you create a project, or switch any time with the version selector at the top of the page.</p>

<h2>Dofus 3 (live)</h2>
<p>The current game. This is the default, kept up to date with the latest patch — including the 3.6 characteristic rework and the newest items. If you just play Dofus on a regular server, this is you.</p>

<h2>Beta</h2>
<p>The test server, where Ankama trials upcoming changes before they go live. Handy if you want to plan a build around what's coming. Just remember the data moves around and can change overnight — it's a preview, not gospel.</p>

<h2>Dofus 2</h2>
<p>The classic 2.x era many players still think of as "real" Dofus. Different item pool and balance from Dofus 3, so it gets its own dataset.</p>

<h2>Retro (1.29)</h2>
<p>Dofus Retro — the old-school 1.29 servers. Way fewer items, no elemental damage runes, simpler everything. The optimizer knows the 1.29 rules, so it won't suggest gear or stats that didn't exist back then.</p>

<h2>Touch</h2>
<p>Dofus Touch, the mobile version, which sits on its own balance and item list (some trophies, for instance, cap set bonuses differently). Its own dataset too, so your mobile builds are accurate.</p>

<p><em>On the right version? <a href="/setup/">Create your project</a> and the tool only shows what exists there.</em></p>
''',
            },
            'fr': {
                'title': 'Dofus 3, Bêta, Dofus 2, Retro, Touch — tu joues à laquelle ?',
                'desc': "Un truc qui distingue la Fashionista : elle couvre cinq versions de Dofus, pas juste la live. Voilà ce qu'est chacune, qui y joue, et comment switcher.",
                'lead': "Un truc qui distingue la Fashionista : elle couvre cinq versions de Dofus, pas juste la live. Voilà la carte rapide pour optimiser sur les bonnes données.",
                'body': '''
<h2>Pourquoi ça compte</h2>
<p>Les stats des items, les recettes et les sorts changent d'une version à l'autre. Un build parfait sur la live peut être n'importe quoi sur Retro, où la moitié des items n'existe pas et où les règles sont à l'ancienne. Donc le premier truc à caler, c'est : tu joues à quelle version, vraiment ? Choisis-la en créant ton projet, ou change quand tu veux avec le sélecteur de version en haut de la page.</p>

<h2>Dofus 3 (live)</h2>
<p>Le jeu actuel. C'est le défaut, tenu à jour avec le dernier patch — refonte des caracs 3.6 et derniers items inclus. Si tu joues juste à Dofus sur un serveur classique, c'est toi.</p>

<h2>Bêta</h2>
<p>Le serveur de test, là où Ankama essaie les changements à venir avant qu'ils passent en live. Pratique pour préparer un build autour de ce qui arrive. Garde juste en tête que la donnée bouge et peut changer du jour au lendemain — c'est un aperçu, pas parole d'évangile.</p>

<h2>Dofus 2</h2>
<p>L'ère classique 2.x que beaucoup considèrent encore comme le "vrai" Dofus. Pool d'items et équilibrage différents de Dofus 3, donc elle a son propre jeu de données.</p>

<h2>Retro (1.29)</h2>
<p>Dofus Retro — les serveurs 1.29 à l'ancienne. Beaucoup moins d'items, pas de runes de dégâts élémentaires, tout plus simple. L'optimiseur connaît les règles 1.29, donc il ne te proposera pas un stuff ou des stats qui n'existaient pas à l'époque.</p>

<h2>Touch</h2>
<p>Dofus Touch, la version mobile, avec son propre équilibrage et sa propre liste d'items (certains trophées, par exemple, plafonnent les bonus de panoplie différemment). Son propre jeu de données aussi, pour que tes builds mobile soient justes.</p>

<p><em>Sur la bonne version ? <a href="/setup/">Crée ton projet</a> et l'outil n'affiche que ce qui existe là-bas.</em></p>
''',
            },
            'es': {
                'title': 'Dofus 3, Beta, Dofus 2, Retro, Touch — ¿en cuál juegas?',
                'desc': "Algo que distingue a la Fashionista: cubre cinco versiones de Dofus, no solo la live. Aquí tienes qué es cada una, quién la juega y cómo cambiar.",
                'lead': "Algo que distingue a la Fashionista: cubre cinco versiones de Dofus, no solo la live. Aquí va el mapa rápido para que optimices con los datos correctos.",
                'body': '''
<h2>Por qué importa</h2>
<p>Las estadísticas de los ítems, las recetas y los hechizos cambian entre versiones. Un build perfecto en la live puede ser un disparate en Retro, donde la mitad de los ítems no existe y las reglas son a la antigua. Así que lo primero que hay que acertar es: ¿en qué versión juegas de verdad? Elígela al crear el proyecto, o cámbiala cuando quieras con el selector de versión arriba.</p>

<h2>Dofus 3 (live)</h2>
<p>El juego actual. Es la opción por defecto, al día con el último parche — incluido el rework de características de 3.6 y los ítems más nuevos. Si juegas a Dofus en un servidor normal, esta eres tú.</p>

<h2>Beta</h2>
<p>El servidor de pruebas, donde Ankama ensaya los cambios que vienen antes de que lleguen a la live. Útil para planear un build alrededor de lo que viene. Solo recuerda que los datos se mueven y pueden cambiar de un día para otro — es un adelanto, no una verdad absoluta.</p>

<h2>Dofus 2</h2>
<p>La era clásica 2.x que muchos siguen considerando el "Dofus de verdad". Conjunto de ítems y balance distintos de Dofus 3, así que tiene su propio set de datos.</p>

<h2>Retro (1.29)</h2>
<p>Dofus Retro — los servidores 1.29 de la vieja escuela. Muchos menos ítems, sin runas de daño elemental, todo más simple. El optimizador conoce las reglas de 1.29, así que no te sugerirá equipo ni estadísticas que no existían entonces.</p>

<h2>Touch</h2>
<p>Dofus Touch, la versión móvil, con su propio balance y lista de ítems (algunos trofeos, por ejemplo, limitan los bonus de panoplia de otra forma). También con su propio set de datos, para que tus builds de móvil sean exactos.</p>

<p><em>¿En la versión correcta? <a href="/setup/">Crea tu proyecto</a> y la herramienta solo mostrará lo que existe ahí.</em></p>
''',
            },
            'pt': {
                'title': 'Dofus 3, Beta, Dofus 2, Retro, Touch — em qual você joga?',
                'desc': "Uma coisa que diferencia a Fashionista: ela cobre cinco versões de Dofus, não só a live. Veja o que é cada uma, quem joga e como trocar.",
                'lead': "Uma coisa que diferencia a Fashionista: ela cobre cinco versões de Dofus, não só a live. Aqui vai o mapa rápido pra você otimizar com os dados certos.",
                'body': '''
<h2>Por que isso importa</h2>
<p>Os atributos dos itens, as receitas e os feitiços mudam de uma versão pra outra. Um build perfeito na live pode ser uma furada no Retro, onde metade dos itens não existe e as regras são old-school. Então a primeira coisa a acertar é: em qual versão você joga de verdade? Escolha ao criar o projeto, ou troque quando quiser no seletor de versão no topo da página.</p>

<h2>Dofus 3 (live)</h2>
<p>O jogo atual. É o padrão, mantido em dia com o último patch — incluindo a reformulação de características da 3.6 e os itens mais novos. Se você joga Dofus num servidor normal, é você.</p>

<h2>Beta</h2>
<p>O servidor de testes, onde a Ankama experimenta as mudanças que vêm aí antes de irem pra live. Útil pra planejar um build em torno do que está chegando. Só lembre que os dados mudam e podem virar de uma hora pra outra — é uma prévia, não verdade absoluta.</p>

<h2>Dofus 2</h2>
<p>A era clássica 2.x que muita gente ainda considera o "Dofus de verdade". Conjunto de itens e balanceamento diferentes da Dofus 3, então tem seu próprio conjunto de dados.</p>

<h2>Retro (1.29)</h2>
<p>Dofus Retro — os servidores 1.29 da velha escola. Muito menos itens, sem runas de dano elemental, tudo mais simples. O otimizador conhece as regras da 1.29, então não vai sugerir equipamento nem atributos que não existiam na época.</p>

<h2>Touch</h2>
<p>Dofus Touch, a versão mobile, com seu próprio balanceamento e lista de itens (alguns troféus, por exemplo, limitam os bônus de conjunto de outro jeito). Também com seu próprio conjunto de dados, pra seus builds de celular saírem certos.</p>

<p><em>Na versão certa? <a href="/setup/">Crie seu projeto</a> e a ferramenta só mostra o que existe ali.</em></p>
''',
            },
            'de': {
                'title': 'Dofus 3, Beta, Dofus 2, Retro, Touch — welches spielst du?',
                'desc': "Eine Sache hebt die Fashionista ab: Sie deckt fünf Spielarten von Dofus ab, nicht nur die Live-Version. Hier ist, was jede ist, wer sie spielt und wie du umschaltest.",
                'lead': "Eine Sache hebt die Fashionista ab: Sie deckt fünf Spielarten von Dofus ab, nicht nur die Live-Version. Hier ist die schnelle Übersicht, damit du mit den richtigen Daten optimierst.",
                'body': '''
<h2>Warum das überhaupt wichtig ist</h2>
<p>Item-Werte, Rezepte und Zauber unterscheiden sich zwischen den Versionen. Ein Build, das auf dem Live-Spiel perfekt ist, kann auf Retro Unsinn sein, wo die Hälfte der Items nicht existiert und die Regeln altmodisch sind. Das Erste, was du richtig setzen musst, ist also: Welche Version spielst du eigentlich? Wähl sie beim Anlegen eines Projekts, oder wechsle jederzeit mit der Versionsauswahl oben auf der Seite.</p>

<h2>Dofus 3 (live)</h2>
<p>Das aktuelle Spiel. Das ist die Voreinstellung, auf dem neuesten Patch gehalten — inklusive Charakterwerte-Rework der 3.6 und der neuesten Items. Wenn du einfach Dofus auf einem normalen Server spielst, bist das du.</p>

<h2>Beta</h2>
<p>Der Testserver, auf dem Ankama kommende Änderungen ausprobiert, bevor sie live gehen. Praktisch, um ein Build um das zu planen, was kommt. Denk nur dran, dass sich die Daten verschieben und über Nacht ändern können — es ist eine Vorschau, kein Evangelium.</p>

<h2>Dofus 2</h2>
<p>Die klassische 2.x-Ära, die viele immer noch als das "echte" Dofus sehen. Anderer Item-Pool und Balance als Dofus 3, also bekommt es seinen eigenen Datensatz.</p>

<h2>Retro (1.29)</h2>
<p>Dofus Retro — die altmodischen 1.29-Server. Viel weniger Items, keine Elementarschaden-Runen, alles simpler. Der Optimierer kennt die 1.29-Regeln und schlägt dir daher keine Ausrüstung oder Werte vor, die es damals nicht gab.</p>

<h2>Touch</h2>
<p>Dofus Touch, die mobile Version, mit eigener Balance und Item-Liste (manche Trophäen deckeln zum Beispiel Set-Boni anders). Ebenfalls mit eigenem Datensatz, damit deine Mobile-Builds stimmen.</p>

<p><em>Auf der richtigen Version? <a href="/setup/">Erstell dein Projekt</a> und das Tool zeigt nur, was es dort gibt.</em></p>
''',
            },
        },
    },

    # ------------------------------------------------------------------ #
    'game-modes': {
        'i18n': {
            'en': {
                'title': "Building for PvM, PvP and Kolossium",
                'desc': "The same character needs a different build depending on whether you're farming dungeons, dueling, or grinding Kolossium. Here's how to weight each one without rebuilding from scratch.",
                'lead': "The same character needs a different build depending on whether you're farming dungeons, dueling, or grinding Kolossium. Same items, different priorities — here's how to weight each.",
                'body': '''
<h2>Why one build isn't enough</h2>
<p>Your gear doesn't change, but what you ask of it does. A PvM farm set wants to delete monsters before they matter; a Kolossium set wants to still be standing on turn ten. Pour the same items into both and you'll be mediocre at each. The trick isn't owning three stuffs — it's telling the optimizer what <strong>this</strong> set is for and saving it as its own project.</p>

<h2>PvM: kill fast, survive enough</h2>
<p>Against monsters you usually know the fight, so you can lean into offense. Weight your element and Power high, push flat and percent damage, and keep just enough vitality and resistance to clear the dungeon you actually run. No opponent is reading your build, so dumping defensive stats for raw damage is often correct. Lock your AP, MP and range to hit your spell combo, then let the tool pour everything else into killing power.</p>

<h2>PvP and Kolossium: resistance wins games</h2>
<p>Now someone is actively trying to ruin your turn. Flat and percent resistance jump to the top of your weights — surviving a burst is worth more than a slightly bigger hit you might not land. Wisdom matters too: it cuts how much AP and MP an enemy can strip from you, and getting locked out of your kit loses fights. Keep your damage element, but balance it against staying alive, and value range and MP for the positioning game.</p>

<h2>The three you always lock</h2>
<p>Whatever the mode, AP, MP and range are targets, not sliders. Decide the breakpoints your spells need — say 11 AP, 6 MP, 4 range — and lock them. The optimizer then spends every remaining stat point on what changes between modes, instead of wasting gear hitting an AP number you never asked for.</p>

<h2>Do it in the tool</h2>
<p>Make one project per mode. Start from your PvM set, duplicate it, drag resistance and Wisdom up, drag a little damage down, and re-tailor — you've got a Kolossium variant in under a minute. Then throw both into the <a href="/choose_compare_sets/">comparison</a> to see exactly what you trade. That side-by-side is the fastest way to understand your own build.</p>

<p><em>Pick a mode and tune it: <a href="/setup/">start a project.</a></em></p>
''',
            },
            'fr': {
                'title': "Optimiser son stuff pour le PvM, le PvP et le Kolizéum",
                'desc': "Le même perso a besoin d'un build différent selon que tu farmes du donjon, que tu duelles ou que tu grind le Kolizéum. Voilà comment pondérer chacun sans tout refaire de zéro.",
                'lead': "Le même perso a besoin d'un build différent selon que tu farmes du donjon, que tu duelles ou que tu grind le Kolizéum. Mêmes items, priorités différentes — voilà comment pondérer chacun.",
                'body': '''
<h2>Pourquoi un seul build ne suffit pas</h2>
<p>Ton stuff ne change pas, mais ce que tu lui demandes, si. Un set de farm PvM veut effacer les monstres avant qu'ils comptent ; un set Kolizéum veut être encore debout au tour dix. Mets les mêmes items dans les deux et tu seras moyen partout. L'astuce, c'est pas d'avoir trois stuffs — c'est de dire à l'optimiseur à quoi sert <strong>ce</strong> set-là et de le sauvegarder comme projet à part.</p>

<h2>PvM : tuer vite, survivre assez</h2>
<p>Contre les monstres tu connais souvent le combat, donc tu peux miser sur l'attaque. Pondère ton élément et la Puissance haut, pousse les dommages fixes et en %, et garde juste assez de vita et de résistance pour clean le donjon que tu fais vraiment. Personne ne lit ton build en face, donc sacrifier du défensif pour du dégât brut est souvent le bon choix. Verrouille tes PA, PM et portée pour sortir ton combo, puis laisse l'outil tout mettre dans la puissance de frappe.</p>

<h2>PvP et Kolizéum : la résistance gagne les matchs</h2>
<p>Là, quelqu'un essaie activement de pourrir ton tour. La résistance fixe et en % grimpe en haut de tes poids — encaisser un burst vaut plus qu'un coup à peine plus gros que tu vas peut-être rater. La Sagesse compte aussi : elle réduit les PA et PM qu'un ennemi peut te retirer, et se faire lock hors de son kit, ça perd des combats. Garde ton élément de dégâts, mais équilibre-le avec la survie, et valorise la portée et les PM pour le jeu de placement.</p>

<h2>Les trois que tu verrouilles toujours</h2>
<p>Peu importe le mode, PA, PM et portée sont des objectifs, pas des curseurs. Décide les paliers dont tes sorts ont besoin — genre 11 PA, 6 PM, 4 de portée — et verrouille-les. L'optimiseur dépense alors chaque point de stat restant sur ce qui change entre les modes, au lieu de gaspiller du stuff à atteindre un nombre de PA que t'as pas demandé.</p>

<h2>Fais-le dans l'outil</h2>
<p>Crée un projet par mode. Pars de ton set PvM, duplique-le, monte la résistance et la Sagesse, baisse un peu les dégâts, et retaille — t'as une variante Kolizéum en moins d'une minute. Puis balance les deux dans le <a href="/choose_compare_sets/">comparateur</a> pour voir exactement ce que tu échanges. Ce côte-à-côte, c'est le moyen le plus rapide de comprendre ton propre build.</p>

<p><em>Choisis un mode et règle-le : <a href="/setup/">lance un projet.</a></em></p>
''',
            },
            'es': {
                'title': "Optimizar tu build para PvM, PvP y Koliseo",
                'desc': "El mismo personaje necesita un build distinto según si farmeas mazmorras, dueleas o grindeas Koliseo. Aquí tienes cómo ponderar cada uno sin rehacerlo todo de cero.",
                'lead': "El mismo personaje necesita un build distinto según si farmeas mazmorras, dueleas o grindeas Koliseo. Mismos ítems, prioridades distintas — aquí tienes cómo ponderar cada uno.",
                'body': '''
<h2>Por qué un solo build no basta</h2>
<p>Tu equipo no cambia, pero lo que le pides sí. Un set de farmeo PvM quiere borrar a los monstruos antes de que importen; un set de Koliseo quiere seguir en pie en el turno diez. Mete los mismos ítems en ambos y serás mediocre en los dos. El truco no es tener tres sets — es decirle al optimizador para qué sirve <strong>este</strong> set y guardarlo como su propio proyecto.</p>

<h2>PvM: matar rápido, sobrevivir lo justo</h2>
<p>Contra monstruos sueles conocer la pelea, así que puedes apostar por el ataque. Pondera tu elemento y la Potencia alto, sube el daño fijo y en %, y guarda solo la vita y resistencia que necesites para limpiar la mazmorra que de verdad haces. Nadie lee tu build enfrente, así que sacrificar defensa por daño bruto suele ser lo correcto. Bloquea tus PA, PM y alcance para sacar tu combo, y deja que la herramienta lo meta todo en poder de daño.</p>

<h2>PvP y Koliseo: la resistencia gana partidas</h2>
<p>Ahora alguien intenta activamente arruinarte el turno. La resistencia fija y en % sube a lo más alto de tus pesos — aguantar un burst vale más que un golpe algo mayor que quizá falles. La Sabiduría también cuenta: reduce los PA y PM que un enemigo puede quitarte, y quedarte bloqueado fuera de tu kit pierde combates. Mantén tu elemento de daño, pero equilíbralo con sobrevivir, y valora el alcance y los PM para el juego de posición.</p>

<h2>Los tres que siempre bloqueas</h2>
<p>Da igual el modo, PA, PM y alcance son objetivos, no deslizadores. Decide los umbrales que tus hechizos necesitan — pongamos 11 PA, 6 PM, 4 de alcance — y bloquéalos. El optimizador gasta entonces cada punto restante en lo que cambia entre modos, en vez de malgastar equipo llegando a un número de PA que no pediste.</p>

<h2>Hazlo en la herramienta</h2>
<p>Haz un proyecto por modo. Parte de tu set PvM, duplícalo, sube resistencia y Sabiduría, baja un poco el daño, y vuelve a crear el set — tienes una variante de Koliseo en menos de un minuto. Luego mete ambos en el <a href="/choose_compare_sets/">comparador</a> para ver exactamente qué cambias. Ese lado a lado es la forma más rápida de entender tu propio build.</p>

<p><em>Elige un modo y ajústalo: <a href="/setup/">empieza un proyecto.</a></em></p>
''',
            },
            'pt': {
                'title': "Otimizar seu build para PvM, PvP e Koliseu",
                'desc': "O mesmo personagem precisa de um build diferente conforme você farma masmorra, duela ou grinda Koliseu. Veja como ponderar cada um sem refazer tudo do zero.",
                'lead': "O mesmo personagem precisa de um build diferente conforme você farma masmorra, duela ou grinda Koliseu. Mesmos itens, prioridades diferentes — veja como ponderar cada um.",
                'body': '''
<h2>Por que um build só não basta</h2>
<p>Seu equipamento não muda, mas o que você pede dele muda. Um set de farm PvM quer apagar os monstros antes que eles importem; um set de Koliseu quer continuar de pé no turno dez. Coloque os mesmos itens nos dois e você fica mediano em ambos. O truque não é ter três sets — é dizer ao otimizador pra que serve <strong>este</strong> set e salvá-lo como um projeto próprio.</p>

<h2>PvM: matar rápido, sobreviver o suficiente</h2>
<p>Contra monstros você costuma conhecer a luta, então dá pra apostar no ataque. Pondere seu elemento e a Potência alto, suba o dano fixo e em %, e mantenha só a vita e resistência que precisa pra limpar a masmorra que você realmente faz. Ninguém lê seu build do outro lado, então sacrificar defesa por dano bruto costuma ser o certo. Trave seus PA, PM e alcance pra sair seu combo, e deixe a ferramenta jogar todo o resto em poder de dano.</p>

<h2>PvP e Koliseu: resistência ganha partidas</h2>
<p>Agora alguém está tentando ativamente estragar seu turno. Resistência fixa e em % sobe pro topo dos seus pesos — aguentar um burst vale mais que um golpe um pouco maior que você talvez erre. Sabedoria também conta: ela reduz os PA e PM que um inimigo pode te tirar, e ficar travado fora do seu kit perde lutas. Mantenha seu elemento de dano, mas equilibre com sobreviver, e valorize alcance e PM pro jogo de posição.</p>

<h2>Os três que você sempre trava</h2>
<p>Não importa o modo, PA, PM e alcance são metas, não controles. Decida os limiares que seus feitiços precisam — digamos 11 PA, 6 PM, 4 de alcance — e trave. O otimizador então gasta cada ponto restante no que muda entre os modos, em vez de desperdiçar equipamento batendo num número de PA que você não pediu.</p>

<h2>Faça na ferramenta</h2>
<p>Faça um projeto por modo. Comece do seu set PvM, duplique, suba resistência e Sabedoria, abaixe um pouco o dano, e refaça o set — você tem uma variante de Koliseu em menos de um minuto. Depois jogue os dois no <a href="/choose_compare_sets/">comparador</a> pra ver exatamente o que você troca. Esse lado a lado é o jeito mais rápido de entender seu próprio build.</p>

<p><em>Escolha um modo e ajuste: <a href="/setup/">comece um projeto.</a></em></p>
''',
            },
            'de': {
                'title': "Builds für PvM, PvP und Kolosseum",
                'desc': "Derselbe Charakter braucht je nach dem ein anderes Build — ob du Dungeons farmst, duellierst oder Kolosseum grindest. So gewichtest du jeden Modus, ohne alles neu zu bauen.",
                'lead': "Derselbe Charakter braucht je nach dem ein anderes Build — ob du Dungeons farmst, duellierst oder Kolosseum grindest. Gleiche Items, andere Prioritäten — so gewichtest du jeden.",
                'body': '''
<h2>Warum ein Build nicht reicht</h2>
<p>Deine Ausrüstung ändert sich nicht, aber was du von ihr verlangst, schon. Ein PvM-Farmset will Monster löschen, bevor sie zählen; ein Kolosseum-Set will in Runde zehn noch stehen. Steck dieselben Items in beide und du bist überall mittelmäßig. Der Trick ist nicht, drei Sets zu besitzen — sondern dem Optimierer zu sagen, wofür <strong>dieses</strong> Set ist, und es als eigenes Projekt zu speichern.</p>

<h2>PvM: schnell töten, genug überleben</h2>
<p>Gegen Monster kennst du den Kampf meist, also kannst du auf Angriff setzen. Gewichte dein Element und Power hoch, drück fixen und prozentualen Schaden, und behalte nur so viel Vita und Resistenz, wie du für den Dungeon brauchst, den du wirklich läufst. Niemand liest gegenüber dein Build, also ist es oft richtig, Defensive für rohen Schaden zu opfern. Fixier deine AP, BP und Reichweite für dein Combo, und lass das Tool alles andere in Schlagkraft stecken.</p>

<h2>PvP und Kolosseum: Resistenz gewinnt Partien</h2>
<p>Jetzt versucht jemand aktiv, dir die Runde zu ruinieren. Fixe und prozentuale Resistenz springen an die Spitze deiner Gewichte — einen Burst zu überleben ist mehr wert als ein etwas größerer Treffer, den du vielleicht nicht landest. Weisheit zählt auch: Sie senkt, wie viel AP und BP ein Gegner dir abziehen kann, und aus dem eigenen Kit gesperrt zu werden, verliert Kämpfe. Behalte dein Schadenselement, aber wäge es gegen Überleben ab, und schätze Reichweite und BP fürs Positionsspiel.</p>

<h2>Die drei, die du immer fixierst</h2>
<p>Egal welcher Modus, AP, BP und Reichweite sind Ziele, keine Regler. Leg die Schwellen fest, die deine Zauber brauchen — sagen wir 11 AP, 6 BP, 4 Reichweite — und fixier sie. Der Optimierer gibt dann jeden übrigen Statpunkt für das aus, was sich zwischen den Modi ändert, statt Ausrüstung zu verschwenden, um eine AP-Zahl zu treffen, die du nie verlangt hast.</p>

<h2>Mach es im Tool</h2>
<p>Leg pro Modus ein Projekt an. Starte von deinem PvM-Set, dupliziere es, zieh Resistenz und Weisheit hoch, etwas Schaden runter, und schneider neu — du hast in unter einer Minute eine Kolosseum-Variante. Wirf dann beide in den <a href="/choose_compare_sets/">Vergleich</a>, um genau zu sehen, was du eintauschst. Dieses Nebeneinander ist der schnellste Weg, dein eigenes Build zu verstehen.</p>

<p><em>Wähl einen Modus und stell ihn ein: <a href="/setup/">starte ein Projekt.</a></em></p>
''',
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


def list_guides(language_code):
    """Return [{slug, title, desc}] in display order for a language."""
    lang = _lang(language_code)
    out = []
    for slug in ORDER:
        guide = GUIDES[slug]
        block = guide['i18n'].get(lang) or guide['i18n']['en']
        out.append({
            'slug': slug,
            'title': block['title'],
            'desc': block['desc'],
        })
    return out


def get_guide(slug, language_code):
    """Return {slug, title, desc, lead, body} or None if slug unknown."""
    guide = GUIDES.get(slug)
    if not guide:
        return None
    lang = _lang(language_code)
    block = guide['i18n'].get(lang) or guide['i18n']['en']
    data = {'slug': slug}
    data.update(block)
    return data
