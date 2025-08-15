# Configuration for Haven Pro
ENABLE_GOOGLE = False   # set True after filling credentials
LOCAL_ONLY = True       # avoid external calls by default
RETENTION_DAYS = 180

# Web Push (VAPID) placeholders — generate your own for production
VAPID_PRIVATE_KEY = "REPLACE_WITH_BASE64URL_PRIVATE_KEY"
VAPID_PUBLIC_KEY = "REPLACE_WITH_BASE64URL_PUBLIC_KEY"
VAPID_CLAIMS = {"sub": "mailto:owner@example.com"}

# OIDC / SSO placeholders (Employer edition)
OIDC_CLIENT_ID = "REPLACE_ME"
OIDC_CLIENT_SECRET = "REPLACE_ME"
OIDC_ISSUER = "https://example-issuer"  # e.g., https://your-tenant.auth0.com
REDIRECT_URI = "http://127.0.0.1:8000/integrations/google/callback"  # update for your domain
