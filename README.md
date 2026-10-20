# DevTrack

A minimal backend API for tracking engineering issues, like a stripped-down GitHub Issues. Engineers register as **reporters**, file **issues**, set priorities, update status and remove issues.

Built with Django 6.1 and PostgreSQL 18 (running in Docker). The same API can also store everything in two JSON files (`data/reporters.json` and `data/issues.json`) with a single setting.

- [How to run](#how-to-run)
- [Storage: PostgreSQL or JSON files](#storage-postgresql-or-json-files)
- [API endpoints](#api-endpoints)
- [Data model and OOP design](#data-model-and-oop-design)
- [Design decision](#design-decision)
- [Postman screenshots](#postman-screenshots)
- [Project structure](#project-structure) (file-by-file guide: [PROJECT_GUIDE.md](PROJECT_GUIDE.md))

---

## How to run

You need **Python 3.12 or newer** and **Docker Desktop** (for PostgreSQL).

```bash
# 1. Clone the repository
git clone https://github.com/evsvipin/dev-track.git
cd dev-track

# 2. Start PostgreSQL in Docker (port 5433)
docker compose up -d

# 3. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

# 4. Install dependencies
pip install -r requirements.txt

# 5. Create the database tables
python manage.py migrate

# 6. Start the server
python manage.py runserver
```

The API is now available at **http://127.0.0.1:8000/api/**.

**Settings (optional):** everything works with the defaults. To change the secret key, the database password, or the storage backend, copy `.env.example` to `.env` and edit it. `docker-compose.yaml` reads the same `.env`.

**Run the tests:**

```bash
python manage.py test
```

There are 67 tests. Every API test runs twice, once against PostgreSQL and once against the JSON files. The tests use a temporary test database and a temporary folder, so your real data is never touched.

**Stop PostgreSQL:** `docker compose down`. Your data is kept in the `postgres_data` Docker volume.

---

## Storage: PostgreSQL or JSON files

The `STORAGE_BACKEND` setting decides where records are saved:

| `STORAGE_BACKEND` | Where data goes | Needs Docker? |
|---|---|---|
| `database` (default) | PostgreSQL tables `reporters` and `issues` | Yes |
| `json` | `data/reporters.json` and `data/issues.json` | No |

To use JSON files, set `STORAGE_BACKEND=json` in `.env` and run the server. No database or `migrate` is needed in that mode. The API behaves exactly the same either way.

**Database tables** (created by `python manage.py migrate`):

```
reporters                     issues
─────────────                 ──────────────────────────
id     bigint  PK  ◄──┐       id           bigint  PK
name   varchar(100)   │       title        varchar(200)
email  varchar(254)   │       description  text
team   varchar(50)    │       status       varchar(20)
                      │       priority     varchar(20)
                      └────── reporter_id  bigint  FK → reporters.id
                              created_at   timestamp
```

To look at the tables directly:

```bash
docker compose exec postgres psql -U postgres -d devtrack -c "select * from issues"
```

---

## API endpoints

Base URL: `http://127.0.0.1:8000`

| Method | URL | What it does |
|---|---|---|
| POST | `/api/reporters/` | Create a new reporter |
| GET | `/api/reporters/` | Get all reporters |
| GET | `/api/reporters/?id=1` | Get a single reporter by ID |
| PATCH | `/api/reporters/?id=1` | Update a reporter's name, email or team |
| DELETE | `/api/reporters/?id=1` | Delete a reporter (only if they have no issues) |
| POST | `/api/issues/` | Create a new issue |
| GET | `/api/issues/` | Get all issues |
| GET | `/api/issues/?id=1` | Get a single issue by ID |
| GET | `/api/issues/?status=open` | Get all issues with the given status |
| PATCH | `/api/issues/?id=1` | Update an issue (status, priority, title, …) |
| DELETE | `/api/issues/?id=1` | Delete an issue |

**Conventions**

- Request and response bodies are JSON. For POST and PATCH, set the header `Content-Type: application/json` (in Postman: Body → raw → JSON).
- **Keep the trailing slash** (`/api/issues/`, not `/api/issues`).
- PATCH and DELETE need `?id=` in the URL.
- **IDs are assigned by the server.** An `id` sent in a POST body is ignored.
- Every error response has the shape `{"error": "<message>"}`.
- Other methods (e.g. PUT) return `405 Method Not Allowed`.

### Status codes

| Code | When |
|---|---|
| 200 OK | GET, PATCH or DELETE succeeded |
| 201 Created | POST created a record |
| 400 Bad Request | Invalid JSON, a missing field, a validation failure, an unknown `reporter_id`, a missing or non-integer `?id=`, or a field that can't be updated |
| 404 Not Found | No record matches `?id=` |
| 405 Method Not Allowed | The method isn't GET, POST, PATCH or DELETE |
| 409 Conflict | Deleting a reporter who still has issues |

---

### Reporters

#### POST `/api/reporters/` — create a reporter

| Field | Type | Required | Rules |
|---|---|---|---|
| `name` | string | yes | Cannot be empty |
| `email` | string | yes | Must contain `@` |
| `team` | string | yes | Cannot be empty, e.g. `backend`, `frontend`, `devops` |

**Request**

```json
{
  "name": "Asha Rao",
  "email": "asha@example.com",
  "team": "backend"
}
```

**Response — 201 Created**

```json
{
  "id": 1,
  "name": "Asha Rao",
  "email": "asha@example.com",
  "team": "backend"
}
```

**Response — 400 Bad Request**

```json
{ "error": "Invalid email" }
```

Other 400 messages: `Name cannot be empty`, `Team cannot be empty`, `Missing required field(s): email, team`, `Request body must be valid JSON`.

#### GET `/api/reporters/` — get all reporters

**Response — 200 OK**

```json
[
  { "id": 1, "name": "Asha Rao", "email": "asha@example.com", "team": "backend" },
  { "id": 2, "name": "Ben Lee", "email": "ben@example.com", "team": "frontend" }
]
```

Returns `[]` when there are no reporters.

#### GET `/api/reporters/?id=1` — get one reporter

**Response — 200 OK**

```json
{ "id": 1, "name": "Asha Rao", "email": "asha@example.com", "team": "backend" }
```

**Response — 404 Not Found**

```json
{ "error": "Reporter not found" }
```

**Response — 400 Bad Request** (e.g. `?id=abc`)

```json
{ "error": "id must be an integer" }
```

#### PATCH `/api/reporters/?id=1` — update a reporter

Send only the fields you want to change: any of `name`, `email`, `team`. The same rules as POST apply.

**Request**

```json
{ "team": "devops" }
```

**Response — 200 OK**

```json
{ "id": 1, "name": "Asha Rao", "email": "asha@example.com", "team": "devops" }
```

**Errors**

- `400`: `{"error": "Cannot update field(s): id. Allowed: name, email, team"}`, `{"error": "No fields to update"}`, `{"error": "id query parameter is required, e.g. ?id=1"}`, or a validation message
- `404`: `{"error": "Reporter not found"}`

#### DELETE `/api/reporters/?id=1` — delete a reporter

**Response — 200 OK**

```json
{ "message": "Reporter 1 deleted" }
```

**Response — 409 Conflict**: the reporter still has issues. Delete those issues, or move them to another reporter with `PATCH /api/issues/?id=…` and `{"reporter_id": 2}`.

```json
{ "error": "Reporter 1 has 2 issue(s). Delete them or move them to another reporter first" }
```

**Response — 404 Not Found**: `{"error": "Reporter not found"}`

---

### Issues

#### POST `/api/issues/` — create an issue

| Field | Type | Required | Rules |
|---|---|---|---|
| `title` | string | yes | Cannot be empty |
| `description` | string | yes | Full details (may be empty) |
| `status` | string | yes | One of `open`, `in_progress`, `resolved`, `closed` |
| `priority` | string | yes | One of `low`, `medium`, `high`, `critical` |
| `reporter_id` | integer | yes | Must be the ID of an existing reporter |

The server adds `id` and `created_at`. The response also includes a `message` built by the issue's `describe()` method, which depends on the priority:

| Priority | Class used | `message` |
|---|---|---|
| `critical` | `CriticalIssue` | `[URGENT] <title> — needs immediate attention` |
| `low` | `LowPriorityIssue` | `<title> — low priority, handle when free` |
| `medium`, `high` | `Issue` | `<title> [<priority>]` |

**Request**

```json
{
  "id": 1,
  "title": "Login button not working on mobile",
  "description": "Users on iOS 17 cannot tap the login button",
  "status": "open",
  "priority": "critical",
  "reporter_id": 1
}
```

**Response — 201 Created**

```json
{
  "id": 1,
  "title": "Login button not working on mobile",
  "description": "Users on iOS 17 cannot tap the login button",
  "status": "open",
  "priority": "critical",
  "reporter_id": 1,
  "created_at": "2026-10-20 18:07:57.965079",
  "message": "[URGENT] Login button not working on mobile — needs immediate attention"
}
```

**Response — 400 Bad Request**

```json
{ "error": "Title cannot be empty" }
```

Other 400 messages: `Status must be one of: open, in_progress, resolved, closed`, `Priority must be one of: low, medium, high, critical`, `Reporter with id 9 does not exist`, `reporter_id must be a positive integer`, `Missing required field(s): ...`, `Request body must be valid JSON`.

#### GET `/api/issues/` — get all issues

**Response — 200 OK**: a list of every issue, ordered by `id` (`[]` if there are none).

#### GET `/api/issues/?id=1` — get one issue

**Response — 200 OK**

```json
{
  "id": 1,
  "title": "Login button not working on mobile",
  "description": "Users on iOS 17 cannot tap the login button",
  "status": "open",
  "priority": "critical",
  "reporter_id": 1,
  "created_at": "2026-10-20 18:07:57.965079"
}
```

**Response — 404 Not Found**

```json
{ "error": "Issue not found" }
```

#### GET `/api/issues/?status=open` — filter issues by status

**Response — 200 OK**: a list of the issues whose `status` matches (`[]` if none match).

**Response — 400 Bad Request** (e.g. `?status=done`)

```json
{ "error": "Status must be one of: open, in_progress, resolved, closed" }
```

If both `id` and `status` are given, `id` wins.

#### PATCH `/api/issues/?id=1` — update an issue

Send only the fields you want to change: any of `title`, `description`, `status`, `priority`, `reporter_id`. The same rules as POST apply. `id` and `created_at` can't be changed. If the priority changes, the issue becomes the matching class, so `message` changes too.

**Request**

```json
{ "status": "in_progress", "priority": "high" }
```

**Response — 200 OK**

```json
{
  "id": 1,
  "title": "Login button not working on mobile",
  "description": "Users on iOS 17 cannot tap the login button",
  "status": "in_progress",
  "priority": "high",
  "reporter_id": 1,
  "created_at": "2026-10-20 18:07:57.965079",
  "message": "Login button not working on mobile [high]"
}
```

**Errors**

- `400`: `{"error": "Cannot update field(s): created_at. Allowed: title, description, status, priority, reporter_id"}`, `{"error": "No fields to update"}`, `{"error": "id query parameter is required, e.g. ?id=1"}`, or a validation message
- `404`: `{"error": "Issue not found"}`

#### DELETE `/api/issues/?id=1` — delete an issue

**Response — 200 OK**

```json
{ "message": "Issue 1 deleted" }
```

**Response — 404 Not Found**: `{"error": "Issue not found"}`

---

## Data model and OOP design

**Reporter**: `id`, `name`, `email`, `team`.
**Issue**: `id`, `title`, `description`, `status`, `priority`, `reporter_id`, `created_at`.

The relationship is **one Reporter → many Issues**. Each issue stores the `reporter_id` of the person who filed it. In PostgreSQL this is a foreign key from `issues.reporter_id` to `reporters.id`.

The OOP classes live in [issues/models.py](issues/models.py):

```
BaseEntity (abstract: validate(), to_dict())
├── Reporter
└── Issue                (describe() -> "<title> [<priority>]")
    ├── CriticalIssue    (describe() overridden)
    └── LowPriorityIssue (describe() overridden)
```

- **`BaseEntity`** is an abstract base class. It declares `validate()` as an `@abstractmethod`, so every entity must implement it. It also provides a shared `to_dict()` that turns any entity into a dict.
- **`Reporter`** and **`Issue`** inherit from `BaseEntity` and each implement their own `validate()`.
- **`CriticalIssue`** and **`LowPriorityIssue`** inherit from `Issue` and override `describe()` (method overriding). The view calls `issue.describe()` without caring which class it has.

On `POST /api/issues/`, the view picks the class from the priority, calls `validate()`, saves `to_dict()`, and adds `describe()` to the response as `message`.

Storage uses the same pattern ([issues/storage.py](issues/storage.py)):

```
BaseStorage (abstract: find_all, find_by_id, create, update, delete)
├── JsonStorage       reads and writes data/*.json
└── DatabaseStorage   uses the Django ORM models in issues/db_models.py
```

---

## Design decision

**Business rules and storage are kept in separate classes.**

The OOP classes (`Reporter`, `Issue` and the subclasses) decide *what is valid* and *how an issue describes itself*. They know nothing about files or databases. Storage classes (`JsonStorage`, `DatabaseStorage`) decide *where records are saved*. They know nothing about validation. Views connect the two, and they only ever talk to the abstract `BaseStorage` interface.

Why:

- **The move from JSON files to PostgreSQL didn't touch any business rules.** Adding the database meant writing one new class, `DatabaseStorage`. `validate()` and `describe()` stayed exactly the same, and both backends pass the same tests.
- **Each rule is written once.** "A title can't be empty" lives only in `Issue.validate()`, and the same check runs for POST, PATCH, JSON and database.
- **Polymorphism, twice.** The views call `issue.describe()` without knowing which `Issue` subclass they have, and call `storage.create(...)` without knowing which storage backend they have.

Other decisions:

- **The `message` from `describe()` is returned but never stored.** It can be rebuilt from `title` and `priority` at any time. A stored copy would go stale when the priority changes (for example `low` → `critical`).
- **Django ORM models are separate from the OOP classes** ([issues/db_models.py](issues/db_models.py)). An ORM model can't inherit from the brief's `BaseEntity` (their metaclasses clash), and its `__dict__` contains Django internals that would leak into `to_dict()`.
- **The server assigns IDs.** With a database, auto-increment IDs avoid two clients picking the same number. The `id` in the brief's sample request is accepted but ignored, and on an empty database the first issue still gets `id: 1`.
- **A reporter with issues can't be deleted** (409). Deleting them would leave issues pointing to a reporter who doesn't exist. The database enforces this as well (`on_delete=PROTECT`).
- **PATCH instead of PUT.** Clients usually change one or two fields (most often `status`), so they send only what changes.

---

## Postman screenshots

<!-- Save your Postman screenshots in docs/screenshots/ with these names. -->

**Success: `POST /api/issues/` (201 Created)**

![POST /api/issues/ success](docs/screenshots/create-issue-success.png)

**Success: `PATCH /api/issues/?id=1` (200 OK)**

![PATCH /api/issues/ success](docs/screenshots/update-issue-success.png)

**Failure: `POST /api/issues/` with an empty title (400 Bad Request)**

![POST /api/issues/ validation failure](docs/screenshots/create-issue-400.png)

**Failure: `GET /api/issues/?id=99` (404 Not Found)**

![GET /api/issues/?id=99 not found](docs/screenshots/get-issue-404.png)

A ready-made Postman collection with every request is in [docs/DevTrack.postman_collection.json](docs/DevTrack.postman_collection.json). In Postman, choose **Import** and select that file.

---

## Project structure

```
dev-track/
├── manage.py                 # Django command-line entry point
├── requirements.txt          # Python dependencies
├── docker-compose.yaml       # PostgreSQL 18 container
├── .env.example              # Settings template (copy to .env)
├── data/
│   ├── reporters.json        # Reporter records (JSON mode)
│   └── issues.json           # Issue records (JSON mode)
├── devtrack/                 # Django project: settings and root URLs
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
├── issues/                   # Django app: the API
│   ├── models.py             # OOP classes: BaseEntity, Reporter, Issue, subclasses
│   ├── db_models.py          # Django ORM models = PostgreSQL tables
│   ├── storage.py            # BaseStorage, JsonStorage, DatabaseStorage
│   ├── views.py              # Endpoint logic
│   ├── urls.py               # Endpoint routes
│   ├── migrations/           # Database table definitions generated by Django
│   ├── apps.py
│   └── tests.py              # Automated tests
├── docs/
│   ├── DevTrack.postman_collection.json
│   └── screenshots/
├── README.md
└── PROJECT_GUIDE.md          # What each file does and why
```

See [PROJECT_GUIDE.md](PROJECT_GUIDE.md) for a walkthrough of every file and how a request flows through them.
