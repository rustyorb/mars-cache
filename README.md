# MARS CACHE

**Mobile Archive for Resilience & Survival**

A survival, repair and rebuilding reference library for the Mars brothers, focused on Kentuckiana.

**[Open the field library](https://rustyorb.github.io/mars-cache/)** · **[Download the offline core](https://github.com/rustyorb/mars-cache/releases/download/v0.1.0/MARS-CACHE-Public-Offline-Core-v0.1.0.zip)**

Two brothers. One cache. Knowledge worth keeping.

## What's here

- **32 hosted references:** nuclear/radiation preparedness, water, food preservation, local topographic maps, communications and practical tools.
- **23 publisher resources:** regional university and state publications, health books and additional technical references. These links require internet access until you obtain your own copies.
- A browser catalog with title, subject and publisher filtering, source attribution, edition information and original-document links.
- An offline ZIP: unzip the whole archive, then open `index.html`.
- A personal preparation tool: while online, obtain the remaining publisher files directly, then check the offline-readiness report. See [Prepare your cache](PREPARE-YOUR-CACHE.md).

The hosted references include eight USGS topo sheets around Louisville and southern Indiana, the USDA home canning introduction and seven guides, CDC radiation infographics, and FEMA planning references. The topo collection is a regional starter, not complete Kentuckiana coverage.

The public website is the distribution point. The survival copy is the complete set of files stored on your own devices. Publisher links are missing offline content until preparation downloads them. The personal tool plans 143 reference/chapter files and reports any failed downloads.

## Hosting

GitHub Pages publishes the `site/` directory on pushes to `main`. The repository includes the generated static site so deployment needs no private collection, credentials, paid hosting or application server. The large offline ZIP is distributed as a release asset rather than committed to Git.

To check the site locally:

```sh
python tools/verify.py
python -m http.server 8080 --directory site
```

To regenerate from a compatible local MARS CACHE collection, install `tools/requirements.txt`, then run:

```sh
python tools/build.py --collection /path/to/MARS-CACHE
```

The build exports selected source metadata, hosted federal references and publisher links. It does not export personal source snapshots, vendor packages, collection logs, household records or local-machine paths.

## Sources, scope and attribution

Collected November 4, 2026. Source publication dates vary, and some material is historical. Original PDFs remain unchanged. Readable HTML copies retain source text and available illustrations while removing navigation and active website content. The library has not undergone independent medical or engineering review. Static maps and reference material provide no live road, weather or fallout conditions.

Source: CDC, HHS, FEMA, USDA, USGS, EPA and National Weather Service, as credited per entry. CDC/HHS materials are also available free on agency websites. This independent project and its references do not imply endorsement by CDC, HHS, any other agency or publisher, or the United States Government.

Hesperian chapter PDFs are linked to their publisher and are not redistributed here. See [Hesperian's digital distribution policy](https://hesperian.org/open-copyright-policy/). Regional university and state references are also linked to their original publishers.

## Reference rights

Third-party reference documents, illustrations and data retain their original rights and terms. Publishing this collection does not relicense those works. See [NOTICE.md](NOTICE.md).
