# Prepare now. Read offline later.

The public website is a way to distribute MARS CACHE while the internet works. The post-outage version is the copy stored on your own devices.

1. Download the [public offline core](https://github.com/rustyorb/mars-cache/releases/download/v0.1.0/MARS-CACHE-Public-Offline-Core-v0.1.0.zip) and unzip the entire archive.
2. The 32 hosted references work locally immediately: open `index.html`.
3. **While still online**, run `Prepare-Personal-Cache.cmd` on Windows. Python 3 must be installed. On macOS/Linux, run `python3 tools/prepare_personal.py` in the unzipped folder.
4. The tool reuses the core PDFs, then obtains the remaining references and health chapters directly from their publishers. It creates an isolated tool environment and stores your personal library in your home folder as `MARS-CACHE-Personal`.
5. Open `OFFLINE-READINESS.html` in that personal folder. It reports the actual number saved out of the 143 planned reference/chapter files and lists any unavailable downloads. Missing files mean preparation is incomplete.
6. Disconnect Wi-Fi and mobile data, open the personal library, and practice finding maps and instructions. Copy the complete personal folder to a backup drive. For the Pi stage, the same content will be served locally over the Pi's Wi-Fi.

The preparation step needs internet access. A website bookmark or publisher link is not an offline copy. The browser catalog searches titles, subjects and publisher notes, not the full text of every PDF.

Publisher resources remain subject to their original terms. In particular, the health chapters are obtained directly for your personal use, rather than redistributed in the public ZIP. Preserve their copyright pages and attribution.

Run preparation again while online to retry failed downloads. Existing validated files are reused. The tool reports source failures; it does not quietly substitute unknown mirrors or claim an incomplete collection is complete.
