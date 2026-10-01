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
