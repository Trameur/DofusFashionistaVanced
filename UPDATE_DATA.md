# Updating the data

From the repository, with the Python that already runs the `update_data_*.py` scripts:

```powershell
py update_all.py
```

For each game, the launcher shows the local version, the Ankama client version
and the version that can really be imported. Answer with the numbers or names of
the versions (`1,4`, `dofus3,touch`), `changed` for the ones that changed, or
`all` for the five Dofus versions. Wakfu is available with `6` or `wakfu` and
stays an explicit choice, since it is experimental. Then choose with or without
images for each version, and confirm. Pressing Enter without a choice quits.

The old scripts can still be run directly; the launcher reuses their steps and
their arguments. The terminal shows each step with its title and its duration,
with a reminder every 30 seconds during a long operation. The step number shown
is the one in the log name (`dofus3-05-items-obtainment.log` for "Dofus 3 | 05").

## Commands

```powershell
py update_all.py --list
py update_all.py --dry-run --versions dofus3,beta --images no
py update_all.py --versions dofus3,touch --images yes --yes
py update_all.py --restore .update-reports\<folder>
py update_all.py --restore .update-reports\<folder> --versions beta
py update_all.py --clean-reports
```

`--list` and `--dry-run` read the sources without changing anything. `--list`
also gives the space taken by `.update-reports`. `--dry-run` gives the size and
duration of the image backup, the free space, the databases open in another
program and any stopped import that needs a restore. `--yes` needs explicit
choices for the versions and the images. `--restore` and `--clean-reports` are
described below. No mode commits, pushes or deploys.

## How a run goes

Before any import, the launcher refuses to start if a database it has to replace
is open in another program (dev server, DB Browser...) and names the file. On
Windows, a database that is merely open is enough to block its replacement. It
also refuses to start while an import stopped halfway has not been restored (see
"Hard stop").

Each version is handled alone, one after the other:

1. check that the source has not changed since it was chosen;
2. inventory before the import and backup of its files: database, dump,
   `spell_reference`, `spell_states`, `transformed_wakfu.json` for Wakfu,
   `retro_damage_spells.json` for Dofus Retro, and the shared files as they are
   at that moment (`fashionista_version.py`, `dynamic_translations.py`,
   `dofus_constants*.py`);
3. record of the JSON files tracked by git under `itemscraper/` (see
   "Intermediate files");
4. import by its `update_data*.py` script;
5. inventory after the import and data checks.

If everything passes, the version label in `fashionista_version.py` and its
entry in `.update-reports/state.json` are written right away. When a new patch
starts, its `PATCH_TIMELINE` entry is added and the terminal says so. For Dofus
Touch and Dofus Retro, the `WATCHED_*` markers of the same file (Touch asset
pack, Retro build, languages and image digest) take the values of the imported
source, so that `itemscraper/check_game_versions.py` compares the same thing as
the launcher. The Retro image digest only changes if the images were imported.
If the import or the checks fail, only that version is restored and the launcher
moves on to the next one. If that restore stays incomplete (locked file), the
launcher stops: the next versions are marked `NOT STARTED` with the cause, and
the tests are not run. Ctrl+C restores the version in progress and then stops.

Network steps (downloads, mirror, scraping, `data/sets`, `data/spells`, images)
are run again once after 20 seconds if they fail; the log of the first attempt
is kept next to it (`.attempt-1.log`). A step that runs past its time limit is
not run again. Other steps are never run again.

## Images

If at least one version downloads images, the image folders of
`fashionsite/chardata/static` are backed up once at the start. The
`staticfiles` copy is not backed up: it is not read locally and `collectstatic`
rebuilds it on deployment. Before this backup, the launcher checks that the disk
has 1.2 times its size free; otherwise it refuses to start and gives both
numbers.

When a version fails, only the images that were readable before it and became
missing or unreadable are put back from this backup. New or updated images stay
in place: they come from Ankama's sources. The images of the versions not chosen
are checked the same way at the end.

## Intermediate files

The imports rewrite JSON files tracked by git under `itemscraper/`
(`transformed_equipment.json`, `all_*.json`, `touch_raw/`...). Before each
version, the launcher copies the ones that were already modified locally and
records the size and date of all the others. When the version is restored,
every file it changed comes back: from the copy if it was already modified,
otherwise with `git checkout HEAD -- <file>`. A file changed afterwards by a
later version is kept and listed. Code files (`.py`) are never touched, so that
an edit made during the import is not lost.

## Checks after the imports

Run only if at least one version was imported and no restore is incomplete:

1. a real generation of a level 50 earth Iop in each Dofus version (and the
   Wakfu solver checks if Wakfu is chosen). If an imported version can no longer
   generate a build, its data is restored, then the generation runs once more:
   anything that still fails needs review;
2. weapon data check (`check_version_weapon_data.py`);
3. full Django suite with `--settings=fashionsite.settings_test`.

A failure of the last two restores nothing: the data stays, the status becomes
`IMPORTED, TESTS TO REVIEW`, the terminal gives the number of failing tests and
the first three, and the summary lists them all with the log. A failing check
without a named test shows its error. Test expectations are never changed
automatically: a human decides whether it is a game change or an import defect.

## What is checked

- Dofus 3, Dofus 3 Beta and Dofus 2: the item API tag must have its spell and
  language archive. A newer Ankama client is reported separately.
- Dofus Touch: game build read from `window.buildVersion` in the production
  client, asset pack and languages from its official configuration.
- Dofus Retro: versions of the language files in the five languages and digest
  of the images in the client manifest.
- Wakfu: version of the official feed and of the last local transformation. The
  spells are harvested for the imported build.
- Before and after: SQLite integrity, rows per table, emptied tables, orphan
  references, lost or reassigned ids, added or removed stats, new source
  effects, changed items and spells, items removed by Ankama and kept hidden,
  database and dump agreement, referenced images present and readable.

These block a version: a deleted table, a loss of more than 3% in a table, a
lost or reassigned id, an inconsistent dump, an empty essential table, a lost
existing image. A legitimate removal by Ankama therefore needs a human review,
except in the two Wakfu cases below.

Wakfu: an item that the old database had and the new build no longer has is
kept under its id with `removed = 1`, like the items removed from the Dofus
versions: the site hides it, saved builds still find it. The count appears in
the log of the "Building the database" step. For `item_recipes`,
`item_recipe_ingredient_names` and `item_craft_jobs`, a loss of more than 3% is
only a warning when the mirror's `recipes.json` shrank by at least the share
above those 3%; the Wakfu inventory keeps the mirror's recipe count for this
comparison.

## Summary

Each run keeps a `.update-reports/<date>-<pid>/` folder:

- `RECAP.md`: overall status on the first line, one block per version (status,
  local version -> imported version, items and spells added, removed and
  changed, new stats, new image problems, zero counts grouped on one line, kept
  DofusDB data on one line, steps with warnings), the failing tests, the command
  to finish an incomplete restore, then the command to undo;
- `report.json`, the `<version>-before.json` and `-after.json` inventories, the
  logs of each step and of the checks;
- `<version>/`: backup of each version, `images/`: image backup,
  `images-changed.json`: images changed during the run.

Status of a version: `IMPORTED`, `FAILED, RESTORED`, `RESTORE INCOMPLETE` or
`NOT STARTED` (nothing was changed, the cause is given). Overall status:
`IMPORTED`, `PARTLY IMPORTED`, `FAILED` or `INTERRUPTED`, followed when needed by
`, TESTS TO REVIEW`, `, ERRORS` or `, RESTORE INCOMPLETE`.

Exit codes: `0` everything imported and tests green, `2` everything imported but
tests to review, `1` at least one failed version or an incomplete restore, `130`
interrupted. Even after a Ctrl+C at the very end of a run, the lock is released
and `report.json` and `RECAP.md` are written.

## Restore

The restore tries every file. Putting a database back also deletes its
`-journal`, `-wal` and `-shm` files, which would otherwise replay the cancelled
import into the restored database; if one of them is locked, the database counts
as not restored. A database identical to the backup, or left as it was before
the import, is not rewritten. A file locked by Windows is tried again for up to
60 seconds at the end; a file missing from the backup is reported without
stopping the rest.

When a restore is incomplete or was interrupted, the terminal and the summary
give the command that finishes it, limited to the versions concerned:

```powershell
py update_all.py --restore .update-reports\<folder> --versions beta
```

With `--versions`, only those versions and their `state.json` entries are put
back. If a later version of the same run stays imported, its changes are kept:
only the restored version's label is put back in `fashionista_version.py`,
and a shared file changed afterwards by the other version is kept and listed.

Without `--versions`, `--restore` undoes the whole run: the versions from the
newest to the oldest, then the changed images, and the `state.json` entries it
wrote. Running the command again finishes a partial restore. The launcher
refuses to restore a version that a newer run has imported since, and names that
run; `--force` overrides this. Application data (accounts, characters, builds)
is never touched. A restore error is shown in one sentence, without a Python
traceback.

## Hard stop

While a version is being imported, the file `<folder>/<version>.importing`
exists; it goes away as soon as the version is imported or restored. The
`.update-data.lock` lock names the folder of the run. If the window is closed or
Windows restarts during an import, the next launcher recovers the lock, then
refuses to start and shows the exact command:

```powershell
py update_all.py --restore .update-reports\<folder> --versions dofus3
```

Once that version is restored, the `.importing` file goes away and the launcher
starts normally again.

## Disk space

Each run with images keeps an image backup. `py update_all.py --clean-reports`
lists the image backups older than the last three (old runs in the `backup/`
format included), with their size, and deletes them only after you type `yes`
(`oui` is accepted too). `--yes` is not enough. A run whose restore is
unfinished is always kept. Logs, summaries and data backups stay.

## Kept sources

The DofusDB API is disabled in this launcher. Mount appearances, and monster
grades and subareas for Dofus 3 and Dofus 3 Beta, are taken from the backup of
the same version and saved in the database and its dump. Appearances follow the
Ankama id and type of each mount, so they survive a rename. Dofus 3 and Dofus 3
Beta monster artwork stays local. The summary says so once per version.

The "without images" choice also applies to Dofus Touch spells and Dofus Retro
artwork. With images, the scripts reuse their usual caches.

## Dofus Touch and Dofus Retro versions

Dofus Touch uses several independent numbers. For example, on 23 September
2026:

| Number | Meaning | Source |
|---|---|---|
| Client `3.14.2` | Version of the app installed on the phone | Phone screen; not detected by the launcher |
| Build `1.74.5` | Game version shown in that app | `window.buildVersion` in the [production client](https://dt-proxy-production-login.ankama-games.com/build/script.js) |
| Assets `3.3.6_…` | Graphics pack served by the CDN | `assetsUrl` in the [official configuration](https://dt-proxy-production-login.ankama-games.com/config.json?lang=fr) |

The launcher presents the game build as the available version, reading only the
start of the JavaScript file without running it. An unreadable or ambiguous
build makes the source unavailable. A change of the build or of the assets
triggers an update.

For Dofus Retro, `1.49.5.5656.445-401e092` becomes `1.49.5` in the game version
line. The full Cytrus id is still shown and is kept for the checks.

## Requirements and concurrency

The launcher uses the existing dependencies and
`fashionsite/fashionsite/settings_test.py` set up with SQLite. It refuses to
start if that file is missing or if the Fashionista configuration points to
another repository. The Dofus Retro image steps may need Java/JPEXS and resvg:
the tools in `~/Documents/fashionista-loop/tools/flash/` are found
automatically, and the `JAVA_EXE`, `FFDEC_JAR` and `RESVG_EXE` variables take
precedence.

`.update-data.lock` stops two launchers from running at the same time. The
launcher also registers itself in the "En cours" section of
`~/Documents/fashionista-loop/RUNNING.md` if that file exists (another file with
`--running-file`) and refuses to start if other work is listed there; the
section ends at the next heading. After a forced stop, the old lock is recovered
if no Python program from the repository, solver or image job is still running;
otherwise the launcher names that program and asks you to close it (the dev
server included) before running again.

A step has one hour, and the full import of a version four hours:

```powershell
py update_all.py --step-timeout 7200
```
