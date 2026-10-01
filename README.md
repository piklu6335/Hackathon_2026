# NewsCred

NewsCred serves its existing website and FastAPI API from one origin. The current analysis inputs are article URLs, uploaded screenshots, image URLs, and the Chrome/Edge extension.

## Run locally

From the repository root, install `backend/requirements.txt` and start the API:

```powershell
python -m pip install -r backend/requirements.txt
python -m uvicorn backend.main:app --reload
```

Open `http://127.0.0.1:8000`. API routes are under `/api`; `/api/health` is the health check. The model checkpoint is expected at `backend/models/c2_new_model_weights.pt`.

## Browser extension

Load the `extension` directory as an unpacked extension in Chrome or Edge. It scans likely article pages once after load, caches by page URL, and supports a manual re-analysis from the popup. Before publishing, set `API_BASE` in `extension/background.js` to the deployed NewsCred origin and add that origin to `host_permissions` in `extension/manifest.json`.

## Render and MySQL

`render.yaml` configures the FastAPI web service. The model stack needs a paid instance with enough memory; validate its peak memory before choosing production capacity. The Blueprint expects DB environment variables to be supplied as secrets/settings. Render MySQL is a separate private service; create it with a persistent disk mounted at `/var/lib/mysql`, then use its internal hostname for `DB_HOST`. Run `backend/database/schema.sql` once to prepare the database.

The schema is ready for account sessions and analysis history, but authentication, database writes, and history endpoints are not yet implemented. Account pages currently remain presentation-only. HTTPS is managed by Render on its public service domains.

## Local translation models

NewsCred translates extracted article/OCR text in the FastAPI backend using the Argos Translate Python module, which is the open-source engine used by LibreTranslate. It does not call a translation API and needs no API key. The backend detects the source language, downloads only the required model pair (or an English pivot pair) on first use, then runs translation locally. Translation requests are capped at 5,000 characters.

Models are stored in Argos's local package directory. Render mounts a 5 GB persistent disk for those model files, so downloaded models survive redeploys. The disk adds about $1.25/month at Render's current $0.25/GB rate; there is no separate translation service or API charge. Argos Translate is open-source and supports local Python translation: https://github.com/argosopentech/argos-translate/.
#
