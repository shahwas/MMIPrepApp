# OIDC Setup (Google / Okta) — Quick Guide

This app uses Streamlit's built-in OpenID Connect (OIDC) support via `st.login()`.
Follow these steps to configure a free provider (Google is easiest for local dev):

1) Install auth extras

```bash
pip install "streamlit[auth]" authlib
```

2) Create `.streamlit/secrets.toml` from `.streamlit/secrets.example.toml` and fill in values.

3) Register an OAuth/OIDC app with your provider:

- Google (free):
  - Go to Google Cloud Console → APIs & Services → Credentials → Create OAuth client ID.
  - Application type: Web application.
  - Add `http://localhost:8501/oauth2callback` as an authorized redirect URI.
  - Copy `client_id` and `client_secret` into `secrets.toml`.

- Okta (free developer account):
  - Create an Okta Developer account, add an OIDC app.
  - Set redirect URI to `http://localhost:8501/oauth2callback`.
  - Copy `client_id`/`client_secret` and `server_metadata_url`.

4) Generate a strong `cookie_secret` (at least 32 random chars) and place it in `secrets.toml`.

5) Run the app

```bash
streamlit run app.py
```

6) In the app, click `Sign in` to be redirected to your provider. After sign-in Streamlit will set an identity cookie and `st.user` will be available.

Notes:
- For production, use HTTPS and set `redirect_uri` to your real public URL + `/oauth2callback`.
- Streamlit handles CSRF/XSRF protections when auth is configured.
