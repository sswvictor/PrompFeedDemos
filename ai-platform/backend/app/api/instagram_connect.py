from __future__ import annotations

import html
import json
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import get_current_user_id
from app.db.session import get_db
from app.services.instagram_connect_service import (
    InstagramConnectError,
    InstagramConnectService,
)


router = APIRouter(prefix="/instagram/connect", tags=["instagram-connect"])


class ConnectStartIn(BaseModel):
    return_to: str | None = None


class ConnectStartOut(BaseModel):
    auth_url: str
    state: str
    expires_in_seconds: int


class ConnectStatusOut(BaseModel):
    connected: bool
    instagram_user_id: str | None = None
    instagram_username: str | None = None
    profile_picture_url: str | None = None
    followers_count: int | None = None
    following_count: int | None = None


class DisconnectOut(BaseModel):
    disconnected_pages: int


def _is_mobile_return_target(target_uri: str | None) -> bool:
    if not target_uri:
        return False
    parsed = urlsplit(target_uri)
    return parsed.scheme == "fixmeapp"


def _mobile_redirect_response(
    *,
    ok: bool,
    payload: dict | None = None,
    error: str | None = None,
    target_uri: str,
) -> RedirectResponse:
    parsed = urlsplit(target_uri)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["source"] = "fixmeapp-instagram-connect"
    query["ok"] = "1" if ok else "0"

    if ok and payload:
        for key in (
            "instagram_user_id",
            "instagram_username",
            "profile_picture_url",
            "followers_count",
            "following_count",
            "media_count",
            "page_mapping_id",
        ):
            value = payload.get(key)
            if value is not None:
                query[key] = str(value)

    if error:
        query["error"] = error

    redirect_url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment))
    return RedirectResponse(url=redirect_url, status_code=302)


def _popup_response(*, ok: bool, payload: dict | None = None, error: str | None = None, target_origin: str | None = None) -> HTMLResponse:
    event_payload = {
        "source": "fixmeapp-instagram-connect",
        "ok": ok,
        "payload": payload or {},
        "error": error,
    }
    event_json = json.dumps(event_payload, ensure_ascii=True)

    safe_origin = "*"
    if target_origin and target_origin.startswith(("http://", "https://")):
        parsed = urlsplit(target_origin)
        if parsed.scheme and parsed.netloc:
            safe_origin = f"{parsed.scheme}://{parsed.netloc}"

    body = f"""
<!doctype html>
<html>
  <head>
    <meta charset=\"utf-8\" />
    <title>Instagram connect</title>
    <style>
      body {{ font-family: Inter, system-ui, -apple-system, sans-serif; background:#0b0b0b; color:#f5f5f0; display:flex; align-items:center; justify-content:center; min-height:100vh; margin:0; }}
      .box {{ border:1px solid #2a2a2a; background:#141414; border-radius:16px; padding:20px; max-width:420px; text-align:center; }}
      p {{ margin:8px 0; color:#b5b5ad; }}
    </style>
  </head>
  <body>
    <div class=\"box\">
      <h3>{'Connected' if ok else 'Connection failed'}</h3>
      <p>{html.escape(error or 'You can return to onboarding now.')}</p>
      <p>This window will close automatically.</p>
    </div>
    <script>
      (function() {{
        var payload = {event_json};
        try {{
          if (window.opener && !window.opener.closed) {{
            window.opener.postMessage(payload, {json.dumps(safe_origin)});
          }}
        }} catch (e) {{}}
        setTimeout(function() {{ window.close(); }}, 350);
      }})();
    </script>
  </body>
</html>
"""
    return HTMLResponse(content=body)


@router.post("/start", response_model=ConnectStartOut)
def start_connect(
    body: ConnectStartIn,
    user_id: str = Depends(get_current_user_id),
):
    try:
        state = InstagramConnectService.build_signed_state(
            user_id=user_id,
            return_to=body.return_to,
        )
        url = InstagramConnectService.build_auth_url(state=state)
    except InstagramConnectError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    return ConnectStartOut(
        auth_url=url,
        state=state,
        expires_in_seconds=15 * 60,
    )


@router.get("/callback")
def connect_callback(
    code: str | None = Query(None),
    state: str | None = Query(None),
    error: str | None = Query(None),
    error_description: str | None = Query(None),
    db: Session = Depends(get_db),
):
    target_origin = None
    if state:
        try:
            state_payload = InstagramConnectService.verify_signed_state(state)
            target_origin = state_payload.get("return_to") or None
        except InstagramConnectError:
            state_payload = None
    else:
        state_payload = None

    if error:
        msg = error_description or error
        if _is_mobile_return_target(target_origin):
            return _mobile_redirect_response(
                ok=False,
                error=f"Instagram denied access: {msg}",
                target_uri=target_origin,
            )
        return _popup_response(ok=False, error=f"Instagram denied access: {msg}", target_origin=target_origin)

    if not code or not state_payload:
        if _is_mobile_return_target(target_origin):
            return _mobile_redirect_response(
                ok=False,
                error="Missing OAuth code/state",
                target_uri=target_origin,
            )
        return _popup_response(ok=False, error="Missing OAuth code/state", target_origin=target_origin)

    try:
        oauth_payload, _expires_in = InstagramConnectService.exchange_code_and_fetch_payload(code)
        page = InstagramConnectService.upsert_provider_connection(
            db,
            user_id=state_payload["user_id"],
            payload=oauth_payload,
        )
        payload = {
            "instagram_user_id": oauth_payload.ig_user_id,
            "instagram_username": oauth_payload.username,
            "profile_picture_url": oauth_payload.profile_picture_url,
            "followers_count": oauth_payload.followers_count,
            "following_count": oauth_payload.follows_count,
            "media_count": oauth_payload.media_count,
            "page_mapping_id": page.id,
        }
        if _is_mobile_return_target(target_origin):
            return _mobile_redirect_response(
                ok=True,
                payload=payload,
                target_uri=target_origin,
            )
        return _popup_response(ok=True, payload=payload, target_origin=target_origin)
    except InstagramConnectError as exc:
        if _is_mobile_return_target(target_origin):
            return _mobile_redirect_response(
                ok=False,
                error=str(exc),
                target_uri=target_origin,
            )
        return _popup_response(ok=False, error=str(exc), target_origin=target_origin)
    except Exception:
        if _is_mobile_return_target(target_origin):
            return _mobile_redirect_response(
                ok=False,
                error="Unexpected error while connecting Instagram",
                target_uri=target_origin,
            )
        return _popup_response(ok=False, error="Unexpected error while connecting Instagram", target_origin=target_origin)


@router.get("/status", response_model=ConnectStatusOut)
def connect_status(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    data = InstagramConnectService.get_connection_status(db, user_id=user_id)
    return ConnectStatusOut(**data)


@router.post("/disconnect", response_model=DisconnectOut)
def disconnect(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    count = InstagramConnectService.disconnect_for_user(db, user_id=user_id)
    return DisconnectOut(disconnected_pages=count)
