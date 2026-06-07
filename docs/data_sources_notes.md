# Notes sur les sources de données (Retro, Touch, HDV)

Quelques notes sur d'où viennent (ou peuvent venir) les données des différentes
versions, et sur ce qui est faisable ou non.

## Dofus Retro et Dofus Touch — faits

Les deux sont implémentés et tirent leurs données directement d'Ankama :

- **Retro** : les fichiers "lang" officiels du CDN Retro. Détails dans
  [retro_data_from_ankama.md](retro_data_from_ankama.md).
- **Touch** : le backend de données du client Touch (POST `/data/map`). Détails
  dans [touch_data_sources.md](touch_data_sources.md).

Pistes écartées en cours de route, pour mémoire :

- `api.dofusdb.fr` — API riche et multilingue, mais ce sont des données Dofus
  moderne (Unity 3), pas du Retro 1.29. Redondant avec dofusdude.
- `Spx0001/DofusAPI` — malgré son titre « API Dofus 1.29 », c'est en fait un
  émulateur de serveur / gestion de comptes en PHP, pas une base d'items.
- `bot4dofus/Datafus` — dumps JSON Dofus moderne, pas Retro.
- `dofapi.fr` — historiquement la source Touch en JSON, mais l'API n'est plus
  joignable aujourd'hui. Le crawler `crawlit-dofus-encyclopedia-parser` qui
  l'alimentait scrape l'encyclopédie `www.dofus-touch.com` ; on garde ça comme
  solution de repli (voir touch_data_sources.md).

## HDV / budget kamas — bloqué

Pour la contrainte de budget (prix HDV), il n'y a pas de voie propre :

- L'accès automatisé aux prix HDV est **interdit par les CGU d'Ankama**. C'est un
  risque juridique, pas seulement technique.
- **Vulbis** est hors-ligne depuis Dofus 3.0.
- Les outils existants (La Boubourse, KamaMaster) n'exposent pas d'API publique et
  reposent sur de la saisie communautaire ou du scraping en zone grise.

La seule voie conforme serait la **saisie communautaire des prix** : les
utilisateurs renseignent les prix de leurs items par serveur (un modèle
`ItemPrice(item, server, price, updated_by, updated_at)`), et la contrainte de
budget du solveur s'appuie là-dessus. Conforme aux CGU et sans dépendance externe
fragile, mais la couverture dépend de la communauté — à traiter comme une vraie
feature si on s'y attaque.

## Liens

- [dofusdude / doduda](https://github.com/dofusdude/doduda) — Dofus 2 / 3 (déjà utilisé)
- [api.dofusdb.fr](https://api.dofusdb.fr/items) — API live, Dofus moderne
- [dofapi/dofapi](https://github.com/dofapi/dofapi) — Dofus + Touch (hors-ligne au test)
- [Forum Ankama — accès prix HDV interdit](https://www.dofus.com/fr/forum/1003-divers/2298605-api-hdv)
