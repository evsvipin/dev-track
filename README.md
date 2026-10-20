# DevTrack

A minimal backend API for tracking engineering issues, like a stripped-down GitHub Issues. Engineers register as **reporters**, file **issues**, set priorities and track status.

Built with Django 6.1. Data is stored in two JSON files: `data/reporters.json` and `data/issues.json`. There is no database.

- [How to run](#how-to-run)
- [API endpoints](#api-endpoints)
- [Data model and OOP design](#data-model-and-oop-design)
- [Design decision](#design-decision)
- [Postman screenshots](#postman-screenshots)
- [Project structure](#project-structure) (file-by-file guide: [PROJECT_GUIDE.md](PROJECT_GUIDE.md))

---

## How to run

You need **Python 3.12 or newer**.

```bash
# 1. Clone the repository
git clone https://github.com/evsvipin/dev-track.git
cd dev-track

# 2. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Start the server
python manage.py runserver
```

The API is now available at **http://127.0.0.1:8000/api/**.

**Optional:** to set your own secret key or debug flag, copy `.env.example` to `.env` and edit it. Without a `.env` file the project runs with local development defaults.

**Run the tests:**

```bash
python manage.py test
```

The tests use a temporary folder, so they never change the real JSON files.

---

## API endpoints

Base URL: `http://127.0.0.1:8000`

| Method | URL | What it does |
|---|---|---|
| POST | `/api/reporters/` | Create a new reporter |
| GET | `/api/reporters/` | Get all reporters |
| GET | `/api/reporters/?id=1` | Get a single reporter by ID |
| POST | `/api/issues/` | Create a new issue |
| GET | `/api/issues/` | Get all issues |
| GET | `/api/issues/?id=1` | Get a single issue by ID |
| GET | `/api/issues/?status=open` | Get all issues with the given status |

**Conventions**

- Request and response bodies are JSON. For POST requests, set the header `Content-Type: application/json` (in Postman: Body → raw → JSON).
- **Keep the trailing slash** (`/api/issues/`, not `/api/issues`).
- Every error response has the shape `{"error": "<message>"}`.
- Other methods (PUT, DELETE, …) return `405 Method Not Allowed`.

### Status codes

| Code | When |
|---|---|
| 200 OK | A GET request succeeded |
| 201 Created | A POST request created a record |
| 400 Bad Request | Invalid JSON, a missing field, a validation failure, an unknown `reporter_id`, or a non-integer `?id=` |
| 404 Not Found | No record matches `?id=` |
| 405 Method Not Allowed | The method is not GET or POST |
| 409 Conflict | A record with the given `id` already exists |

---

### POST `/api/reporters/` — create a reporter

| Field | Type | Required | Rules |
|---|---|---|---|
| `id` | integer | no | Positive and unique. If left out, the next free ID is used. |
| `name` | string | yes | Cannot be empty |
| `email` | string | yes | Must contain `@` |
| `team` | string | yes | Cannot be empty, e.g. `backend`, `frontend`, `devops` |

**Request**

```json
{
  "id": 1,
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

Other 400 messages: `Name cannot be empty`, `Team cannot be empty`, `Missing required field(s): email, team`, `Request body must be valid JSON`, `id must be a positive integer`.

**Response — 409 Conflict**

```json
{ "error": "Reporter with id 1 already exists" }
```

### GET `/api/reporters/` — get all reporters

**Response — 200 OK**

```json
[
  { "id": 1, "name": "Asha Rao", "email": "asha@example.com", "team": "backend" },
  { "id": 2, "name": "Ben Lee", "email": "ben@example.com", "team": "frontend" }
]
```

Returns `[]` when there are no reporters.

### GET `/api/reporters/?id=1` — get one reporter

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

---

### POST `/api/issues/` — create an issue

| Field | Type | Required | Rules |
|---|---|---|---|
| `id` | integer | no | Positive and unique. If left out, the next free ID is used. |
| `title` | string | yes | Cannot be empty |
| `description` | string | yes | Full details (may be empty) |
| `status` | string | yes | One of `open`, `in_progress`, `resolved`, `closed` |
| `priority` | string | yes | One of `low`, `medium`, `high`, `critical` |
| `reporter_id` | integer | yes | Must be the ID of an existing reporter |

The server adds `created_at` (the time the issue was created). The response also includes a `message` built by the issue's `describe()` method. It depends on the priority:

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
  "created_at": "2026-10-20 17:53:51.216222",
  "message": "[URGENT] Login button not working on mobile — needs immediate attention"
}
```

**Response — 400 Bad Request**

```json
{ "error": "Title cannot be empty" }
```

Other 400 messages: `Status must be one of: open, in_progress, resolved, closed`, `Priority must be one of: low, medium, high, critical`, `Reporter with id 9 does not exist`, `Missing required field(s): ...`, `Request body must be valid JSON`.

**Response — 409 Conflict**

```json
{ "error": "Issue with id 1 already exists" }
```

### GET `/api/issues/` — get all issues

**Response — 200 OK**: a list of every issue (`[]` if there are none).

### GET `/api/issues/?id=1` — get one issue

**Response — 200 OK**

```json
{
  "id": 1,
  "title": "Login button not working on mobile",
  "description": "Users on iOS 17 cannot tap the login button",
  "status": "open",
  "priority": "critical",
  "reporter_id": 1,
  "created_at": "2026-10-20 17:53:51.216222"
}
```

**Response — 404 Not Found**

```json
{ "error": "Issue not found" }
```

### GET `/api/issues/?status=open` — filter issues by status

**Response — 200 OK**: a list of the issues whose `status` matches (`[]` if none match).

**Response — 400 Bad Request** (e.g. `?status=done`)

```json
{ "error": "Status must be one of: open, in_progress, resolved, closed" }
```

If both `id` and `status` are given, `id` wins.

---

## Data model and OOP design

**Reporter**: `id`, `name`, `email`, `team`.
**Issue**: `id`, `title`, `description`, `status`, `priority`, `reporter_id`, `created_at`.

The relationship is **one Reporter → many Issues**. Each issue stores the `reporter_id` of the person who filed it. Reporters do not store a list of their issues.

All classes live in [issues/models.py](issues/models.py):

```
BaseEntity (abstract: validate(), to_dict())
├── Reporter
└── Issue                (describe() -> "<title> [<priority>]")
    ├── CriticalIssue    (describe() overridden)
    └── LowPriorityIssue (describe() overridden)
```

- **`BaseEntity`** is an abstract base class. It declares `validate()` as an `@abstractmethod`, so every entity must implement it. It also provides a shared `to_dict()` that turns any entity into a dict ready for JSON.
- **`Reporter`** and **`Issue`** inherit from `BaseEntity` and each implement their own `validate()`.
- **`CriticalIssue`** and **`LowPriorityIssue`** inherit from `Issue` and override `describe()`. This is method overriding: the view calls `issue.describe()` without caring which class it is, and the subclass decides the text.

On `POST /api/issues/`, the view picks the class from the priority, calls `validate()`, saves `to_dict()` to `issues.json`, and adds `describe()` to the response as `message`.

---

## Design decision

**The `message` from `describe()` is returned in the POST response but not saved to `issues.json`.**

The message can always be rebuilt from the stored `title` and `priority`, so saving it would duplicate data. Duplicated data also goes stale: if an issue's priority were later changed from `low` to `critical`, a stored message would still say "handle when free". Saving only the real fields (`to_dict()`) keeps `issues.json` as the single source of truth.

Other decisions:

- **Validation lives in the classes, not the views.** `Reporter.validate()` and `Issue.validate()` raise `ValueError`, and the view turns any `ValueError` into a 400 response. The rules are written once and reused anywhere an entity is created.
- **`id` is optional on POST.** The brief's sample request sends an `id`, so a client-supplied `id` is accepted and checked for uniqueness (409 if taken). If it's left out, the server assigns the next free ID, so clients don't have to track IDs themselves.
- **`reporter_id` must point to an existing reporter.** Without this check an issue could reference someone who doesn't exist, which breaks the 1:many relationship.
- **File access is in one module** ([issues/storage.py](issues/storage.py)). Views never open files directly, so moving to a real database later would only change that one file.

---

## Postman screenshots

<!-- Save your Postman screenshots in docs/screenshots/ with these names. -->

**Success: `POST /api/issues/` (201 Created)**

![POST /api/issues/ success](docs/screenshots/create-issue-success.png)

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
├── .env.example              # Optional settings template
├── data/
│   ├── reporters.json        # Reporter records
│   └── issues.json           # Issue records
├── devtrack/                 # Django project (settings and root URLs)
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
├── issues/                   # Django app with the API
│   ├── models.py             # OOP classes: BaseEntity, Reporter, Issue, subclasses
│   ├── views.py              # Endpoint logic
│   ├── urls.py               # Endpoint routes
│   ├── storage.py            # JSON file read/write helpers
│   ├── apps.py
│   └── tests.py              # Automated tests
├── docs/
│   ├── DevTrack.postman_collection.json
│   └── screenshots/
├── README.md
└── PROJECT_GUIDE.md          # What each file does and why
```

See [PROJECT_GUIDE.md](PROJECT_GUIDE.md) for a walkthrough of every file and how a request flows through them.
