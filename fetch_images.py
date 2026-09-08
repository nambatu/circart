#!/usr/bin/env python3
"""
Download artwork images from Wikimedia Commons.

Usage:
    python3 fetch_images.py artline_resolved.json [--width 1600] [--out images]

Skips files already on disk, so it is safe to interrupt and rerun. Respects
Wikimedia's rate limits: one request at a time, a real User-Agent, and backoff
on 429. About 220 images takes roughly five minutes.
"""

import json, sys, os, time, argparse, urllib.request, urllib.error

UA = "Artline/0.1 (https://example.at/artline; you@example.at) python-urllib"
DELAY = 1.0


def download(url, dest, tries=4):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                data = r.read()
            if len(data) < 2000:
                return False, "suspiciously small"
            with open(dest, "wb") as f:
                f.write(data)
            return True, len(data)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = int(e.headers.get("Retry-After", 0)) or (5 * 2 ** attempt)
                time.sleep(wait)
            elif e.code == 404:
                return False, "404"
            else:
                # Commons' thumbnailer times out on gigapixel scans. Retry smaller.
                if "width=" in url and attempt == 0:
                    url = url.split("?")[0] + "?width=1000"
                    continue
                return False, f"http {e.code}"
        except Exception as e:
            time.sleep(3 * 2 ** attempt)
            if attempt == tries - 1:
                return False, str(e)[:60]
    return False, "gave up"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("json")
    p.add_argument("--width", type=int, default=1600)
    p.add_argument("--out", default="images")
    args = p.parse_args()

    records = json.load(open(args.json, encoding="utf-8"))
    os.makedirs(args.out, exist_ok=True)

    todo = [r for r in records if r.get("image")]
    print(f"{len(todo)} of {len(records)} have an image URL")

    # Restore any existing manual images that may have lost their JSON link
    restored_manual = 0
    for r in records:
        if not r.get("image"):
            dest = os.path.join(args.out, r["id"] + ".jpg")
            if os.path.exists(dest) and os.path.getsize(dest) > 2000:
                mtime = int(os.path.getmtime(dest))
                r["image_local"] = f"{dest}?t={mtime}"
                r["source"] = "manual"
                restored_manual += 1
    if restored_manual:
        print(f"Restored {restored_manual} manual local images.")

    ok = skipped = 0
    failures = []
    for i, r in enumerate(todo, 1):
        dest = os.path.join(args.out, r["id"] + ".jpg")
        if os.path.exists(dest) and os.path.getsize(dest) > 2000:
            mtime = int(os.path.getmtime(dest))
            r["image_local"] = f"{dest}?t={mtime}"
            skipped += 1
            continue

        url = r["image"].split("?")[0] + f"?width={args.width}"
        good, info = download(url, dest)
        if good:
            r["image_local"] = dest
            ok += 1
            print(f"  [{i}/{len(todo)}] {r['id']}  {info//1024} KB")
        else:
            failures.append((r["id"], info))
            print(f"  [{i}/{len(todo)}] FAILED {r['id']}: {info}")
        time.sleep(DELAY)

    json.dump(records, open(args.json, "w", encoding="utf-8"), indent=2, ensure_ascii=False)

    print(f"\ndownloaded {ok}, already present {skipped}, failed {len(failures)}")
    missing = [r["id"] for r in records if not r.get("image_local")]
    if missing:
        with open("report_missing_images.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(missing))
        print(f"{len(missing)} cards still have no image -> report_missing_images.txt")
        print("Expect sculpture, performance and post-1970 work here; "
              "those often need a manual Commons search.")


if __name__ == "__main__":
    main()
