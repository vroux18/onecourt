# OneCourt — notes pour Claude

App statique mono-page (aucun framework, aucun build) qui affiche les créneaux de courts dispo à Paris (tennis municipal / padel / foot placeholder). Lire `docs/HANDOFF.md` avant toute modif structurelle.

## Règles du projet

- **Zéro dépendance** : `app/index.html` est du HTML/CSS/JS vanilla inline ; les scrapers sont Python stdlib only. Ne pas introduire de framework, de bundler ni de package.
- **Un seul schéma JSON pour tous les sports** (voir README) — l'UI a un seul code de rendu. Toute évolution de schéma doit rester compatible tennis ET padel.
- **Les scrapers écrivent dans le répertoire courant** : les lancer depuis `app/`.
- **Prod = Artifact Claude** `b268f8f2-63c1-48fe-85bd-4e8023b970fb`, republié chaque matin par une tâche planifiée qui ne régénère JAMAIS index.html (elle republie l'index exact + les JSON). Si on modifie index.html ici, il faut le republier sur l'artifact pour que la prod change.
- `foot.json` n'existe pas volontairement — l'app gère le 404 et affiche l'état "pas de source".
- Langue de l'UI et des messages : français.

## Lancer en local

Serveur de preview défini dans `.claude/launch.json` (port 8020, sert `app/`).
