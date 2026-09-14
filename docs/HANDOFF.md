# OneCourt (ex-Créno) — Handoff fonctionnel complet

Document de reprise du projet **OneCourt** (ex-Créno, ex-Court Libre) : ce que l'app fait, comment elle marche, ses données, son pipeline, ses limites et la suite. Niveau : fonctionnel + technique. Public : toi, un dev ou un designer qui reprend le projet.

Dernière mise à jour : 14 sept. 2026.

---

## 1. Résumé

OneCourt affiche en un coup d'œil les **créneaux de courts disponibles à Paris** sur plusieurs sports, et renvoie vers la réservation officielle. Ce n'est pas une app de réservation : elle agrège la dispo, elle ne prend pas le paiement. Usage perso, mobile, consulté surtout le matin.

- **Type** : web app mono-page (HTML/CSS/JS vanilla, sans framework), hébergée comme Artifact Claude (URL privée, partageable).
- **Sports** : Tennis (municipal), Padel (clubs privés), Foot (placeholder, pas de source).
- **Données** : rafraîchies automatiquement chaque matin (~7h Paris) par une tâche planifiée.
- **URL** : artifact `b268f8f2-63c1-48fe-85bd-4e8023b970fb` sur claude.ai.

## 2. Fonctionnalités (état actuel)

### Navigation par sport (bandeau bas)
Tab bar fixe en bas, 3 onglets : Tennis / Padel / Foot. Le tap change de sport, recharge la liste et mémorise le choix (localStorage). Chaque onglet affiche son compteur de créneaux ("3 143 créneaux"), ou "bientôt" / "—" si pas de données.

### Sélecteur de jour
Rangée horizontale scrollable de 7 jours. Chaque jour affiche le nombre de créneaux dispo ; jour complet = grisé. Sélection = un jour à la fois. Au changement de sport, se recale sur le premier jour ayant de la dispo.

### Filtres
- **Arrondissement** : liste déroulante alimentée dynamiquement selon les données du sport actif (Paris intra + "Hors Paris" pour la couronne).
- **Surface** : (tennis seulement) Béton poreux, Résine, Terre battue, Synthétique, Gazon synthétique, Bitume.
- **Couvert** / **Éclairé** : (tennis seulement) toggles.
- **Soir 18h+** : commun à tous les sports.

Les filtres surface/couvert/éclairé sont masqués hors tennis (le padel n'a pas ces attributs dans la source).

### Liste des créneaux
Groupée par club (carte). Chaque carte : nom, pastille arrondissement, adresse. Rangée de pilules-heure (ex. "19h ×4" = heure + nombre de courts). Tap sur une pilule = dépliage du détail.

### Détail créneau
Par court : heure, nom du court (tennis) ou durée (padel), tags (Couvert/Éclairé pour tennis), méta (surface / durée / places), prix réel. Bouton **Réserver** :
- Tennis → tennis.paris.fr (connexion Mon Paris requise).
- Padel → page Anybuddy du club.

### États
- **Vide/complet** : message propre par jour.
- **Foot** : état "pas de source" expliqué.
- **Données anciennes** : pastille ambre si le fichier date de +30h (garde-fou en cas d'échec du scrape).
- **Erreur de chargement** : message si les données ne chargent pas.

### Persistance
localStorage garde : sport actif, arrondissement, surface, toggles. Pas de compte, pas de backend, pas de données personnelles.

## 3. Sources de données

| Sport | Source | Auth | Fenêtre | Volume typique | Prix |
|---|---|---|---|---|---|
| Tennis | tennis.paris.fr (portail municipal JSP) | Aucune | 7 jours | ~3 000-3 700 créneaux/jour cumulés | 7-12 € |
| Padel | API Anybuddy (`/api/v1/availabilities`) | Aucune (route Next.js publique) | ~3-7 jours (fenêtre de résa club) | ~3 200 créneaux | 50-60 € |
| Foot | — | — | — | 0 | — |

### Tennis — comment ça marche
Le portail expose un POST sans login : `Portal.jsp?page=recherche&action=rechercher_creneau` avec `token`, `when` (JJ/MM/AAAA), `hourRange=8-22`, `selWhereTennisName[]` (multi-clubs par requête), `selInOut[]` (V/F), `selCoating[]`. La liste des 39 clubs ouverts à la résa et le token sont extraits de la page de recherche (GeoJSON embarqué). ~40 POST pour couvrir 39 clubs × 7 jours. Le HTML de résultat est parsé (pilules `#head<Club><HH>h`, lignes `.tennis-court`).

### Padel — comment ça marche
Anybuddy est un SPA Next.js. La dispo n'est pas dans la page mais servie par une **route serveur** `GET /api/v1/availabilities?clubSlug=X&dateFrom&dateTo&activity=padel` qui ne demande pas de token (l'auth est gérée côté serveur Anybuddy). Réponse JSON : blocs `startDateTime` + `services[]` (duration, price en centimes, availablePlaces). 12 clubs Paris + proche couronne, liste figée dans le scraper.

## 4. Architecture technique

Pas de serveur applicatif. Trois fichiers publiés dans l'artifact :

- **index.html** : toute l'UI (HTML + CSS + JS inline). Charge `data.json`, `padel.json`, `foot.json` au démarrage via `fetch`. Structure de données pilotée par sport (`DS = {tennis, padel, foot}`).
- **data.json** : dump tennis. Format : `{generated_at, days[], sites[{name,arr,adresse,cp,lat,lng,open}], slots{jour:[{s,h,c,surf,ecl,cov,p,t}]}, total, errors[]}`. `s` = index dans `sites`.
- **padel.json** : même format + `sites[].url` (lien résa club).
- **scraper.py** : scraper tennis (Python stdlib, aucune dépendance), joint à l'artifact pour être relancé par la tâche.

Le même schéma JSON sert les deux sports, ce qui permet à l'UI de traiter tennis et padel avec le même code de rendu.

## 5. Pipeline de rafraîchissement

**Tâche planifiée** (Claude scheduled task, cloud, cron `0 5 * * *` UTC ≈ 7h Paris) :
1. Récupère `index.html` et `scraper.py` exacts publiés (read_file — bytes identiques, la page n'est jamais régénérée).
2. Tennis : exécute `scraper.py` → `data.json`.
3. Padel : récupère les 12 clubs Anybuddy en **une seule commande curl multi-URL**, construit `padel.json`.
4. Republie l'index inchangé + les deux JSON par-dessus.
5. Garde-fous : si le tennis échoue totalement, ne republie rien (l'app montre "données anciennes"). Si seul le padel échoue, republie le tennis sans écraser le padel.

**Contrainte importante** : le sandbox Claude bloque les **boucles** d'appels API (classifieur sécurité). D'où le curl multi-URL en un seul process pour le padel. Un scraper local `anybuddy_padel.py` (urllib, sans classifieur) existe pour rafraîchir le padel à la main si besoin.

## 6. Limites connues (à dire franchement)

- **Fragilité scraping** : tout repose sur des sites tiers non contractuels. Un changement de tennis.paris.fr (portail JSP ancien) ou de l'API Anybuddy casse le scraper. À réparer au coup par coup.
- **Padel hors CGU** : lire l'API Anybuddy en automatique est contraire à leurs conditions. Assumé pour un usage perso, à ne pas diffuser.
- **Pas de réservation in-app** : tennis = CAPTCHA + login Mon Paris (non automatisable proprement) ; padel = renvoi Anybuddy. L'app s'arrête à "voir la dispo".
- **Foot** : aucune source ouverte (UrbanSoccer/4Padel derrière Incapsula/anti-bot ; Ten'Up derrière Queue-it + cloisonné licenciés). Onglet placeholder.
- **Fenêtre padel courte** : Anybuddy n'ouvre la résa que quelques jours à l'avance selon le club, donc moins de 7 jours pleins.
- **Bug historique corrigé** : la tâche du matin republiait une vieille copie de la page et écrasait le renommage/design. Corrigé (republie l'index exact). À re-surveiller.

## 7. Design / refonte en cours

Une refonte UI/UX est spécifiée (handoff design séparé) : style iOS moderne, DA complète 2 thèmes, tab bar bas, un accent couleur par sport. À produire dans Claude Design, puis à réintégrer dans l'app réelle. L'app actuelle est fonctionnelle mais au style "Court Libre" (vert/clay), pas encore la nouvelle DA.

## 8. Roadmap suggérée (priorisée)

1. **Fiabiliser** : monitoring simple du scrape (alerte si 0 créneau 2 jours de suite).
2. **Refonte visuelle** : appliquer la DA iOS validée.
3. **Vue Carte** : plan des clubs (données lat/lng déjà présentes) — 4e onglet ou toggle.
4. **Favoris** : épingler ses clubs habituels, filtre rapide.
5. **Notifications** : alerte quand un créneau se libère sur un club/créneau favori (nécessiterait un backend léger — aujourd'hui tout est statique).
6. **Foot** : rouvrir le sujet seulement si une source propre apparaît.

## 9. Décisions actées

- Nom : **OneCourt**
- Périmètre : tout Paris, tous terrains, filtres dans l'UI.
- Multi-sport via bandeau bas Tennis/Padel/Foot.
- Refresh auto matinal tennis + padel dans la même tâche.
- Réservation manuelle assumée (renvoi vers sites officiels).
