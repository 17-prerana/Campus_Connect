# CampusConnect

[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Flask 3.1.3](https://img.shields.io/badge/Flask-3.1.3-000000?logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![Supabase](https://img.shields.io/badge/Supabase-Postgres_%26_Auth-3ECF8E?logo=supabase&logoColor=white)](https://supabase.com/)

CampusConnect is a campus event-management platform for discovering events, creating a student account, and registering for activities. It combines a responsive, single-page web interface with a Flask API and Supabase for authentication, PostgreSQL data storage, and row-level access control.

## The problem

Campus events are often scattered across notices, chats, and social channels. That makes it harder for students to find activities and keep track of registrations. CampusConnect provides a single event catalogue with a protected registration flow, so event information is easy to browse while each student's registration data remains private.

## Features

| Area | Implemented functionality |
| --- | --- |
| Event discovery | Retrieves public events ordered by date/time and displays dashboard, browse, and event-detail views. |
| Search | Filters displayed events by title as the user types. |
| Event details | Presents an event's title, date/time, capacity, and registration call to action. |
| Authentication | Creates and signs in email/password users through Supabase Auth; sign-up stores the submitted full name in user metadata. |
| Registration | Requires a Supabase bearer token, validates it server-side, and creates a registration for that authenticated user. |
| Duplicate protection | Returns a conflict when the same user attempts to register for the same event twice; the database unique constraint is the final safeguard. |
| Private registration APIs | Lets a signed-in user retrieve their registrations, including associated event data, or their registration for a specific event. |
| Data protection | Uses Supabase Row Level Security (RLS) to keep registration records scoped to their owner. |
| Responsive UI | Uses a single HTML template with CSS and vanilla JavaScript for desktop and mobile layouts. |

> **Current UI scope:** Category buttons only update their selected visual state; they do not filter events. The profile's booking cards currently use the loaded event list and are not connected to the private registrations API. Profile details and event location/category labels are static presentation content.

## Technology stack

| Layer | Technologies |
| --- | --- |
| Backend | Python, Flask 3.1.3 |
| Database | Supabase PostgreSQL |
| Authentication | Supabase Auth (email/password) |
| Data API client | `supabase-py` 2.33.0 / PostgREST |
| Configuration | `python-dotenv` and environment variables |
| Frontend | HTML, CSS, vanilla JavaScript |

## Project structure

```text
CampusConnect/
|-- app.py              # Flask application, Supabase integration, and JSON API routes
|-- schema.sql          # PostgreSQL schema, indexes, grants, and RLS policies
|-- requirements.txt    # Pinned Python dependencies
|-- .env.example        # Safe template for required local configuration
|-- .gitignore          # Excludes secrets, virtual environments, and Python cache files
|-- README.md           # Project documentation
`-- templates/
    `-- index.html      # Responsive single-page client interface
```

## Getting started

### Prerequisites

- Python 3.9 or newer
- A Supabase project
- Email/password authentication enabled in that Supabase project

### 1. Clone the repository

```bash
git clone https://github.com/<your-username>/Campus_Connect.git
cd Campus_Connect
```

### 2. Create and activate a virtual environment

**Windows (PowerShell)**

```powershell
py -m venv venv
.\venv\Scripts\Activate.ps1
```

**macOS/Linux**

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Copy the committed template to create your local configuration file:

**Windows (PowerShell)**

```powershell
Copy-Item .env.example .env
```

**macOS/Linux**

```bash
cp .env.example .env
```

Then edit `.env` with values from your Supabase project's API settings:

```dotenv
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_KEY=your-supabase-publishable-or-anon-key
```

| Variable | Purpose |
| --- | --- |
| `SUPABASE_URL` | URL of the Supabase project used by the Flask application. |
| `SUPABASE_KEY` | Client-safe Supabase publishable key, or a legacy anon key, used for Auth and data requests. |

`.env` is intentionally ignored by Git. Do not commit it or use a Supabase `service_role` key in this application; elevated keys bypass RLS and must never be exposed to clients.

### 5. Create the database schema

1. Open the Supabase dashboard for your project.
2. Go to **SQL Editor** and create a new query.
3. Copy the complete contents of [`schema.sql`](schema.sql) into the editor and run it.
4. Add one or more rows to `public.events` through the Table Editor or SQL Editor so the catalogue has events to display.

### 6. Run locally

```bash
python app.py
```

Open [http://127.0.0.1:5001](http://127.0.0.1:5001). The application validates that both required environment variables are present when it starts.

## Supabase integration and database design

Flask initializes a Supabase client from `SUPABASE_URL` and `SUPABASE_KEY`. Public event reads use that client. For protected registration routes, the API extracts and validates the incoming `Authorization: Bearer <access-token>` token with Supabase Auth, then creates a request-scoped client forwarding that token. PostgREST can therefore enforce RLS using the current authenticated user.

### Tables

| Table | Purpose | Key fields |
| --- | --- | --- |
| `public.events` | Event catalogue exposed for browsing. | `id` UUID primary key, `title`, `capacity`, `timestamp`, `organiser_id` |
| `public.registrations` | A student's registration records. | `id` UUID primary key, `event_id`, `user_id`, `createdAt` |

`registrations.event_id` references `events.id` and uses `ON DELETE CASCADE`. The `(event_id, user_id)` unique constraint allows only one registration per user per event. The schema also indexes registrations by event/creation time and user/creation time to support the present registration queries.

### Access model

Both tables have RLS enabled. The schema grants:

- **Anyone** (`anon` and `authenticated`) can read public events.
- **Authenticated users** can read only registrations where `user_id` equals `auth.uid()`.
- **Authenticated users** can create only registrations whose `user_id` equals `auth.uid()`.

The schema grants no update or delete permissions for registrations, and no write permissions for events.

## API reference

| Method | Endpoint | Authentication | Description |
| --- | --- | --- | --- |
| `GET` | `/api/events` | No | List events ordered by `timestamp`. |
| `GET` | `/api/events/<event_id>` | No | Return a single event or `404`. |
| `POST` | `/api/auth/signup` | No | Create an email/password account; password must be at least 8 characters. |
| `POST` | `/api/auth/login` | No | Sign in with email and password. |
| `POST` | `/api/registrations` | Bearer token | Register the current user for an event. |
| `GET` | `/api/me/registrations` | Bearer token | Get the current user's registrations with event details. |
| `GET` | `/api/events/<event_id>/registrations` | Bearer token | Get the current user's registration(s) for one event. |

For protected endpoints, send the access token returned after a successful login or sign-up session:

```http
Authorization: Bearer <access-token>
```

## Future improvements

- Connect the profile booking view to `/api/me/registrations`.
- Implement real category and date filtering backed by event data.
- Add authorised organiser workflows for creating and managing events.
- Enforce event capacity atomically in the database before accepting a registration.
- Add automated coverage for Flask routes, authentication failures, and RLS policies.

## Security notes

- Commit `.env.example`, never `.env`.
- Use only a client-safe Supabase publishable or legacy anon key in `SUPABASE_KEY`.
- Registration ownership is checked in the Flask route and enforced again by database RLS.
