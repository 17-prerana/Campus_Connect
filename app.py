"""Public event registration API backed by Supabase.

This intentionally has no authentication or authorization. Any caller can
read registrations and identifies a user with an ``X-User-Id`` request header.
"""

import os

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from httpx import HTTPError
from postgrest import APIError
from supabase import Client, ClientOptions, create_client
from supabase_auth.errors import AuthError

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be configured")

app = Flask(__name__)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# These names match the configured Supabase tables and schema.sql.
EVENT_FIELDS = "id,title,capacity,timestamp,organiser_id"


def error(message: str, status: int):
    return jsonify({"error": message}), status


@app.get("/")
def index():
    """Serve the CampusConnect web application."""
    return render_template("index.html")


def get_event(event_id: str, client: Client = supabase):
    response = client.table("events").select(EVENT_FIELDS).eq("id", event_id).execute()
    return response.data[0] if response.data else None


def is_duplicate_registration(exc: APIError) -> bool:
    """Postgres uses SQLSTATE 23505 for a unique-constraint conflict."""
    return getattr(exc, "code", None) == "23505"


def access_token():
    """Return the caller's bearer token, if supplied."""
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    return token.strip() if scheme.lower() == "bearer" else ""


def authenticated_user():
    """Validate the access token remotely and return its Supabase user."""
    token = access_token()
    if not token:
        return None, None
    try:
        response = supabase.auth.get_user(token)
        return response.user if response else None, token
    except (AuthError, HTTPError):
        return None, None


def authenticated_client(token: str) -> Client:
    """Create a request-scoped client so PostgREST evaluates RLS as this user."""
    return create_client(
        SUPABASE_URL,
        SUPABASE_KEY,
        ClientOptions(headers={"Authorization": f"Bearer {token}"}),
    )


def require_user():
    user, token = authenticated_user()
    if user is None:
        return None, None, error("Authentication is required", 401)
    return user, token, None


def auth_response(response, success_status: int):
    """Return a minimal, browser-safe authentication response."""
    session = getattr(response, "session", None)
    user = getattr(response, "user", None)
    if session is None:
        return jsonify({"message": "Check your email to confirm your account"}), 202
    return (
        jsonify(
            {
                "access_token": session.access_token,
                "user": {"id": str(user.id), "email": user.email},
            }
        ),
        success_status,
    )


@app.post("/api/auth/signup")
def sign_up():
    payload = request.get_json(silent=True) or {}
    email = payload.get("email", "").strip()
    password = payload.get("password", "")
    full_name = payload.get("full_name", "").strip()
    if not email or "@" not in email or len(password) < 8:
        return error("A valid email and password of at least 8 characters are required", 400)
    try:
        response = supabase.auth.sign_up(
            {"email": email, "password": password, "options": {"data": {"full_name": full_name}}}
        )
        return auth_response(response, 201)
    except (AuthError, HTTPError):
        return error("Unable to create account", 502)


@app.post("/api/auth/login")
def log_in():
    payload = request.get_json(silent=True) or {}
    email = payload.get("email", "").strip()
    password = payload.get("password", "")
    if not email or not password:
        return error("Email and password are required", 400)
    try:
        response = supabase.auth.sign_in_with_password({"email": email, "password": password})
        return auth_response(response, 200)
    except AuthError:
        return error("Invalid email or password", 401)
    except HTTPError:
        return error("Unable to sign in", 502)


@app.get("/api/events")
def list_events():
    """Browse all events."""
    try:
        response = supabase.table("events").select(EVENT_FIELDS).order("timestamp").execute()
        return jsonify({"events": response.data})
    except (APIError, HTTPError):
        return error("Unable to load events", 502)


@app.get("/api/events/<event_id>")
def event_details(event_id: str):
    """Return one event, or 404 when it does not exist."""
    try:
        event = get_event(event_id)
        if event is None:
            return error("Event not found", 404)
        return jsonify({"event": event})
    except (APIError, HTTPError):
        return error("Unable to load event", 502)


@app.post("/api/registrations")
def create_registration():
    """Create a registration for the authenticated Supabase user."""
    payload = request.get_json(silent=True) or {}
    event_id = payload.get("event_id")
    if not isinstance(event_id, str) or not event_id:
        return error("event_id is required", 400)
    user, token, auth_error = require_user()
    if auth_error:
        return auth_error
    client = authenticated_client(token)

    try:
        if get_event(event_id, client) is None:
            return error("Event not found", 404)
        response = client.table("registrations").insert(
            {"event_id": event_id, "user_id": str(user.id)}
        ).execute()
        return jsonify({"registration": response.data[0]}), 201
    except APIError as exc:
        if is_duplicate_registration(exc):
            return error("This user is already registered for the event", 409)
        return error("Unable to create registration", 502)
    except HTTPError:
        return error("Unable to create registration", 502)


@app.get("/api/me/registrations")
def my_registrations():
    """Return registrations belonging to the authenticated user."""
    user, token, auth_error = require_user()
    if auth_error:
        return auth_error
    client = authenticated_client(token)

    try:
        response = (
            client.table("registrations")
            .select("id,event_id,user_id,createdAt,events(id,title,capacity,timestamp,organiser_id)")
            .eq("user_id", str(user.id))
            .order("createdAt", desc=True)
            .execute()
        )
        return jsonify({"registrations": response.data})
    except (APIError, HTTPError):
        return error("Unable to load registrations", 502)


@app.get("/api/events/<event_id>/registrations")
def event_registrations(event_id: str):
    """Return the authenticated user's registration for one event."""
    user, token, auth_error = require_user()
    if auth_error:
        return auth_error
    client = authenticated_client(token)
    try:
        if get_event(event_id, client) is None:
            return error("Event not found", 404)
        response = (
            client.table("registrations")
            .select("id,event_id,user_id,createdAt")
            .eq("event_id", event_id)
            .eq("user_id", str(user.id))
            .order("createdAt")
            .execute()
        )
        return jsonify({"registrations": response.data})
    except (APIError, HTTPError):
        return error("Unable to load attendees", 502)


if __name__ == "__main__":
    app.run(port=5001)
