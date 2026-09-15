#!/usr/bin/env python3
"""Scraper des créneaux padel disponibles via l'API publique Anybuddy (sans login).

Sortie: padel.json — même schéma que data.json (tennis), avec sites[].url en plus.
Stdlib uniquement (urllib). Usage perso : à lancer localement, puis republier
padel.json à côté de index.html.
"""
import gzip
import io
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

API = "https://www.anybuddyapp.com/api/v1/availabilities"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
DAYS = 8
DELAY = 0.7

# 12 clubs Paris + proche couronne. slug = segment /club/<slug>/padel de l'URL Anybuddy.
CLUBS = [
    {"slug": "aquaboulevard-de-paris", "name": "Forest Hill Aquaboulevard", "arr": 15, "adresse": "4-6 Rue Louis Armand", "cp": "75015", "lat": 48.831068, "lng": 2.275841},
    {"slug": "paris-padel", "name": "Paris Padel", "arr": 20, "adresse": "340 Rue des Pyrénées", "cp": "75020", "lat": 48.87424, "lng": 2.388806},
    {"slug": "sportfield-bercy-paris", "name": "Sportfield Paris 12 - Bercy", "arr": 12, "adresse": "5 Boulevard Poniatowski", "cp": "75012", "lat": 48.829798, "lng": 2.390682},
    {"slug": "les-padelistes-bercy-paris", "name": "Padelistes Bercy - Paris 12", "arr": 12, "adresse": "20 Rue Escoffier", "cp": "75012", "lat": 48.826549, "lng": 2.391712},
    {"slug": "4padel-paris-20", "name": "4PADEL Paris 20", "arr": 20, "adresse": "Avenue Benoît Frachon", "cp": "75020", "lat": 48.853363, "lng": 2.415475},
    {"slug": "ucpa-sport-station-a-paris-paris", "name": "UCPA Sport Station Paris 19", "arr": 19, "adresse": "28 Allée Rose Dieng-Kuntz", "cp": "75019", "lat": 48.896481, "lng": 2.371917},
    {"slug": "padel-15-paris", "name": "Padel 15", "arr": 15, "adresse": "115 Rue Castagnary", "cp": "75015", "lat": 48.82983, "lng": 2.304798},
    {"slug": "sportfield-paris", "name": "Sportfield Paris 16 - Tour Eiffel", "arr": 16, "adresse": "4 Rue Maurice Bourdet", "cp": "75016", "lat": 48.851219, "lng": 2.278951},
    {"slug": "trinquet-village-paris", "name": "Trinquet Village", "arr": 16, "adresse": "8 Quai Saint-Exupéry", "cp": "75016", "lat": 48.837925, "lng": 2.264748},
    {"slug": "4-padel-saint-ouen-saint-ouen-sur-seine", "name": "4Padel Saint-Ouen", "arr": 0, "adresse": "29 Rue Emile Cordon", "cp": "93400", "lat": 48.912904, "lng": 2.341505},
    {"slug": "forest-hill-nanterre-la-defense", "name": "Forest Hill Nanterre-La Défense", "arr": 0, "adresse": "9 avenue de la Liberté", "cp": "92000", "lat": 48.888143, "lng": 2.20755},
    {"slug": "forest-hill-marnes-la-coquette", "name": "Forest Hill Marnes-La-Coquette", "arr": 0, "adresse": "1Bis Boulevard de la République", "cp": "92430", "lat": 48.837534, "lng": 2.165808},
]

opener = urllib.request.build_opener()
opener.addheaders = [("User-Agent", UA), ("Accept", "application/json"), ("Accept-Encoding", "gzip")]


def fetch_json(url, retries=3):
    for attempt in range(retries):
        try:
            with opener.open(url, timeout=60) as r:
                raw = r.read()
                if r.headers.get("Content-Encoding") == "gzip" or raw[:2] == b"\x1f\x8b":
                    raw = gzip.GzipFile(fileobj=io.BytesIO(raw)).read()
                return json.loads(raw.decode("utf-8", "replace"))
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(3 * (attempt + 1))


def iter_blocks(payload):
    """L'API renvoie une liste de blocs {startDateTime, services[]} — parfois
    enveloppée dans un objet. On normalise."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("availabilities", "data", "items", "results"):
            if isinstance(payload.get(key), list):
                return payload[key]
    return []


def main():
    t0 = time.time()
    days = [date.today() + timedelta(days=d) for d in range(DAYS)]
    date_from, date_to = days[0].isoformat(), days[-1].isoformat()

    sites = []
    for c in CLUBS:
        sites.append({
            "name": c["name"], "arr": c["arr"], "adresse": c["adresse"], "cp": c["cp"],
            "lat": c["lat"], "lng": c["lng"], "open": True,
            "url": "https://www.anybuddyapp.com/fr/club/%s/padel" % c["slug"],
        })

    slots = {d.isoformat(): [] for d in days}
    errors = []

    for i, c in enumerate(CLUBS):
        qs = urllib.parse.urlencode({
            "clubSlug": c["slug"], "dateFrom": date_from, "dateTo": date_to, "activity": "padel",
        })
        try:
            payload = fetch_json(API + "?" + qs)
            for block in iter_blocks(payload):
                start = block.get("startDateTime") or block.get("startDatetime") or ""
                m = re.match(r"(\d{4}-\d{2}-\d{2})T(\d{2})", str(start))
                if not m:
                    continue
                day, hour = m.group(1), int(m.group(2))
                if day not in slots:
                    continue
                for svc in block.get("services") or []:
                    dur = svc.get("duration") or 0
                    price = svc.get("price")
                    places = svc.get("availablePlaces")
                    slots[day].append({
                        "s": i, "h": hour,
                        "c": "%d min" % dur if dur else "Padel",
                        "surf": "Padel", "ecl": False, "cov": False,
                        "p": "%d €" % round(price / 100) if isinstance(price, (int, float)) else "",
                        "t": "Padel" + (" · %d places" % places if places else ""),
                    })
        except Exception as e:
            errors.append("%s: %s" % (c["slug"], e))
            print("ERR %s: %s" % (c["slug"], e), file=sys.stderr)
        time.sleep(DELAY)

    total = sum(len(v) for v in slots.values())
    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "days": [d.isoformat() for d in days],
        "sites": sites,
        "slots": slots,
        "total": total,
        "errors": errors,
    }
    with open("padel.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print("OK: %d créneaux, %d erreurs, %.0fs" % (total, len(errors), time.time() - t0), file=sys.stderr)


if __name__ == "__main__":
    main()
