import os
from fastapi import Header, HTTPException


def verify_admin_key(x_admin_key: str = Header(None)):
    """
    Stopgap auth for the admin REST API. Requires the X-Admin-Key header to
    match ADMIN_API_KEY from the environment.

    This is NOT a replacement for spec section 21 (Telegram-ID-based admin
    auth) — it's the minimum needed to take the admin API off the open
    internet immediately. Every admin-only route (and only admin-only
    routes — not the public/bot-facing ones in the same files) must depend
    on this.
    """
    expected = os.getenv("ADMIN_API_KEY")
    if not expected:
        # Fail closed: if the key isn't configured, refuse rather than
        # silently allow (which is exactly the bug we're fixing).
        raise HTTPException(status_code=500, detail="Admin auth not configured")
    if not x_admin_key or x_admin_key != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return x_admin_key
