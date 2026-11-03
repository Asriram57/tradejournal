# Trade Pulse Pro

A free, private trading journal (binary, forex, stocks). One static page, no server. Your data stays in your browser and can sync to **your own** cloud storage.

## 1. Put it on GitHub Pages
1. Create a repo and upload `index.html`, `config.js`, `.nojekyll`, `README.md`.
2. Settings, Pages, Deploy from branch, `main` / root.
3. Your app URL is `https://USERNAME.github.io/REPO/`. Always open the app from this exact URL (trailing slash included). Every OAuth redirect URI below must match it exactly.

If you only have your old single file: save it as `index.html` in this folder and run `python3 apply_all.py`. It applies both sync upgrades and keeps `.bak` copies.

## 2. Pick a sync provider (Settings, Cloud Sync)
Each person pastes their own key, so nothing is shared and no secrets are stored. Keys can also be set once in `config.js`.

| Provider | Key needed | Setup |
|---|---|---|
| Google Drive | OAuth Client ID | Google Cloud Console: enable **Drive API**, create an OAuth client (Web), add `https://USERNAME.github.io` under **Authorized JavaScript origins**. Set the consent screen to **In production** (in Testing mode tokens expire after 7 days). Scope used: `drive.file` (app sees only its own file). |
| Dropbox | App key | Dropbox App Console: Scoped access, **App folder**, enable `files.content.read` and `files.content.write`, add the app URL as **Redirect URI**. Sign-in auto-refreshes. |
| OneDrive | Client ID | Azure, App registrations: personal + work accounts, platform **Single-page application**, redirect URI = app URL. Uses `Files.ReadWrite.AppFolder`. |
| GitHub Gist | Personal access token | Token with only the `gist` scope. Stored as a secret gist. |
| Local file / synced folder | none | Desktop Chrome/Edge: pick `trade-pulse-pro-data.json` inside a folder that **TeraBox, pCloud, MEGA, iCloud, OneDrive** etc. already syncs. |

### TeraBox
TeraBox has no public browser API (no CORS, no OAuth for web apps), so direct sync is not possible. Use the **Local file** option with the TeraBox desktop sync folder, or on phones use Settings, Backup & Data, **JSON export**, then upload the file to TeraBox and use Import to restore.

## Notes
- First connect on a device that already has data offers **merge** (nothing lost) or overwrite.
- Browser data (localStorage) is cleared if you wipe site data. Connect a provider or export JSON regularly.
- Client IDs and app keys are public by design; never put client secrets in this repo.

## One-click Google sign-in (no keys for your users)
The site owner registers **one** Google OAuth Client ID once (put it in `config.js`). After that, every visitor just clicks **Sign in with Google** in the header, picks their account, and their data is saved in **their own** Drive in a `Trade Pulse Pro` folder: the data file plus each chart screenshot as a separate image file. Key boxes are hidden whenever `config.js` has a key. The `drive.file` scope is non-sensitive, so no Google app verification is needed; just publish the consent screen.
Run `python3 patch_google_first.py` after `patch_sync.py` to enable this.
