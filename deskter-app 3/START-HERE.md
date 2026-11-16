# Open Deskter

1. Extract the ZIP.
2. Open the `deskter-app` folder.
3. On Mac, launch `Start-Deskter.command`. On Windows, launch `Start-Deskter.bat`.
4. Keep the terminal window open while using the app. Python 3.12 or newer must already be installed.

The launcher opens the landing page. Choose Create your free account to register, then use the dashboard to publish a service. The server stores records in `deskter.sqlite3`. Do not delete that file or upload it to GitHub.

If the operating system blocks the downloaded launcher, do not disable system-wide security settings. The terminal alternative is `python3 start.py` from this folder. A Codespace cannot open your local browser automatically; open its forwarded port instead.

## Pages

- `/` — landing page
- `/login` — sign in
- `/register` — create account
- `/app` — marketplace/dashboard
- `/plans` — Free, Pro, and Boost information
- `/app?preview=1` — explicitly labeled browser-local demo

Opening `index.html` directly also starts the local demo. It uses separate demo data, not the server database. Real account pages need the server running.

## Existing installation

Stop the old server. Back up its database before updating. Replace source files but keep `deskter.sqlite3` (or your configured database) in its original location. Start the new app; database upgrades run automatically. Do not move the database into the publicly served folder of a general-purpose static server.

## Checks and backups

- `python3 check.py` runs the automated checks (Node.js is also needed for frontend tests).
- `python3 manage.py check` checks database integrity.
- `python3 manage.py backup` creates a consistent SQLite backup in `backups/`.

This is a local development release, not a publicly launched commerce service. No payments are collected. See FEATURE_STATUS.md and RELEASE.md for limits.
