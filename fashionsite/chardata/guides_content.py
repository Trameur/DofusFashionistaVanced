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

ORDER = ['getting-started', 'how-it-works', 'stats-explained', 'tuning-your-weights', 'game-modes', 'reading-an-item', 'understanding-your-solution', 'mono-vs-multi-element', 'gearing-up', 'comparing-builds', 'forgemagie-planning', 'versions-explained']


GUIDES = {
    # ------------------------------------------------------------------ #
    'getting-started': {
        'published': '2026-06-30',
        'i18n': {
            'en': {
                'title': 'Your first Dofus build, step by step',
                'desc': "You picked a class, you're staring at a wall of items, and you have no clue which belt actually fits. Here's how to go from nothing to a full optimized set in a few minutes.",
                'lead': "You picked a class, you're staring at a wall of items, and you have no clue which belt actually fits. That's exactly what the Fashionista is for.",
                'body': '''
<h2>1. Start a project</h2>
<p>Hit <a href="/setup/">Create a project</a>, pick your class, your level and the Dofus version you play. That's the whole setup. If you'd rather not fiddle with anything, two shortcuts get you a build almost instantly:</p>
<ul>
<li><a href="/quickstart/">Quick start</a>: answer three quick questions and you get a set.</li>
<li><a href="/smartbuild/">Smart build</a>: literally describe what you want in plain words ("agility Sram level 200, 11 AP, max range") and it sets things up for you.</li>
</ul>

<h2>2. Tell it what you actually want</h2>
<p>This is where most people overthink it. The wizard gives you sliders: AP, MP, range, the element you hit with, vitality, and so on. You're not entering numbers item by item, you're telling the tool how much each stat is <strong>worth to you</strong>. Want a glass cannon? Crank damage and element, leave vitality low. Doing Kolossium? Push resistance and lock your AP/MP. You can always come back and nudge a slider later.</p>

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
                'desc': "T'as choisi ta classe, t'as une montagne d'items devant les yeux et aucune idée de quelle ceinture coller. Voilà comment passer de zéro à un stuff complet et optimisé en quelques minutes.",
                'lead': "T'as choisi ta classe, t'as une montagne d'items devant les yeux et aucune idée de quelle ceinture coller. C'est exactement à ça que sert la Fashionista.",
                'body': '''
<h2>1. Crée un projet</h2>
<p>Clique sur <a href="/setup/">Créer un projet</a>, choisis ta classe, ton niveau et la version de Dofus que tu joues. C'est toute la config. Et si t'as la flemme de régler quoi que ce soit, deux raccourcis te sortent un stuff quasi instantanément :</p>
<ul>
<li><a href="/quickstart/">Démarrage rapide</a> : trois questions et t'as un set.</li>
<li><a href="/smartbuild/">Build intelligent</a> : tu décris littéralement ce que tu veux en français ("Sram agi niveau 200, 11 PA, portée max") et il te prépare tout.</li>
</ul>

<h2>2. Dis-lui vraiment ce que tu veux</h2>
<p>C'est là que la plupart des gens se prennent la tête pour rien. L'assistant te donne des curseurs : PA, PM, portée, l'élément avec lequel tu tapes, la vita, etc. Tu ne rentres pas les items un par un, tu dis à l'outil combien chaque carac <strong>vaut pour toi</strong>. Tu veux un build full dégâts ? Monte les dégâts et l'élément, laisse la vita en bas. Tu fais du Kolizéum ? Pousse la résistance et verrouille tes PA/PM. Tu pourras toujours revenir bouger un curseur après.</p>

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
<p>Aquí es donde la mayoría se complica sin necesidad. El asistente te da deslizadores: PA, PM, alcance, el elemento con el que pegas, vitalidad y demás. No metes los ítems uno a uno: le dices a la herramienta cuánto <strong>vale para ti</strong> cada característica. ¿Quieres un build de cristal? Sube daño y elemento, deja la vita baja. ¿Haces Koliseo? Sube la resistencia y bloquea tus PA/PM. Siempre puedes volver y mover un deslizador después.</p>

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
                'desc': "Você escolheu a classe, tem uma parede de itens na frente e nenhuma ideia de qual cinto encaixa. Veja como sair do zero até um set completo e otimizado em poucos minutos.",
                'lead': "Você escolheu a classe, tem uma parede de itens na frente e nenhuma ideia de qual cinto encaixa de verdade. É exatamente para isso que a Fashionista serve.",
                'body': '''
<h2>1. Crie um projeto</h2>
<p>Clique em <a href="/setup/">Criar um projeto</a>, escolha sua classe, seu nível e a versão de Dofus que você joga. É toda a configuração. E se você estiver com preguiça de ajustar qualquer coisa, dois atalhos entregam um build quase na hora:</p>
<ul>
<li><a href="/quickstart/">Início rápido</a>: três perguntas e você tem um set.</li>
<li><a href="/smartbuild/">Build inteligente</a>: descreva o que você quer com suas palavras ("Sram de agilidade nível 200, 11 PA, alcance máximo") e ele monta tudo pra você.</li>
</ul>

<h2>2. Diga o que você realmente quer</h2>
<p>É aqui que a maioria complica à toa. O assistente te dá controles deslizantes: PA, PM, alcance, o elemento com que você bate, vitalidade e por aí vai. Você não coloca os itens um por um, você diz pra ferramenta quanto cada atributo <strong>vale pra você</strong>. Quer um build de vidro? Aumenta dano e elemento, deixa a vita lá embaixo. Joga Koliseu? Sobe a resistência e trava seus PA/PM. Dá sempre pra voltar e mexer num controle depois.</p>

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
                'desc': "Klasse gewählt, eine Wand voller Items vor dir, und keine Ahnung, welcher Gürtel eigentlich passt. So kommst du in ein paar Minuten von null zum fertigen, optimierten Set.",
                'lead': "Klasse gewählt, eine Wand voller Items vor dir, und keine Ahnung, welcher Gürtel eigentlich passt. Genau dafür ist die Fashionista da.",
                'body': '''
<h2>1. Leg ein Projekt an</h2>
<p>Klick auf <a href="/setup/">Projekt erstellen</a>, wähl deine Klasse, dein Level und die Dofus-Version, die du spielst. Mehr Einrichtung gibt's nicht. Und wenn du gar nichts einstellen willst, bringen dich zwei Abkürzungen fast sofort zum Build:</p>
<ul>
<li><a href="/quickstart/">Schnellstart</a>: drei Fragen, fertig ist das Set.</li>
<li><a href="/smartbuild/">Smart Build</a>: beschreib einfach in Worten, was du willst ("Agi-Sram Level 200, 11 AP, maximale Reichweite") und es richtet alles für dich ein.</li>
</ul>

<h2>2. Sag ihm, was du wirklich willst</h2>
<p>Hier machen es sich die meisten unnötig kompliziert. Der Assistent gibt dir Regler: AP, BP, Reichweite, das Element, mit dem du haust, Vitalität und so weiter. Du trägst nicht Item für Item Zahlen ein, du sagst dem Tool, wie viel dir jeder Wert <strong>wert ist</strong>. Glaskanone? Schadens- und Element-Regler hoch, Vita niedrig lassen. Kolosseum? Resistenz hoch und AP/BP fixieren. Du kannst jederzeit zurück und einen Regler nachjustieren.</p>

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
                'desc': "AP, range, masteries, vitality, crits… Dofus throws a lot of numbers at you. Here's a no-nonsense rundown of what actually matters and how to weight it in a build.",
                'lead': "AP, range, masteries, vitality, crits… Dofus throws a lot of numbers at you. Here's a no-nonsense rundown of what actually matters and how to weight it.",
                'body': '''
<h2>The kingmakers: AP, MP and range</h2>
<p>These three decide what your character can even do on a turn. One more AP can mean a whole extra spell; one more MP is positioning and kiting; range makes or breaks half the classes in the game. They're scarce, every build fights over them, so in the tool you usually <strong>lock them to a target</strong> rather than weight them: "give me exactly 11 AP and 6 MP, then optimize the rest."</p>

<h2>Your element and mastery</h2>
<p>Your damage comes from one (or more) of Strength, Intelligence, Agility and Chance, paired with the matching elemental mastery. Pick the element your main spells scale with and lean into it: a focused mono-element build almost always out-damages a smeared multi-element one. Since the 3.6 characteristic rework, masteries carry even more of the weight, so they deserve a high slider on any damage build.</p>

<h2>Staying alive</h2>
<p>Vitality is raw HP and it's cheap to stack, but more isn't always better: 1000 extra HP you didn't need is a damage stat you threw away. Resistance (flat and %) is what actually keeps you up in PvP and tough fights. For Kolossium, weight resistance seriously; for mobbing PvM, you can often get away with less.</p>

<h2>The multipliers: Power, Damage, Crit</h2>
<p>Power boosts all your elemental damage at once and is almost always worth a high weight. Flat Damage (+dmg) is strongest on multi-hit, low-base spells; % damage scales with big hits. Critical hit rate is great <em>if</em> your crits actually add a meaningful bonus: check the spell before you chase it.</p>

<h2>The quiet ones: Wisdom, Prospecting, Initiative, Pods</h2>
<p>Not every build is about damage. Wisdom = XP and resistance to AP/MP loss; Prospecting = drop rate, gold for farmers; Initiative decides turn order; Pods are pure convenience. Give them a small weight when they matter to you and zero when they don't: the optimizer will only chase them if there's no real cost.</p>

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
<p>Ces trois-là décident de ce que ton perso peut faire dans un tour, point. Un PA de plus, c'est parfois un sort entier en rab ; un PM de plus, c'est du placement et du kite ; la portée fait ou défait la moitié des classes du jeu. C'est rare, tous les builds se les arrachent, donc dans l'outil tu les <strong>verrouilles à un objectif</strong> plutôt que de les pondérer : "donne-moi exactement 11 PA et 6 PM, puis optimise le reste".</p>

<h2>Ton élément et ta maîtrise</h2>
<p>Tes dégâts viennent d'un (ou plusieurs) parmi Force, Intelligence, Agilité et Chance, couplés à la maîtrise élémentaire correspondante. Choisis l'élément sur lequel scalent tes sorts principaux et fonce dessus : un build mono-élément concentré tape presque toujours plus fort qu'un build multi-élément dilué. Depuis la refonte des caracs 3.6, les maîtrises pèsent encore plus lourd, donc elles méritent un gros curseur sur tout build dégâts.</p>

<h2>Rester en vie</h2>
<p>La vitalité, c'est des PV bruts et ça s'empile pas cher, mais plus n'est pas toujours mieux : 1000 PV en trop dont t'avais pas besoin, c'est une stat de dégâts jetée à la poubelle. La résistance (fixe et %) c'est ce qui te garde debout en PvP et dans les combats velus. Pour le Kolizéum, pondère la résistance sérieusement ; en PvM de mob, tu peux souvent t'en passer un peu.</p>

<h2>Les multiplicateurs : Puissance, Dommages, Critique</h2>
<p>La Puissance booste tous tes dégâts élémentaires d'un coup et mérite presque toujours un gros poids. Les Dommages fixes (+dom) sont rois sur les sorts multi-coups à faible base ; les dégâts en % scalent avec les gros coups. Le taux de critique est top <em>si</em> tes crits ajoutent vraiment un bonus qui compte : vérifie le sort avant de courir après.</p>

<h2>Les discrètes : Sagesse, Prospection, Initiative, Pods</h2>
<p>Tous les builds ne tournent pas autour des dégâts. Sagesse = XP et résistance à la perte de PA/PM ; Prospection = taux de drop, kamas pour les farmeurs ; l'Initiative décide de l'ordre des tours ; les Pods, c'est du confort pur. Mets-leur un petit poids quand ça t'importe et zéro sinon : l'optimiseur ne les chassera que si ça ne coûte rien.</p>

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
<p>Estos tres deciden lo que tu personaje puede hacer en un turno, y punto. Un PA más a veces es un hechizo entero extra; un PM más es colocación y kiteo; el alcance hace o deshace a la mitad de las clases del juego. Son escasos, todos los builds se pelean por ellos, así que en la herramienta normalmente los <strong>bloqueas a un objetivo</strong> en vez de ponderarlos: "dame exactamente 11 PA y 6 PM, y luego optimiza el resto".</p>

<h2>Tu elemento y tu dominio</h2>
<p>Tu daño sale de uno (o varios) entre Fuerza, Inteligencia, Agilidad y Suerte, junto con el dominio elemental correspondiente. Elige el elemento con el que escalan tus hechizos principales y ve a por él: un build monoelemento concentrado casi siempre pega más que uno multielemento diluido. Desde el rework de características de 3.6, los dominios pesan aún más, así que merecen un deslizador alto en cualquier build de daño.</p>

<h2>Seguir vivo</h2>
<p>La vitalidad son PV en bruto y apilarla es barato, pero más no siempre es mejor: 1000 PV de más que no necesitabas es una estadística de daño tirada a la basura. La resistencia (fija y %) es lo que de verdad te mantiene en pie en PvP y en peleas duras. Para el Koliseo, pondera la resistencia en serio; en PvM de mobeo, muchas veces puedes ir con menos.</p>

<h2>Los multiplicadores: Potencia, Daños, Crítico</h2>
<p>La Potencia sube todo tu daño elemental de golpe y casi siempre merece un peso alto. Los Daños fijos (+daño) brillan en hechizos multigolpe de base baja; el daño en % escala con los golpazos. La tasa de crítico es genial <em>si</em> tus críticos suman un bonus que de verdad cuenta: mira el hechizo antes de ir a por ella.</p>

<h2>Las calladas: Sabiduría, Prospección, Iniciativa, Pods</h2>
<p>No todos los builds van de daño. Sabiduría = XP y resistencia a la pérdida de PA/PM; Prospección = tasa de drop, kamas para farmers; la Iniciativa decide el orden de turnos; los Pods son comodidad pura. Dales un peso pequeño cuando te importan y cero cuando no: el optimizador solo irá a por ellos si no cuesta nada.</p>

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
<p>Esses três decidem o que seu personagem consegue fazer num turno, ponto. Um PA a mais às vezes é um feitiço inteiro extra; um PM a mais é posicionamento e kite; o alcance faz ou quebra metade das classes do jogo. São escassos, todo build briga por eles, então na ferramenta você geralmente os <strong>trava num objetivo</strong> em vez de ponderar: "me dá exatamente 11 PA e 6 PM, e depois otimiza o resto".</p>

<h2>Seu elemento e seu domínio</h2>
<p>Seu dano vem de um (ou mais) entre Força, Inteligência, Agilidade e Sorte, junto com o domínio elemental correspondente. Escolha o elemento com que seus feitiços principais escalam e vá fundo nele: um build mono-elemento concentrado quase sempre bate mais que um multi-elemento diluído. Desde a reformulação de características da 3.6, os domínios pesam ainda mais, então merecem um controle alto em qualquer build de dano.</p>

<h2>Continuar vivo</h2>
<p>Vitalidade é PV cru e empilhar é barato, mas mais nem sempre é melhor: 1000 PV a mais de que você não precisava é um atributo de dano jogado fora. Resistência (fixa e %) é o que de fato te mantém em pé no PvP e em lutas pesadas. Pro Koliseu, pondere resistência a sério; em PvM de mob, muitas vezes dá pra ir com menos.</p>

<h2>Os multiplicadores: Potência, Danos, Crítico</h2>
<p>A Potência aumenta todo o seu dano elemental de uma vez e quase sempre merece um peso alto. Danos fixos (+dano) brilham em feitiços multi-golpe de base baixa; dano em % escala com golpes grandes. A taxa de crítico é ótima <em>se</em> seus críticos somam um bônus que conta de verdade: confira o feitiço antes de correr atrás.</p>

<h2>Os quietos: Sabedoria, Prospecção, Iniciativa, Pods</h2>
<p>Nem todo build é sobre dano. Sabedoria = XP e resistência à perda de PA/PM; Prospecção = taxa de drop, kamas pros farmers; a Iniciativa decide a ordem dos turnos; os Pods são puro conforto. Dê um peso pequeno quando importam e zero quando não: o otimizador só vai atrás deles se não custar nada.</p>

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
<p>Diese drei entscheiden, was deine Figur in einer Runde überhaupt tun kann. Ein AP mehr ist manchmal ein ganzer zusätzlicher Zauber; ein BP mehr ist Positionierung und Kiten; Reichweite macht oder bricht die Hälfte der Klassen im Spiel. Sie sind knapp, jedes Build kämpft darum, deshalb <strong>fixierst</strong> du sie im Tool meist auf ein Ziel, statt sie zu gewichten: "gib mir genau 11 AP und 6 BP, dann optimiere den Rest".</p>

<h2>Dein Element und deine Beherrschung</h2>
<p>Dein Schaden kommt aus einem (oder mehreren) von Stärke, Intelligenz, Beweglichkeit und Glück, zusammen mit der passenden Elementarbeherrschung. Wähl das Element, mit dem deine Hauptzauber skalieren, und zieh es durch: ein fokussiertes Mono-Element-Build macht fast immer mehr Schaden als ein verwässertes Multi-Element-Build. Seit dem Charakterwerte-Rework in 3.6 wiegen Beherrschungen noch schwerer, also verdienen sie in jedem Schadens-Build einen hohen Regler.</p>

<h2>Am Leben bleiben</h2>
<p>Vitalität ist rohes LP und billig zu stapeln, aber mehr ist nicht immer besser: 1000 LP zu viel, die du nicht gebraucht hast, sind ein weggeworfener Schadenswert. Resistenz (fix und %) ist das, was dich in PvP und harten Kämpfen wirklich oben hält. Fürs Kolosseum gewichte Resistenz ernsthaft; beim Mob-PvM kommst du oft mit weniger aus.</p>

<h2>Die Multiplikatoren: Stärke (Power), Schaden, Kritisch</h2>
<p>Power hebt deinen gesamten Elementarschaden auf einmal und verdient fast immer ein hohes Gewicht. Fixer Schaden (+Schaden) ist am stärksten bei Multi-Treffer-Zaubern mit niedriger Basis; %-Schaden skaliert mit großen Treffern. Kritische Trefferrate ist super, <em>wenn</em> deine Kritischen wirklich einen spürbaren Bonus draufpacken: schau den Zauber an, bevor du ihr hinterherjagst.</p>

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
                'title': 'Dofus 3, Beta, Dofus 2, Retro, Touch: which one are you on?',
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
                'title': 'Dofus 3, Bêta, Dofus 2, Retro, Touch : tu joues à laquelle ?',
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
                'desc': "Eine Sache hebt die Fashionista ab: Sie deckt fünf Spielarten von Dofus ab, nicht nur die Live-Version. Hier ist, was jede ist, wer sie spielt und wie du umschaltest.",
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

    # ------------------------------------------------------------------ #
    'game-modes': {
        'published': '2026-07-01',
        'i18n': {
            'en': {
                'title': "Building for PvM, PvP and Kolossium",
                'desc': "The same character needs a different build depending on whether you're farming dungeons, dueling, or grinding Kolossium. Here's how to weight each one without rebuilding from scratch.",
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
                'desc': "Le même perso a besoin d'un build différent selon que tu farmes du donjon, que tu duelles ou que tu grind le Kolizéum. Voilà comment pondérer chacun sans tout refaire de zéro.",
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
                'desc': "El mismo personaje necesita un build distinto según si farmeas mazmorras, dueleas o grindeas Koliseo. Aquí tienes cómo ponderar cada uno sin rehacerlo todo de cero.",
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
                'desc': "Derselbe Charakter braucht je nach dem ein anderes Build, ob du Dungeons farmst, duellierst oder Kolosseum grindest. So gewichtest du jeden Modus, ohne alles neu zu bauen.",
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
                'desc': "Spreading your damage across two elements feels safe, but it usually hits softer than committing to one. Here's why mono almost always wins, and the few times it doesn't.",
                'lead': "Spreading your damage across two elements feels safe, but it usually hits softer than committing to one. Here's why focusing pays off, and when it doesn't.",
                'body': '''
<h2>Why one element usually wins</h2>
<p>Your damage scales with the matching mastery: fire damage with fire mastery, and so on. Split your gear across two elements and every point of mastery only helps half your hits; pour it all into one and every point counts every time. The same goes for the characteristic behind it (Strength, Intelligence, Agility, Chance). Concentration compounds: a focused mono-element set almost always out-damages a smeared two-element one of the same level.</p>

<h2>It's really just your sliders</h2>
<p>In the tool, mono-vs-multi isn't a separate setting: it's how you weight your elements. Crank one element and its mastery, leave the others low, and the optimizer builds you a focused hitter. Weight two elements equally and it'll happily split your gear between them. So if your build came out spread when you wanted focused, your weights are the place to look.</p>

<h2>When multi-element is actually right</h2>
<p>It's not always wrong. A few cases genuinely want two elements:</p>
<ul>
<li>Spells that hit in two elements, or a kit that mixes them, your damage really does scale on both.</li>
<li>A set bonus or a key item that pushes a second element for free, so taking it costs you nothing.</li>
<li>Utility over raw damage: a secondary element for a specific spell's effect rather than its hit.</li>
</ul>
<p>Outside those, splitting is usually just leaving damage on the table.</p>

<h2>Pick the element your spells love</h2>
<p>Choose the element your main damage spells scale on (check them on the spells page if you're not sure) and weight that one and its mastery high. Let the optimizer do the rest. One clean element beats two half-hearted ones nearly every time.</p>

<p><em>Try both and compare: <a href="/setup/">build a set</a> and see the damage for yourself.</em></p>
''',
            },
            'fr': {
                'title': "Mono-élément ou multi-élément ? Choisis-en un et tape plus fort",
                'desc': "Répartir tes dégâts sur deux éléments rassure, mais ça tape souvent moins fort que de tout miser sur un seul. Voilà pourquoi le mono gagne presque toujours, et les rares cas où non.",
                'lead': "Répartir tes dégâts sur deux éléments rassure, mais ça tape souvent moins fort que de tout miser sur un seul. Voilà pourquoi se concentrer paie, et quand ça ne paie pas.",
                'body': '''
<h2>Pourquoi un seul élément gagne d'habitude</h2>
<p>Tes dégâts scalent avec la maîtrise correspondante : dégâts feu avec maîtrise feu, etc. Répartis ton stuff sur deux éléments et chaque point de maîtrise n'aide que la moitié de tes coups ; mets tout sur un seul et chaque point compte à chaque fois. Pareil pour la caractéristique derrière (Force, Intelligence, Agilité, Chance). La concentration se cumule : un set mono-élément concentré tape presque toujours plus fort qu'un set bi-élément dilué du même niveau.</p>

<h2>En vrai, c'est juste tes curseurs</h2>
<p>Dans l'outil, le mono-vs-multi n'est pas un réglage à part : c'est la façon dont tu pondères tes éléments. Monte un élément et sa maîtrise, laisse les autres bas, et l'optimiseur te construit un frappeur concentré. Pondère deux éléments à égalité et il répartira ton stuff entre les deux sans souci. Donc si ton build est sorti dilué alors que tu le voulais concentré, c'est tes poids qu'il faut regarder.</p>

<h2>Quand le multi-élément a vraiment du sens</h2>
<p>C'est pas toujours un tort. Quelques cas veulent vraiment deux éléments :</p>
<ul>
<li>Des sorts qui tapent en deux éléments, ou un kit qui les mélange, tes dégâts scalent vraiment sur les deux.</li>
<li>Un bonus de panoplie ou un item clé qui pousse un second élément gratuitement, donc le prendre ne te coûte rien.</li>
<li>L'utilité plutôt que le dégât brut : un second élément pour l'effet d'un sort précis, pas pour son coup.</li>
</ul>
<p>En dehors de ça, répartir, c'est en général laisser du dégât sur la table.</p>

<h2>Choisis l'élément que tes sorts préfèrent</h2>
<p>Prends l'élément sur lequel scalent tes sorts de dégâts principaux (vérifie-les sur la page des sorts si tu hésites) et pondère celui-là et sa maîtrise haut. Laisse l'optimiseur faire le reste. Un élément propre bat deux éléments à moitié presque à chaque fois.</p>

<p><em>Teste les deux et compare : <a href="/setup/">construis un set</a> et regarde les dégâts toi-même.</em></p>
''',
            },
            'es': {
                'title': "¿Monoelemento o multielemento? Elige uno y pega más fuerte",
                'desc': "Repartir tu daño entre dos elementos da sensación de seguridad, pero suele pegar más flojo que apostar por uno solo. Aquí tienes por qué el mono casi siempre gana, y las pocas veces que no.",
                'lead': "Repartir tu daño entre dos elementos da sensación de seguridad, pero suele pegar más flojo que apostar por uno solo. Aquí tienes por qué concentrarse compensa, y cuándo no.",
                'body': '''
<h2>Por qué un solo elemento suele ganar</h2>
<p>Tu daño escala con el dominio correspondiente: daño de fuego con dominio de fuego, y así. Reparte tu equipo entre dos elementos y cada punto de dominio solo ayuda a la mitad de tus golpes; mételo todo en uno y cada punto cuenta siempre. Lo mismo con la característica detrás (Fuerza, Inteligencia, Agilidad, Suerte). La concentración se acumula: un set monoelemento concentrado casi siempre pega más que uno bielemento diluido del mismo nivel.</p>

<h2>En realidad son tus deslizadores</h2>
<p>En la herramienta, mono-vs-multi no es un ajuste aparte: es cómo ponderas tus elementos. Sube un elemento y su dominio, deja los demás bajos, y el optimizador te monta un pegador concentrado. Pondera dos elementos por igual y repartirá tu equipo entre ambos sin problema. Así que si tu build salió repartido cuando lo querías concentrado, mira tus pesos.</p>

<h2>Cuándo el multielemento sí tiene sentido</h2>
<p>No siempre está mal. Algunos casos quieren de verdad dos elementos:</p>
<ul>
<li>Hechizos que pegan en dos elementos, o un kit que los mezcla, tu daño escala de verdad en ambos.</li>
<li>Un bonus de panoplia o un ítem clave que empuja un segundo elemento gratis, así que cogerlo no te cuesta nada.</li>
<li>Utilidad antes que daño bruto: un segundo elemento por el efecto de un hechizo concreto, no por su golpe.</li>
</ul>
<p>Fuera de eso, repartir suele ser dejar daño sin aprovechar.</p>

<h2>Elige el elemento que aman tus hechizos</h2>
<p>Coge el elemento con el que escalan tus hechizos de daño principales (míralos en la página de hechizos si dudas) y pondera ese y su dominio alto. Deja que el optimizador haga el resto. Un elemento limpio gana a dos a medias casi siempre.</p>

<p><em>Prueba ambos y compara: <a href="/setup/">monta un set</a> y mira el daño tú mismo.</em></p>
''',
            },
            'pt': {
                'title': "Mono-elemento ou multi-elemento? Escolha um e bata mais forte",
                'desc': "Espalhar seu dano em dois elementos passa segurança, mas costuma bater mais fraco do que apostar em um só. Veja por que o mono quase sempre ganha, e as poucas vezes que não.",
                'lead': "Espalhar seu dano em dois elementos passa segurança, mas costuma bater mais fraco do que apostar em um só. Veja por que se concentrar compensa, e quando não.",
                'body': '''
<h2>Por que um só elemento costuma ganhar</h2>
<p>Seu dano escala com o domínio correspondente: dano de fogo com domínio de fogo, e por aí. Espalhe seu equipamento entre dois elementos e cada ponto de domínio só ajuda metade dos seus golpes; jogue tudo em um e cada ponto conta sempre. O mesmo vale pra característica por trás (Força, Inteligência, Agilidade, Sorte). A concentração acumula: um set mono-elemento concentrado quase sempre bate mais que um bi-elemento diluído do mesmo nível.</p>

<h2>Na real, são seus controles</h2>
<p>Na ferramenta, mono-vs-multi não é um ajuste à parte: é como você pondera seus elementos. Suba um elemento e seu domínio, deixe os outros baixos, e o otimizador monta um batedor concentrado. Pondere dois elementos igual e ele espalha seu equipamento entre os dois numa boa. Então se seu build saiu espalhado quando você queria concentrado, olhe seus pesos.</p>

<h2>Quando o multi-elemento faz sentido mesmo</h2>
<p>Nem sempre é errado. Alguns casos querem de verdade dois elementos:</p>
<ul>
<li>Feitiços que batem em dois elementos, ou um kit que os mistura, seu dano escala de verdade nos dois.</li>
<li>Um bônus de conjunto ou um item-chave que empurra um segundo elemento de graça, então pegar não te custa nada.</li>
<li>Utilidade em vez de dano bruto: um segundo elemento pelo efeito de um feitiço específico, não pelo golpe.</li>
</ul>
<p>Fora isso, espalhar costuma ser deixar dano na mesa.</p>

<h2>Escolha o elemento que seus feitiços amam</h2>
<p>Pegue o elemento com que seus feitiços de dano principais escalam (confira na página de feitiços se tiver dúvida) e pondere ele e seu domínio alto. Deixe o otimizador fazer o resto. Um elemento limpo ganha de dois pela metade quase sempre.</p>

<p><em>Teste os dois e compare: <a href="/setup/">monte um set</a> e veja o dano você mesmo.</em></p>
''',
            },
            'de': {
                'title': "Mono-Element oder Multi-Element? Nimm eins und hau härter zu",
                'desc': "Den Schaden auf zwei Elemente zu verteilen fühlt sich sicher an, haut aber meist weicher zu als sich auf eins festzulegen. Hier ist, warum Mono fast immer gewinnt, und die wenigen Fälle, in denen nicht.",
                'lead': "Den Schaden auf zwei Elemente zu verteilen fühlt sich sicher an, haut aber meist weicher zu als sich auf eins festzulegen. Hier ist, warum Fokus sich lohnt, und wann nicht.",
                'body': '''
<h2>Warum ein Element meist gewinnt</h2>
<p>Dein Schaden skaliert mit der passenden Beherrschung: Feuerschaden mit Feuerbeherrschung, und so weiter. Verteil deine Ausrüstung auf zwei Elemente, und jeder Beherrschungspunkt hilft nur der Hälfte deiner Treffer; steck alles in eins, und jeder Punkt zählt jedes Mal. Dasselbe gilt für den Wert dahinter (Stärke, Intelligenz, Beweglichkeit, Glück). Fokus summiert sich: Ein konzentriertes Mono-Element-Set macht fast immer mehr Schaden als ein verwässertes Zwei-Element-Set desselben Levels.</p>

<h2>Es sind eigentlich nur deine Regler</h2>
<p>Im Tool ist Mono-vs-Multi keine eigene Einstellung: es ist, wie du deine Elemente gewichtest. Dreh ein Element und seine Beherrschung hoch, lass die anderen niedrig, und der Optimierer baut dir einen fokussierten Schläger. Gewichte zwei Elemente gleich, und er verteilt deine Ausrüstung gern auf beide. Wenn dein Build also verstreut rauskam, obwohl du Fokus wolltest, schau bei deinen Gewichten.</p>

<h2>Wann Multi-Element wirklich richtig ist</h2>
<p>Es ist nicht immer falsch. Ein paar Fälle wollen echt zwei Elemente:</p>
<ul>
<li>Zauber, die in zwei Elementen treffen, oder ein Kit, das sie mischt, dein Schaden skaliert wirklich auf beiden.</li>
<li>Ein Set-Bonus oder ein Schlüssel-Item, das ein zweites Element gratis mitbringt, sodass es dich nichts kostet.</li>
<li>Nutzen statt rohem Schaden: ein zweites Element für den Effekt eines bestimmten Zaubers, nicht für seinen Treffer.</li>
</ul>
<p>Außerhalb davon lässt Verteilen meist Schaden liegen.</p>

<h2>Wähl das Element, das deine Zauber lieben</h2>
<p>Nimm das Element, auf dem deine Hauptschadenszauber skalieren (schau sie auf der Zauberseite an, wenn du unsicher bist) und gewichte dieses und seine Beherrschung hoch. Den Rest macht der Optimierer. Ein sauberes Element schlägt zwei halbe fast jedes Mal.</p>

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
                'title': "You've got the build: now how do you actually get the gear?",
                'desc': "The optimizer hands you a perfect set, then reality hits: you don't own a single piece. Here's how to get each item (drop it, craft it, or buy it) and where to start.",
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
                'desc': "L'optimiseur te sort un set parfait, puis la réalité te rattrape : t'as pas une seule pièce. Voilà comment obtenir chaque item (le drop, le crafter ou l'acheter) et par où commencer.",
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
                'desc': "El optimizador te da un set perfecto, y entonces llega la realidad: no tienes ni una pieza. Aquí tienes cómo conseguir cada ítem (dropearlo, fabricarlo o comprarlo) y por dónde empezar.",
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
                'desc': "O otimizador te dá um set perfeito, e aí bate a realidade: você não tem uma peça sequer. Veja como conseguir cada item (dropar, fabricar ou comprar) e por onde começar.",
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
                'desc': "Der Optimierer gibt dir ein perfektes Set, dann kommt die Realität: Du besitzt kein einziges Teil. So bekommst du jedes Item (droppen, herstellen oder kaufen) und wo du anfängst.",
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
                'title': "Comparing builds side by side: stop guessing which set is better",
                'desc': "You've got two sets and you're not sure which one to wear. Throw them into the comparison and the Fashionista shows you exactly what you gain and lose, stat by stat.",
                'lead': "You've got two sets and you're not sure which one to wear. Instead of squinting at two tabs, put them side by side and let the numbers decide.",
                'body': '''
<h2>Why compare at all</h2>
<p>Two builds can look similar and play completely differently. One has 200 more vitality; the other hits 8% harder. Eyeballing that across a dozen slots is hopeless. The comparison lines both sets up column by column so the trade-offs jump out: no spreadsheet, no guesswork.</p>

<h2>How to set it up</h2>
<p>On any solution page (yours or a shared build), hit <strong>Add to comparison</strong>. Do it on a second build (or a third, or a fourth) and open the <a href="/choose_compare_sets/">comparison</a>. You can also paste build share links straight in. Your cart sticks around as you browse, so you can collect candidates and compare them all at once.</p>

<h2>Reading the result</h2>
<p>Each build gets a column; with exactly two, you also get a <em>diff</em> column that spells out the gap on every stat. Items shared between sets line up, so you instantly see which pieces actually differ and which carry over. That's usually where the real decision lives, not in the totals, but in the two or three slots that aren't the same.</p>

<h2>What to compare</h2>
<p>The obvious use is "my current set vs. the optimizer's suggestion." But it's just as good for "PvM vs. Kolossium variant," "cheap vs. expensive version," or settling a guild argument by dropping two shared builds in together. Anytime you're torn between two directions, compare them instead of debating them.</p>

<p><em>Got two builds in mind? <a href="/choose_compare_sets/">Compare them now.</a></em></p>
''',
            },
            'fr': {
                'title': "Comparer deux builds côte à côte : arrête de deviner quel set est meilleur",
                'desc': "T'as deux sets et tu sais pas lequel porter. Balance-les dans le comparateur et la Fashionista te montre exactement ce que tu gagnes et ce que tu perds, stat par stat.",
                'lead': "T'as deux sets et tu sais pas lequel porter. Plutôt que de loucher sur deux onglets, mets-les côte à côte et laisse les chiffres trancher.",
                'body': '''
<h2>Pourquoi comparer</h2>
<p>Deux builds peuvent sembler proches et jouer complètement différemment. L'un a 200 vita de plus ; l'autre tape 8% plus fort. Juger ça à l'œil sur douze emplacements, c'est mission impossible. Le comparateur aligne les deux sets colonne par colonne pour que les compromis sautent aux yeux : pas de tableur, pas de devinette.</p>

<h2>Comment le lancer</h2>
<p>Sur n'importe quelle page de solution (la tienne ou un build partagé), clique sur <strong>Ajouter à la comparaison</strong>. Fais-le sur un deuxième build (ou un troisième, ou un quatrième) et ouvre le <a href="/choose_compare_sets/">comparateur</a>. Tu peux aussi coller directement des liens de partage. Ton panier reste en place pendant que tu navigues, donc tu collectes des candidats et tu compares tout d'un coup.</p>

<h2>Lire le résultat</h2>
<p>Chaque build a sa colonne ; avec exactement deux, t'as en plus une colonne <em>diff</em> qui détaille l'écart sur chaque stat. Les items communs aux deux sets s'alignent, donc tu vois direct quelles pièces diffèrent vraiment et lesquelles reviennent. C'est en général là que se joue la vraie décision, pas dans les totaux, mais dans les deux-trois emplacements qui ne sont pas les mêmes.</p>

<h2>Quoi comparer</h2>
<p>L'usage évident, c'est "mon set actuel vs la propo de l'optimiseur". Mais c'est aussi parfait pour "variante PvM vs Kolizéum", "version cheap vs chère", ou clore un débat de guilde en mettant deux builds partagés ensemble. Dès que t'hésites entre deux directions, compare-les au lieu d'en débattre.</p>

<p><em>Deux builds en tête ? <a href="/choose_compare_sets/">Compare-les maintenant.</a></em></p>
''',
            },
            'es': {
                'title': "Comparar builds lado a lado: deja de adivinar qué set es mejor",
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
<p>El uso obvio es "mi set actual vs. la sugerencia del optimizador". Pero va igual de bien para "variante PvM vs. Koliseo", "versión barata vs. cara", o zanjar una discusión de gremio metiendo dos builds compartidos juntos. Cuando dudes entre dos direcciones, compáralas en vez de debatirlas.</p>

<p><em>¿Dos builds en mente? <a href="/choose_compare_sets/">Compáralos ahora.</a></em></p>
''',
            },
            'pt': {
                'title': "Comparar builds lado a lado: pare de adivinhar qual set é melhor",
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
<p>O uso óbvio é "meu set atual vs. a sugestão do otimizador". Mas serve igual pra "variante PvM vs. Koliseu", "versão barata vs. cara", ou encerrar uma discussão de guilda colocando dois builds compartilhados juntos. Sempre que estiver dividido entre duas direções, compare em vez de debater.</p>

<p><em>Dois builds em mente? <a href="/choose_compare_sets/">Compare agora.</a></em></p>
''',
            },
            'de': {
                'title': "Builds nebeneinander vergleichen: hör auf zu raten, welches Set besser ist",
                'desc': "Du hast zwei Sets und weißt nicht, welches du tragen sollst. Wirf sie in den Vergleich und die Fashionista zeigt dir genau, was du gewinnst und verlierst, Wert für Wert.",
                'lead': "Du hast zwei Sets und weißt nicht, welches du tragen sollst. Statt zwischen zwei Tabs zu schielen, stell sie nebeneinander und lass die Zahlen entscheiden.",
                'body': '''
<h2>Warum überhaupt vergleichen</h2>
<p>Zwei Builds können ähnlich aussehen und sich völlig anders spielen. Eins hat 200 Vitalität mehr; das andere haut 8% härter zu. Das über ein Dutzend Plätze nach Augenmaß zu beurteilen, ist aussichtslos. Der Vergleich stellt beide Sets Spalte für Spalte auf, sodass die Kompromisse ins Auge springen: keine Tabelle, kein Raten.</p>

<h2>So richtest du es ein</h2>
<p>Klick auf einer beliebigen Lösungsseite (deiner oder einem geteilten Build) auf <strong>Zum Vergleich hinzufügen</strong>. Mach das bei einem zweiten Build (oder einem dritten, oder vierten) und öffne den <a href="/choose_compare_sets/">Vergleich</a>. Du kannst auch Teil-Links direkt einfügen. Dein Warenkorb bleibt beim Stöbern erhalten, du sammelst also Kandidaten und vergleichst sie alle auf einmal.</p>

<h2>Das Ergebnis lesen</h2>
<p>Jedes Build bekommt eine Spalte; bei genau zweien gibt es zusätzlich eine <em>Diff</em>-Spalte, die den Abstand bei jedem Wert aufschlüsselt. Items, die sich beide Sets teilen, stehen auf einer Linie, sodass du sofort siehst, welche Teile sich wirklich unterscheiden und welche gleich bleiben. Da liegt meist die echte Entscheidung, nicht in den Summen, sondern in den zwei, drei Plätzen, die nicht gleich sind.</p>

<h2>Was du vergleichen kannst</h2>
<p>Der naheliegende Einsatz ist "mein aktuelles Set vs. der Vorschlag des Optimierers". Aber es taugt genauso für "PvM- vs. Kolosseum-Variante", "günstige vs. teure Version" oder um einen Gildenstreit zu klären, indem du zwei geteilte Builds zusammenwirfst. Immer wenn du zwischen zwei Richtungen schwankst, vergleich sie, statt zu diskutieren.</p>

<p><em>Zwei Builds im Kopf? <a href="/choose_compare_sets/">Vergleich sie jetzt.</a></em></p>
''',
            },
        },
    },

    'understanding-your-solution': {
        'published': '2026-07-01',
        'i18n': {
            'en': {
                'title': "Reading your solution: what the optimizer's result page is actually telling you",
                'desc': "The Fashionista handed you a full set. Now what? How to read the solution page: the items it picked, the stats you end up with, and the warnings that actually matter.",
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
                'title': "Lire ta solution : ce que la page de résultat de l'optimiseur te dit vraiment",
                'desc': "La Fashionista t'a sorti un set complet. Et maintenant ? Comment lire la page de solution : les items choisis, les stats que t'obtiens au final, et les avertissements qui comptent vraiment.",
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
                'title': "Leer tu solución: lo que la página de resultado del optimizador te dice de verdad",
                'desc': "La Fashionista te sacó un set completo. ¿Y ahora? Cómo leer la página de solución: los ítems elegidos, las estadísticas que acabas teniendo y los avisos que de verdad importan.",
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
                'title': "Ler sua solução: o que a página de resultado do otimizador está mesmo te dizendo",
                'desc': "A Fashionista te entregou um set completo. E agora? Como ler a página de solução: os itens escolhidos, os atributos que você acaba tendo e os avisos que realmente importam.",
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
                'title': "Deine Lösung lesen: was dir die Ergebnisseite des Optimierers wirklich sagt",
                'desc': "Die Fashionista hat dir ein komplettes Set gebaut. Und jetzt? Wie du die Lösungsseite liest: die gewählten Items, die Werte, die am Ende rauskommen, und die Warnungen, die wirklich zählen.",
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
                'title': "Tuning your weights: how to tell the optimizer what actually matters",
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
                'title': "Bien régler tes poids : dire à l'optimiseur ce qui compte vraiment",
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
                'title': "Ajustar tus pesos: cómo decirle al optimizador lo que de verdad importa",
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
                'title': "Ajustando seus pesos: como dizer ao otimizador o que realmente importa",
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
                'title': "Gewichte richtig einstellen: dem Optimierer sagen, was wirklich zählt",
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
                'title': "Planning a maging run: use the simulator before you burn your kamas",
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
                'title': "Planifier ta forgemagie : passe par le simulateur avant de brûler tes kamas",
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
                'title': "Planificar tu forjamagia: pasa por el simulador antes de quemar tus kamas",
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
                'title': "Planejando sua forjamagia: passe pelo simulador antes de queimar seus kamas",
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
    data = {'slug': slug, 'published': guide['published']}
    data.update(block)
    return data
