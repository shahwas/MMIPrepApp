# Deploying to Streamlit Community Cloud

1. Push your repository to GitHub.
2. Go to https://share.streamlit.io and sign in with GitHub.
3. Click "New app" → choose your repository and branch, set the main file to `app.py`, then deploy.
4. Add secrets (do NOT upload `.streamlit/secrets.toml`):
   - In the deployed app's Settings → Secrets, add the keys from `.streamlit/secrets.example.toml` (e.g. `auth.client_id`, `auth.client_secret`, `auth.cookie_secret`, `auth.server_metadata_url`).
   - For OpenAI, add `OPENAI_API_KEY` as needed.
5. (Optional) Set a Python runtime by adding `runtime.txt` to the repo (example provided).
6. If you use a database (e.g. Postgres), configure connection strings as secrets and point `DATABASE_URL` to them.

Notes:
- Keep real secrets out of the repository. `.streamlit/secrets.toml` is already listed in `.gitignore`.
- Streamlit Cloud will install packages from `requirements.txt` automatically.
- If you need OS packages, create a `packages.txt` (APT) — currently not required for this app.
