# OneCourt

Web app mobile qui affiche en un coup d'œil les **créneaux de courts disponibles à Paris** (tennis municipal, padel, foot à venir) et renvoie vers la réservation officielle. Ce n'est pas une app de réservation : elle agrège la dispo, elle ne prend pas le paiement.

Anciennement "Créno" (et avant "Court Libre"). Usage perso, consulté surtout le matin.

## Structure

```
app/
  index.html          Toute l'UI — HTML/CSS/JS vanilla, mono-page, sans framework
  data.json           Dump tennis (généré par scrapers/tennis_paris.py)
  padel.json          Dump padel (généré par scrapers/anybuddy_padel.py)
  (foot.json)         Absent — l'app gère le 404 et affiche l'état "pas de source"
scrapers/
  tennis_paris.py     Scrape tennis.paris.fr (portail JSP, sans login) — stdlib only
  anybuddy_padel.py   Scrape l'API publique Anybuddy pour 12 clubs padel — stdlib only
docs/
  HANDOFF.md          Handoff fonctionnel complet (contexte, sources, limites, roadmap)
```

## Lancer en local

L'app est 100 % statique. Il faut juste un serveur HTTP (les `fetch` de JSON ne marchent pas en `file://`) :

```bash
cd app && python -m http.server 8020
```

Puis ouvrir http://localhost:8020.

## Rafraîchir les données

```bash
cd app && python ../scrapers/tennis_paris.py     # → data.json (~2-3 min, ~40 requêtes)
cd app && python ../scrapers/anybuddy_padel.py   # → padel.json (~15 s, 12 requêtes)
```

Les deux scripts écrivent dans le répertoire courant — les lancer depuis `app/`.

## Format des données

Même schéma JSON pour tous les sports (l'UI a un seul code de rendu) :

```jsonc
{
  "generated_at": "2026-09-14T05:04:00+00:00",
  "days": ["2026-09-14", "..."],          // 7 jours
  "sites": [{ "name": "", "arr": 12, "adresse": "", "cp": "", "lat": 0, "lng": 0, "open": true, "url": "..." }],
  "slots": { "2026-09-14": [{ "s": 0, "h": 19, "c": "Court 1", "surf": "", "ecl": false, "cov": false, "p": "8 €", "t": "" }] },
  "total": 3143,
  "errors": []
}
```

`s` = index dans `sites`. `sites[].url` (padel) = lien de résa du club ; pour le tennis le lien est global (tennis.paris.fr). L'UI affiche une pastille "données anciennes" si `generated_at` a plus de 30 h.

## Déploiement

Publié comme Artifact Claude (`b268f8f2-63c1-48fe-85bd-4e8023b970fb`), rafraîchi chaque matin (~7h Paris) par une tâche planifiée qui relance les scrapers et republie les JSON **sans jamais régénérer index.html**. Garde-fous : échec tennis total → rien n'est republié ; échec padel seul → tennis republié, padel conservé.

Voir [docs/HANDOFF.md](docs/HANDOFF.md) pour le détail des sources, les limites connues (fragilité scraping, CGU Anybuddy, pas de source foot) et la roadmap.
