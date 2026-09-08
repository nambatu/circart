#!/usr/bin/env python3
"""
Apply corrections to circart_cards.json in place, preserving image and image_local.

Usage:
    python3 patch_cards.py artline.json

Writes a .bak copy first. Idempotent - safe to run twice.
"""

import json, sys, shutil, collections, re, time

PATH = sys.argv[1] if len(sys.argv) > 1 else "artline.json"
BAK = f"{PATH}.{time.strftime('%Y%m%d-%H%M%S')}.bak"
shutil.copy(PATH, BAK)
recs = json.load(open(PATH, encoding="utf-8"))
print(f"loaded {len(recs)}")

# ---------- 1. remove Rhythm 0 ----------
before = len(recs)
recs = [r for r in recs if r.get("id") != "1974-marina-abramovic-rhythm-0"]
if len(recs) < before:
    print("removed Rhythm 0")

# ---------- 2. corrected trivia ----------
FIXES = {
"1962-andy-warhol-marilyn-diptych": (
 "Monroe died on 4 August 1962, in the same month Warhol first started experimenting with "
 "screenprinting, and over the following four months he made more than twenty paintings of her, every "
 "one built from a single cropped publicity still that Gene Kornman had shot for the 1953 film Niagara. "
 "The famous part is the left half in saturated colour against the right half fading into smeared black "
 "and white, universally read as celebrity against mortality. What is less often mentioned is that these "
 "were two separate paintings. The collectors Burton and Emily Tremaine came to the studio, were shown "
 "the black Marilyns first and the coloured one several pictures later, and Emily suggested hanging them "
 "as a diptych; Warhol's recorded response was gee whiz yes. So the most quoted interpretation in "
 "twentieth-century American painting rests on an arrangement the buyer thought of."),
"1434-jan-van-eyck-the-arnolfini-portrait": (
 "High on the back wall, in gold, in the elaborate notarial script used for legal documents, Van Eyck "
 "wrote Johannes de eyck fuit hic 1434, which translates as Jan van Eyck was here. It is toilet-wall "
 "graffiti executed in the handwriting of a contract, on one of the most technically accomplished "
 "paintings in Europe, and it is positioned directly above a convex mirror barely five centimetres across "
 "in which he painted the entire room from behind, two extra figures standing in the doorway roughly "
 "where you are, and ten separate scenes of the Passion around the frame. Two corrections while you are "
 "looking: the woman is not pregnant, she is holding up an expensive amount of cloth in the fashion of "
 "the day, and the theory that the picture records a wedding is now widely doubted. What it records may "
 "simply be that he was there."),
}
NOTES = {
 "1962-andy-warhol-marilyn-diptych":
   "card image must show BOTH panels - left colour, right black and white",
}
for r in recs:
    if r["id"] in FIXES:
        r["trivia"] = FIXES[r["id"]]
        print("patched trivia:", r["id"])
    if r["id"] in NOTES and not r.get("date_note"):
        r["date_note"] = NOTES[r["id"]]

# ---------- 2b. Tres Riches Heures: name one folio, and drop the wrong image ----------
# The manuscript runs to 200+ leaves, so the title identified no single image, and the
# Wikidata pick was Folio 108r (Hell) - painted by Jean Colombe from 1485, not by the
# Limbourgs at all. February is securely theirs and is the page people know.
for r in recs:
    if "limbourg" in r["id"] and not r["id"].endswith("february"):
        r["id"] = "1416-limbourg-brothers-tres-riches-heures-february"
        r["title"] = "Très Riches Heures: February"
        r["date_note"] = "calendar pages painted c. 1412-16; the manuscript was left "\
                         "unfinished and later folios, including Hell, are by Jean Colombe from 1485"
        r["image"] = None
        r["image_local"] = None
        r["image_note"] = ("Previous image was Folio 108r (Hell), which is by Jean Colombe, "
                           "not the Limbourgs. Fetch the February calendar page (folio 2v) "
                           "from Wikimedia Commons category 'Tres Riches Heures du duc de Berry'.")
        r["trivia"] = (
          "The earliest known snow scene in Western art, and the Limbourgs had to invent most of it: "
          "a February page in a book of hours conventionally showed somebody warming by a fire or "
          "chopping twigs in a bare landscape, and they gave almost the whole page to what is happening "
          "outside instead, with a woodcutter, a donkey on the road, a dovecote, sheep, and beehives "
          "under snow. Inside the open-fronted farmhouse, two peasants have hitched their tunics up to "
          "warm their legs and are exposing themselves entirely, while the woman beside them decorously "
          "warms only her ankles. The blue is ground lapis lazuli, more expensive by weight than gold. "
          "All three brothers died in 1416, probably of plague, in the same year as their patron, none "
          "of them yet thirty, and the manuscript sat unfinished for seventy years until Jean Colombe "
          "was hired to complete it.")
        print("patched Tres Riches Heures -> February, image cleared")

# ---------- 3. flag the wrong Comedian image ----------
for r in recs:
    if r["id"] == "2019-maurizio-cattelan-comedian":
        if r.get("image") and "fridge" in r["image"].lower():
            r["image"] = None
            r["image_local"] = None
            r["image_note"] = ("WRONG IMAGE REMOVED: the Commons file was a banana taped to a "
                               "fridge, not Cattelan's work. No free image of Comedian exists; "
                               "use the typographic card treatment.")
            print("cleared wrong Comedian image")

# ---------- 4. normalise key order ----------
ORDER = ["id","title","artist","year","date_note","movement","medium","location",
         "tier","tier_label","explicit","visual_type","personal_copy","trivia",
         "image","image_local","wikidata_qid","source","image_note"]
normalised = []
for r in recs:
    row = {k: r[k] for k in ORDER if k in r}
    for k in r:                       # keep anything unexpected
        if k not in row: row[k] = r[k]
    row.setdefault("visual_type", "object")
    row.setdefault("personal_copy", None)
    row.setdefault("image_local", None)
    normalised.append(row)
recs = sorted(normalised, key=lambda x: (x["year"], x["artist"]))

# ---------- 5. validate ----------
errs = []
SHORT = {"Vincent van Gogh","Georges Seurat","Egon Schiele","Jean-Michel Basquiat",
         "Masaccio","Amedeo Modigliani","Umberto Boccioni","Keith Haring"}
for k,v in collections.Counter(r["artist"] for r in recs).items():
    if v > 4: errs.append(f"artist cap {k}={v}")
for (a,d),v in collections.Counter((r["artist"], r["year"]//10*10) for r in recs).items():
    if v > 2 and a not in SHORT: errs.append(f"artist/decade {a} {d}s={v}")
for k,v in collections.Counter(r["year"] for r in recs).items():
    if v > 3: errs.append(f"year cap {k}={v}")
for k,v in collections.Counter(r["year"]//10*10 for r in recs).items():
    if v > 13: errs.append(f"decade cap {k}s={v}")
for k,v in collections.Counter(r["id"] for r in recs).items():
    if v > 1: errs.append(f"duplicate id {k}")
for r in recs:
    if r["tier_label"] != {1:"icon",2:"recognisable",3:"obscure"}[r["tier"]]:
        errs.append(f"tier mismatch {r['id']}")

json.dump(recs, open(PATH,"w",encoding="utf-8"), indent=2, ensure_ascii=False)

# ---------- 6. report ----------
print(f"\nwrote {len(recs)} cards  (backup at {BAK})")
print("violations:", errs or "none")

no_img = [r["id"] for r in recs if not r.get("image_local")]
print(f"\nno local image: {len(no_img)}")
for i in no_img: print("   ", i)

FRAGILE = ("gstatic.com","oceansbridge","cbc.ca","goldmarkart","wikiart","encrypted-tbn")
frag = [(r["id"], re.sub(r"^https?://([^/]+).*", r"\1", r["image"] or ""))
        for r in recs if r.get("image") and any(f in r["image"] for f in FRAGILE)]
print(f"\nnon-Commons image sources ({len(frag)}) - fine once downloaded, but do not hotlink:")
for i,d in frag: print(f"    {d:24s} {i}")

print("\nby visual_type:", dict(collections.Counter(r["visual_type"] for r in recs)))