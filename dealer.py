#!/usr/bin/env python3
"""
CIRCArt dealer: builds a game's worth of cards from the deck.

    python3 dealer.py circart_cards.json --players 4 --target 10

Writes game_<seed>.json with the starting cards and the draw pile, and appends
the ids used to seen.json so later games avoid repeats.
"""

import json, random, argparse, collections, os, time

# Rough recall rates used only to order the tier schedule, not to score anything.
TIER_ORDER = ["obscure", "recognisable", "icon"]


def load(path, seen_path=None, fresh_only=False):
    cards = json.load(open(path, encoding="utf-8"))
    cards = [c for c in cards if c.get("image_local")]      # unplayable without art
    if fresh_only and seen_path and os.path.exists(seen_path):
        seen = set(json.load(open(seen_path, encoding="utf-8")))
        fresh = [c for c in cards if c["id"] not in seen]
        # Fall back to the full deck once fewer than a third remain unseen.
        if len(fresh) > len(cards) // 3:
            cards = fresh
    return cards


def starting_cards(cards, n, rng):
    """One card per player, spread across eras so nobody starts with an advantage.

    A player whose first card is 1888 sits inside the deck's densest region and
    every later card lands near it; a player starting at 1450 has open space on
    both sides. Spreading the starts evens that out.
    """
    bands = [(1300, 1600), (1600, 1800), (1800, 1900), (1900, 1960), (1960, 2030)]
    pool = collections.defaultdict(list)
    for c in cards:
        for lo, hi in bands:
            if lo <= c["year"] < hi and c["tier"] <= 2:     # start on something knowable
                pool[(lo, hi)].append(c)
    picked, used_bands = [], []
    order = bands[:]
    rng.shuffle(order)
    for i in range(n):
        band = order[i % len(order)]
        candidates = [c for c in pool[band] if c not in picked]
        if not candidates:
            candidates = [c for c in cards if c not in picked]
        picked.append(rng.choice(candidates))
        used_bands.append(band)
    return picked


def tier_for_round(k, total):
    """Weights that start obscure-heavy and end icon-heavy.

    A short timeline has few slots, so a hard card is still a fair guess.
    A long timeline has many slots, so only a card you actually recognise
    gives you better than random odds. Serving them in that order keeps the
    success rate roughly flat instead of grinding down to chance.
    """
    t = (k - 1) / max(total - 1, 1)
    return {"obscure": 0.45 - 0.45 * t,
            "recognisable": 0.45,
            "icon": 0.10 + 0.45 * t}


def build_pile(cards, size, rng, exclude, artist_gap=8, decade_gap=4):
    by_tier = collections.defaultdict(list)
    for c in cards:
        if c["id"] not in exclude:
            by_tier[c["tier_label"]].append(c)
    for v in by_tier.values():
        rng.shuffle(v)

    pile, recent_artists, recent_decades = [], [], []
    for i in range(size):
        w = tier_for_round(i + 1, size)
        tiers = sorted(TIER_ORDER, key=lambda t: -w[t] * rng.random())
        chosen = None
        for t in tiers:
            for c in by_tier[t]:
                if c["artist"] in recent_artists:      # no two Bruegels in a row
                    continue
                if c["year"] // 10 in recent_decades:  # spread the eras out
                    continue
                chosen = c
                break
            if chosen:
                by_tier[t].remove(chosen)
                break
        if chosen is None:                              # constraints too tight, relax
            flat = [c for t in TIER_ORDER for c in by_tier[t]]
            if not flat:
                break
            chosen = rng.choice(flat)
            by_tier[chosen["tier_label"]].remove(chosen)
        pile.append(chosen)
        recent_artists = (recent_artists + [chosen["artist"]])[-artist_gap:]
        recent_decades = (recent_decades + [chosen["year"] // 10])[-decade_gap:]
    return pile


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("deck")
    ap.add_argument("--players", type=int, default=4)
    ap.add_argument("--target", type=int, default=10, help="cards needed to win")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--seen", default="seen.json")
    ap.add_argument("--fresh", action="store_true", help="prefer unseen cards")
    a = ap.parse_args()

    seed = a.seed if a.seed is not None else int(time.time())
    rng = random.Random(seed)
    cards = load(a.deck, a.seen, a.fresh)

    starts = starting_cards(cards, a.players, rng)
    # Players fail roughly half their attempts, so budget about two draws per
    # card they need, plus a margin.
    size = min(int(a.players * a.target * 2.2), len(cards) - a.players)
    pile = build_pile(cards, size, rng, {c["id"] for c in starts})

    game = {"seed": seed, "players": a.players, "target": a.target,
            "starting_cards": starts, "draw_pile": pile}
    out = f"game_{seed}.json"
    json.dump(game, open(out, "w", encoding="utf-8"), indent=2, ensure_ascii=False)

    used = [c["id"] for c in starts + pile]
    prev = json.load(open(a.seen, encoding="utf-8")) if os.path.exists(a.seen) else []
    json.dump(sorted(set(prev) | set(used)), open(a.seen, "w", encoding="utf-8"), indent=2)

    print(f"seed {seed}  ->  {out}")
    print(f"deck {len(cards)} playable | starts {len(starts)} | pile {len(pile)}")
    print("\nstarting cards:")
    for c in starts:
        print(f"  {c['year']}  T{c['tier']}  {c['artist'][:22]:24s} {c['title'][:34]}")
    print("\ntier mix across the pile, in thirds:")
    third = max(len(pile) // 3, 1)
    for name, seg in [("early", pile[:third]), ("middle", pile[third:2*third]),
                      ("late", pile[2*third:])]:
        c = collections.Counter(x["tier_label"] for x in seg)
        n = max(len(seg), 1)
        print(f"  {name:7s} icon {c['icon']*100//n:3d}%  "
              f"recognisable {c['recognisable']*100//n:3d}%  obscure {c['obscure']*100//n:3d}%")


if __name__ == "__main__":
    main()