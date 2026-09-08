# CIRCArt

A browser game about art history. You are dealt a masterpiece and have to place
it in the correct spot on a chronological timeline, with bonus points for
guessing the artist, the title or the exact year. After each round the card
opens up with the movement, medium, where the work hangs today, and a short
piece of writing about what makes it worth knowing.

**Play it: [j.langschwerts.de/circart](https://j.langschwerts.de/circart)**

## How it is built

Plain HTML, CSS and JavaScript, no framework and no build step, so it loads
fast and runs offline once cached. A [Capacitor](https://capacitorjs.com/)
wrapper builds the same code into Android and iOS apps.

```
www/            source (full-resolution images, not committed)
www-mobile/     source for the Capacitor mobile build
docs/           web build published by GitHub Pages
android/ ios/   Capacitor native projects
```

## The card pipeline

The card set in `artline.json` is assembled by a set of Python scripts that
pull metadata and open-access images from museum APIs — the Metropolitan
Museum of Art, the Cleveland Museum of Art and Europeana — and resolve them
against Wikidata.

| Script | What it does |
| --- | --- |
| `fetch_images.py` | Downloads artwork images |
| `resolve.py` | Resolves works against Wikidata |
| `patch_cards.py` | Fills in and corrects card metadata |
| `dealer.py` | Assembles a playable set |
| `verify_server.py` + `verify.html` | Local review UI for checking cards by hand |
| `run_pipeline.bat` | Runs the above in order |

## Building the web version

```
pip install pillow
python build_deploy.py
```

This resizes the artwork to 1600px web JPEGs and writes a complete, publishable
copy into `docs/` — roughly a 67% size reduction, with no visible quality loss.
GitHub Pages serves that folder, so committing it updates the live game.

## Image rights

Every card credits its artist, title, year and holding collection. The images
are reproductions of artworks used here for a non-commercial educational game.
If you hold rights in a work shown in CIRCArt and would like it removed or
credited differently, please get in touch at julian@langschwerts.de and it will
be dealt with promptly.

## Author

Julian Langschwert — [j.langschwerts.de](https://j.langschwerts.de)
