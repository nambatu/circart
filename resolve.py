#!/usr/bin/env python3
"""
Artline resolver: match curated artworks to Wikidata, verify dates, collect image URLs.

Usage:
    python3 resolve.py artline_masterpieces.json

Outputs:
    artline_resolved.json   enriched records
    report_unmatched.txt    entries needing manual QIDs
    report_dates.txt        year disagreements with Wikidata
    .cache/                 raw SPARQL responses (delete to force refetch)

Strategy: two passes. First resolve the 153 artist names to QIDs, then fetch every
work by each artist in one query and fuzzy-match titles locally. That's ~300 requests
instead of ~10,000, and reruns are free because everything is cached to disk.
"""

import json, sys, time, os, re, unicodedata, hashlib
from difflib import SequenceMatcher
import urllib.parse, urllib.request

# --- Wikimedia asks that you identify yourself. Put a real address here. ---
UA = "Artline/0.1 (https://example.at/artline; you@example.at) python-urllib"

SPARQL = "https://query.wikidata.org/sparql"
CACHE = ".cache"
DELAY = 1.2          # seconds between live requests
MATCH_THRESHOLD = 0.82


def fold(s):
    """Strip diacritics and punctuation so 'Durer' matches 'Albrecht Dürer'."""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().replace("&", "and")
    return re.sub(r"[^a-z0-9 ]+", " ", s).strip()


def sim(a, b):
    return SequenceMatcher(None, fold(a), fold(b)).ratio()


def query(sparql_text):
    """Run a SPARQL query, caching the result by hash of the query."""
    os.makedirs(CACHE, exist_ok=True)
    key = hashlib.sha1(sparql_text.encode()).hexdigest()[:16]
    path = os.path.join(CACHE, key + ".json")
    if os.path.exists(path):
        return json.load(open(path))

    url = SPARQL + "?" + urllib.parse.urlencode({"query": sparql_text, "format": "json"})
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/sparql-results+json"})

    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                data = json.load(r)
            json.dump(data, open(path, "w"))
            time.sleep(DELAY)
            return data
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503):
                wait = int(e.headers.get("Retry-After", 0)) or (5 * 2 ** attempt)
                print(f"    throttled ({e.code}), waiting {wait}s", file=sys.stderr)
                time.sleep(wait)
            else:
                raise
        except Exception as e:
            print(f"    error {e}, retrying", file=sys.stderr)
            time.sleep(5 * 2 ** attempt)
    raise RuntimeError("query failed after retries")


def resolve_artists(names):
    """Map artist display names to QIDs. Batched 40 at a time via VALUES."""
    out = {}
    names = sorted(set(names))
    for i in range(0, len(names), 40):
        chunk = names[i:i + 40]
        vals = " ".join('"%s"@en' % n.replace('"', '') for n in chunk)
        q = """
        SELECT ?name ?a ?aLabel ?sitelinks WHERE {
          VALUES ?name { %s }
          ?a rdfs:label|skos:altLabel ?name .
          ?a wikibase:sitelinks ?sitelinks .
          FILTER EXISTS { ?w wdt:P170 ?a }
          SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
        }""" % vals
        print(f"  artists {i+1}-{i+len(chunk)} of {len(names)}")
        best = {}
        for b in query(q)["results"]["bindings"]:
            n = b["name"]["value"]
            links = int(b["sitelinks"]["value"])
            # More sitelinks = the famous Leonardo, not an obscure namesake.
            if n not in best or links > best[n][1]:
                best[n] = (b["a"]["value"].rsplit("/", 1)[-1], links)
        for n in chunk:
            out[n] = best.get(n, (None, 0))[0]
    return out


def works_by_artist(qid):
    """Every work by one artist, with labels, aliases, dates, images, sitelinks."""
    q = """
    SELECT ?w ?label ?inception ?precision ?img ?sitelinks ?deLabel WHERE {
      ?w wdt:P170 wd:%s .
      ?w wikibase:sitelinks ?sitelinks .
      { ?w rdfs:label ?label } UNION { ?w skos:altLabel ?label }
      FILTER(lang(?label) IN ("en","de","fr","it","nl","es"))
      OPTIONAL {
        ?w p:P571 ?st . ?st psv:P571 ?node .
        ?node wikibase:timeValue ?inception ; wikibase:timePrecision ?precision .
      }
      OPTIONAL { ?w wdt:P18 ?img }
      OPTIONAL { ?w rdfs:label ?deLabel FILTER(lang(?deLabel)="de") }
    }""" % qid
    rows = {}
    for b in query(q)["results"]["bindings"]:
        w = b["w"]["value"].rsplit("/", 1)[-1]
        r = rows.setdefault(w, {"qid": w, "labels": set(), "de": None,
                                "year": None, "precision": None,
                                "img": None, "sitelinks": 0})
        r["labels"].add(b["label"]["value"])
        r["sitelinks"] = int(b["sitelinks"]["value"])
        if "deLabel" in b:
            r["de"] = b["deLabel"]["value"]
        if "inception" in b and r["year"] is None:
            m = re.match(r"([+-]?\d+)-", b["inception"]["value"])
            if m:
                r["year"] = int(m.group(1))
            r["precision"] = int(b["precision"]["value"]) if "precision" in b else None
        if "img" in b and not r["img"]:
            r["img"] = urllib.parse.unquote(b["img"]["value"])
    return list(rows.values())


def main(path):
    records = json.load(open(path))
    print(f"loaded {len(records)} records")

    print("pass 1: resolving artists")
    artist_qid = resolve_artists([r["artist"] for r in records])
    missing = [n for n, q in artist_qid.items() if not q]
    print(f"  resolved {len(artist_qid)-len(missing)}/{len(artist_qid)}")

    print("pass 2: matching works")
    cache_works, unmatched, date_issues = {}, [], []

    for i, rec in enumerate(records, 1):
        aq = artist_qid.get(rec["artist"])
        if not aq:
            unmatched.append((rec["id"], "artist not resolved"))
            continue
        if aq not in cache_works:
            print(f"  [{i}/{len(records)}] fetching works for {rec['artist']}")
            cache_works[aq] = works_by_artist(aq)

        best, score = None, 0.0
        for w in cache_works[aq]:
            s = max(sim(rec["title"], lab) for lab in w["labels"])
            # Nudge toward the work whose date already agrees with ours.
            if w["year"] is not None and abs(w["year"] - rec["year"]) <= 3:
                s += 0.06
            if s > score:
                best, score = w, s

        if not best or score < MATCH_THRESHOLD:
            unmatched.append((rec["id"], f"best score {score:.2f}"))
            continue

        rec["wikidata_qid"] = best["qid"]
        rec["title_de"] = best["de"]
        rec["sitelinks"] = best["sitelinks"]
        rec["match_score"] = round(score, 3)
        rec["source"] = "wikidata"

        if best["img"]:
            fn = best["img"].rsplit("/", 1)[-1]
            rec["commons_file"] = fn
            rec["image"] = ("https://commons.wikimedia.org/wiki/Special:FilePath/"
                            + urllib.parse.quote(fn) + "?width=1600")

        if best["year"] is not None:
            rec["wikidata_year"] = best["year"]
            # precision 9 = year, 8 = decade, 7 = century
            rec["wikidata_precision"] = best["precision"]
            if abs(best["year"] - rec["year"]) > 3:
                date_issues.append((rec["id"], rec["year"], best["year"],
                                    best["precision"], rec["title"]))

    try:
        if os.path.exists("artline.json"):
            existing = json.load(open("artline.json", "r", encoding="utf-8"))
            existing_map = {r["id"]: r for r in existing}
            for rec in records:
                if rec["id"] in existing_map:
                    ex = existing_map[rec["id"]]
                    if ex.get("source") == "manual":
                        rec["image_local"] = ex.get("image_local")
                        rec["source"] = "manual"
                        if "image" in ex:
                            rec["image"] = ex["image"]
    except Exception as e:
        print("Could not load existing resolved data to preserve manual overrides:", e)

    json.dump(records, open("artline.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)

    with open("report_unmatched.txt", "w", encoding="utf-8") as f:
        f.write(f"{len(unmatched)} unmatched of {len(records)}\n\n")
        for rid, why in unmatched:
            f.write(f"{rid}\t{why}\n")

    with open("report_dates.txt", "w", encoding="utf-8") as f:
        f.write("id\tmine\twikidata\tprecision\ttitle\n")
        for row in sorted(date_issues, key=lambda x: -abs(x[1] - x[2])):
            f.write("\t".join(str(x) for x in row) + "\n")

    resolved = sum(1 for r in records if r.get("wikidata_qid"))
    with_img = sum(1 for r in records if r.get("image"))
    print(f"\nresolved {resolved}/{len(records)}   images {with_img}   "
          f"unmatched {len(unmatched)}   date flags {len(date_issues)}")
    print("check report_unmatched.txt and report_dates.txt before downloading")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "artline.json")
