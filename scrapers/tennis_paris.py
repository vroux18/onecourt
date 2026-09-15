#!/usr/bin/env python3
"""Scraper des créneaux tennis disponibles sur tennis.paris.fr (sans login).

Sortie: data.json — tous les créneaux libres, tous terrains Paris, 7 jours.
Stdlib uniquement (urllib), passe par le proxy via variables d'environnement.
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
from http.cookiejar import CookieJar

BASE = "https://tennis.paris.fr/tennis/jsp/site/Portal.jsp"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
COATINGS = ["96", "2095", "94", "1324", "2016", "92"]
CHUNK = 8
DAYS = 8
DELAY = 0.7

jar = CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
opener.addheaders = [("User-Agent", UA), ("Accept-Encoding", "gzip")]


def fetch(url, data=None, retries=3):
    for attempt in range(retries):
        try:
            body = urllib.parse.urlencode(data, doseq=True).encode() if data else None
            with opener.open(url, body, timeout=60) as r:
                raw = r.read()
                if r.headers.get("Content-Encoding") == "gzip" or raw[:2] == b"\x1f\x8b":
                    raw = gzip.GzipFile(fileobj=io.BytesIO(raw)).read()
                return raw.decode("utf-8", "replace")
        except Exception as e:
            if attempt == retries - 1:
                raise
            time.sleep(3 * (attempt + 1))


def get_sites_and_token():
    h = fetch(BASE + "?page=recherche&view=recherche_creneau")
    m = re.search(r'id="token" type="hidden" value="([0-9a-f-]{36})"', h)
    token = m.group(1) if m else None
    gens = re.findall(r'"general":\{(.*?)\},"transports"', h)
    sites, seen = [], set()
    for g in gens:
        def get(k):
            mm = re.search(r'"%s":"([^"]*)"' % k, g)
            if mm:
                return mm.group(1)
            mm = re.search(r'"%s":([0-9.\-]+)' % k, g)
            return mm.group(1) if mm else None
        name = get("_nomSrtm")
        if not name or name in seen:
            continue
        seen.add(name)
        sites.append({
            "name": name,
            "arr": int(get("_arrondissement") or 0),
            "adresse": get("_adresse"),
            "cp": get("_codePostal"),
            "lat": float(get("_gpsLat") or 0),
            "lon": float(get("_gpsLon") or 0),
            "open": get("_ouvRes") == "V",
        })
    return sites, token


def parse_results(html, name_by_key):
    """-> list of (site_name, hour, court, surface, eclaire, price, tarif, couvert)"""
    out = []
    chunks = html.split('id="head')[1:]
    for ch in chunks:
        m = re.match(r'(.*?)(\d{2})h"', ch)
        if not m:
            continue
        key, hour = m.group(1), int(m.group(2))
        site = name_by_key.get(key)
        if not site:
            continue
        # stop at next panel heading to be safe (split already does)
        for row in re.findall(r'<div class="row tennis-court">(.*?)(?=<div class="row tennis-court">|$)', ch, re.S):
            cm = re.search(r'<span class="court">\s*([^<]+?)\s*<', row)
            pm = re.search(r'<span class="price">\s*([^<]*?)\s*</span>', row)
            dm = re.search(r'price-description">([^<]*)<br\s*/?>([^<]*)<', row)
            if not cm:
                continue
            parts = [p.strip() for p in cm.group(1).split(" - ")]
            court = parts[0]
            surface = parts[1] if len(parts) > 1 else ""
            eclaire = any("clair" in p for p in parts)
            price = (pm.group(1).strip() if pm else "")
            tarif = (dm.group(1).strip() if dm else "")
            couvert = (dm.group(2).strip() if dm else "")
            out.append((site, hour, court, surface, eclaire, price, tarif, couvert))
    return out


def main():
    t0 = time.time()
    sites, token = get_sites_and_token()
    open_sites = [s for s in sites if s["open"]]
    print(f"{len(sites)} sites ({len(open_sites)} ouverts à la résa), token={bool(token)}", file=sys.stderr)
    name_by_key = {s["name"].replace(" ", ""): s["name"] for s in sites}
    site_idx = {s["name"]: i for i, s in enumerate(sites)}

    days = [date.today() + timedelta(days=d) for d in range(DAYS)]
    slots = {d.isoformat(): [] for d in days}
    errors = []

    names = [s["name"] for s in open_sites]
    groups = [names[i:i + CHUNK] for i in range(0, len(names), CHUNK)]

    for d in days:
        when = d.strftime("%d/%m/%Y")
        for gi, group in enumerate(groups):
            data = {
                "token": token or "",
                "when": when,
                "hourRange": "8-22",
                "selWhereTennisName": group,
                "selInOut": ["V", "F"],
                "selCoating": COATINGS,
            }
            try:
                html = fetch(BASE + "?page=recherche&action=rechercher_creneau", data)
                for (site, hour, court, surface, ecl, price, tarif, cvt) in parse_results(html, name_by_key):
                    slots[d.isoformat()].append({
                        "s": site_idx[site], "h": hour, "c": court,
                        "surf": surface, "ecl": ecl, "cov": cvt == "Couvert",
                        "p": price, "t": tarif,
                    })
            except Exception as e:
                errors.append(f"{when} grp{gi}: {e}")
                print(f"ERR {when} grp{gi}: {e}", file=sys.stderr)
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
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print(f"OK: {total} créneaux, {len(errors)} erreurs, {time.time()-t0:.0f}s", file=sys.stderr)


if __name__ == "__main__":
    main()
