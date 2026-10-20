# DevTrack Project Guide

This guide explains what every file in the project does, what is written in it, and how the files work together to answer an API request.

For how to run the project and the full API reference, see [README.md](README.md).

---

## 1. The big picture: how a request flows

Here is what happens when Postman sends `POST /api/issues/`:

```
Postman
  │  POST http://127.0.0.1:8000/api/issues/   { "title": ..., "priority": "critical", ... }
  ▼
manage.py runserver            starts Django using devtrack/settings.py
  ▼
devtrack/urls.py               "api/..."  → hand the rest of the URL to issues/urls.py
  ▼
issues/urls.py                 "issues/"  → call the view function views.issues
  ▼
issues/views.py                issues()   → method is POST → create_issue()
  │   ├── issues/models.py     builds CriticalIssue(...), calls validate(), to_dict(), describe()
  │   └── issues/storage.py    get_storage() → DatabaseStorage (or JsonStorage)
  │         └── issues/db_models.py   IssueModel.objects.create(...)  → INSERT INTO issues ...
  ▼                                                                     (PostgreSQL in Docker)
JsonResponse                   { ..., "message": "[URGENT] ..." }   status 201
  ▼
Postman shows the response
```

Each file has one job:

| Layer | File | Job |
|---|---|---|
| Configuration | `devtrack/settings.py`, `.env` | How Django is set up and which database/storage to use |
| Routing | `devtrack/urls.py`, `issues/urls.py` | Which URL goes to which function |
| Request handling | `issues/views.py` | Read the request, decide the response |
| Business rules | `issues/models.py` | What a Reporter/Issue is and what makes one valid |
| Storage | `issues/storage.py` | Saving and loading records (JSON files or database) |
| Database tables | `issues/db_models.py`, `issues/migrations/` | The PostgreSQL table definitions |
| Infrastructure | `docker-compose.yaml` | Runs PostgreSQL in Docker |

---

## 2. Root folder

### `manage.py`

Django's command-line tool for this project. You don't edit it. It tells Django to use `devtrack.settings` and runs the command you give it:

| Command | What it does |
|---|---|
| `python manage.py runserver` | Starts the development server at http://127.0.0.1:8000 |
| `python manage.py migrate` | Creates or updates the database tables from `issues/migrations/` |
| `python manage.py makemigrations` | After changing `issues/db_models.py`, writes a new migration file describing the change |
| `python manage.py test` | Runs the tests in `issues/tests.py` |
| `python manage.py check` | Checks the project for configuration errors |

### `docker-compose.yaml`

Describes the PostgreSQL container so you don't have to install PostgreSQL yourself.

| Part | Meaning |
|---|---|
| `image: postgres:18` | Use the official PostgreSQL 18 image |
| `ports: "5433:5432"` | PostgreSQL listens on 5432 inside the container, and you reach it on **5433** on your computer (so it doesn't clash with any other PostgreSQL on 5432) |
| `environment:` | User, password and database name. Read from `.env`, with defaults (`postgres` / `admin` / `devtrack`). The database is created on the first start. |
| `volumes: postgres_data` | Stores the database files in a Docker volume, so data survives `docker compose down` and restarts |
| `healthcheck:` | Docker checks that PostgreSQL is ready to accept connections |

Commands: `docker compose up -d` (start in the background), `docker compose down` (stop, data is kept), `docker compose ps` (status).

### `requirements.txt`

The Python packages the project needs, with exact versions. Install them with `pip install -r requirements.txt`.

| Package | Why it is needed |
|---|---|
| `Django` | The web framework |
| `psycopg`, `psycopg-binary` | The driver Django uses to talk to PostgreSQL |
| `python-dotenv` | Loads settings from the `.env` file |
| `asgiref`, `sqlparse`, `tzdata` | Packages Django itself depends on (`tzdata` provides time zone data on Windows) |

### `.env.example` and `.env`

`.env` holds settings that may differ per machine or should stay secret: the secret key, debug flag, `STORAGE_BACKEND`, and the PostgreSQL connection details. It's listed in `.gitignore`, so it is never pushed. `.env.example` is the template that is pushed. Both Django (through `python-dotenv`) and Docker Compose read `.env`. If it's missing, the defaults are used.

### `.gitignore`

Tells Git which files to keep only on your machine: the virtual environment (`.venv/`), Python cache files (`__pycache__/`), `.env`, local SQLite files and editor settings.

### `data/reporters.json` and `data/issues.json`

Used only when `STORAGE_BACKEND=json`. Each file is a JSON list of records, and they start empty (`[]`). Example contents of `issues.json`:

```json
[
    {
        "id": 1,
        "title": "Login button not working on mobile",
        "description": "Users on iOS 17 cannot tap the login button",
        "status": "open",
        "priority": "critical",
        "reporter_id": 1,
        "created_at": "2026-10-20 18:07:57.965079"
    }
]
```

---

## 3. `devtrack/`: the Django project

This folder is the **project**. It holds configuration for the whole site and was created by `django-admin startproject`. A Django site has exactly one project and one or more apps (here, `issues`).

### `devtrack/settings.py`

The configuration for the whole project. The important parts:

| Setting | Value | Meaning |
|---|---|---|
| `load_dotenv(...)` | | Loads `.env` into environment variables before the settings read them |
| `SECRET_KEY` | from `.env`, or a dev default | Used by Django for signing. Must be secret in production. |
| `DEBUG` | `True` by default | Shows detailed error pages. Turn off in production. |
| `ALLOWED_HOSTS` | `localhost`, `127.0.0.1` | Host names the server will answer to |
| `INSTALLED_APPS` | `['issues']` | **Registers the `issues` app** so Django loads its models, migrations and tests |
| `MIDDLEWARE` | security, common, CSRF, clickjacking | Code that runs on every request and response |
| `ROOT_URLCONF` | `'devtrack.urls'` | The first URL file Django looks at |
| `STORAGE_BACKEND` | `'database'` by default | **Custom setting**: `database` or `json`, read by `issues/storage.py` |
| `DATABASES` | PostgreSQL on `localhost:5433`, database `devtrack` | Connection details, matching `docker-compose.yaml`. Set to `{}` in JSON mode so no database is needed. |
| `DEFAULT_AUTO_FIELD` | `BigAutoField` | Type of the auto-increment `id` column |
| `DATA_DIR` | `BASE_DIR / 'data'` | **Custom setting**: folder for the JSON files |
| `USE_TZ` | `False` | Times are stored as plain local times, so `created_at` looks like the brief's `str(datetime.now())` |

### `devtrack/urls.py`

The **root URL file**. Django checks every incoming URL against `urlpatterns` here first.

```python
urlpatterns = [
    path('api/', include('issues.urls')),
]
```

This means: "any URL starting with `api/` belongs to the issues app. Remove `api/` and look up the rest in `issues/urls.py`." This is how the app's URLs are **wired into the project**.

### `devtrack/wsgi.py` and `devtrack/asgi.py`

Entry points used by production web servers (WSGI for servers like Gunicorn, ASGI for async servers like Uvicorn). `runserver` uses WSGI. You don't need to edit them.

### `devtrack/__init__.py`

An empty file that marks `devtrack/` as a Python package so it can be imported (for example `devtrack.settings`).

---

## 4. `issues/`: the Django app

This folder is an **app**: a self-contained feature, created by `python manage.py startapp`. Everything about reporters and issues lives here.

### `issues/models.py`: the OOP classes (business rules)

**What we write here:** the classes that describe our data and its rules. They are **plain Python classes**, not database tables. They decide what is valid; they don't save anything.

```
BaseEntity (abstract)
├── Reporter
└── Issue
    ├── CriticalIssue
    └── LowPriorityIssue
```

| Class / item | What it does | OOP concept |
|---|---|---|
| `ISSUE_STATUSES`, `ISSUE_PRIORITIES` | The allowed values for status and priority | Constants |
| `BaseEntity` | Abstract parent class. Declares `validate()` and provides `to_dict()`. | **Abstraction**: `ABC` + `@abstractmethod` mean `BaseEntity()` can't be created, and every subclass must write its own `validate()` |
| `BaseEntity.to_dict()` | Returns all the object's attributes (`self.__dict__`) as a dict | **Inheritance**: written once, used by every subclass |
| `Reporter` | Stores `id`, `name`, `email`, `team`. `validate()` checks the name and team aren't empty and the email has `@`. | Inherits from `BaseEntity` |
| `Issue` | Stores `id`, `title`, `description`, `status`, `priority`, `reporter_id`, `created_at`. `validate()` checks the title, status, priority and reporter_id. `describe()` returns `"<title> [<priority>]"`. | Inherits from `BaseEntity` |
| `CriticalIssue` | Overrides `describe()` → `"[URGENT] <title> — needs immediate attention"` | **Method overriding / polymorphism** |
| `LowPriorityIssue` | Overrides `describe()` → `"<title> — low priority, handle when free"` | **Method overriding / polymorphism** |
| `validate_id()`, `validate_positive_int()`, `validate_non_empty_string()` | Small helpers so `validate()` methods don't repeat checks. `id` may be `None` for a record that hasn't been saved yet. | Reuse |

`validate()` signals a problem by **raising `ValueError`** with a readable message. The view catches it and returns it as a 400 error, so the message in `{"error": "Title cannot be empty"}` comes straight from `Issue.validate()`.

The last line imports the ORM models from `db_models.py`. Django only discovers database models through each app's `models` module, so without this import `makemigrations` would not see the tables.

### `issues/db_models.py`: the database tables (Django ORM)

**What we write here:** one class per database table. Each class attribute is a column. Django turns these classes into SQL (`CREATE TABLE`) through migrations, and into queries (`SELECT`, `INSERT`, …) through `Model.objects`.

| Class | Table | Columns |
|---|---|---|
| `ReporterModel` | `reporters` | `id` (auto), `name`, `email`, `team` |
| `IssueModel` | `issues` | `id` (auto), `title`, `description`, `status`, `priority`, `reporter_id`, `created_at` |

Key pieces:

- **`models.CharField(max_length=...)`**, **`models.TextField()`**, **`models.DateTimeField()`**: column types (`varchar`, `text`, `timestamp`).
- **`choices=`** on `status` and `priority` lists the allowed values, built from the same constants as the OOP classes.
- **`models.ForeignKey(ReporterModel, on_delete=models.PROTECT, related_name='issues')`**: the **one-to-many relationship**. It creates the `reporter_id` column with a foreign-key constraint to `reporters.id`. `PROTECT` makes the database refuse to delete a reporter who still has issues. `related_name='issues'` lets you write `reporter.issues.all()`.
- **`class Meta: db_table = 'issues'`** sets the table name (otherwise Django would call it `issues_issuemodel`). `ordering = ['id']` returns rows in ID order.
- **`to_dict()`** converts a row into the same dict shape the JSON files use, so the views get identical data from both backends.

Why separate from `models.py`? An ORM model can't also inherit from `BaseEntity`, because Django's model metaclass clashes with `ABC`'s. Its `__dict__` also contains Django internals (`_state`) that would leak into `to_dict()`. So the brief's OOP classes stay pure, and the tables live here.

### `issues/migrations/`

**What is in here:** files generated by `python manage.py makemigrations` that describe how to build the tables. `0001_initial.py` creates `reporters` and `issues`. `python manage.py migrate` runs them against PostgreSQL and records what was applied in the `django_migrations` table. **Don't edit migrations by hand.** Change `db_models.py`, then run `makemigrations` again to get a new numbered file.

### `issues/storage.py`: where records are saved

**What we write here:** all saving and loading. Views never open files or query tables directly. They call `get_storage()` and use the methods below.

```
BaseStorage (abstract)
├── JsonStorage       data/reporters.json, data/issues.json
└── DatabaseStorage   PostgreSQL through ReporterModel / IssueModel
```

| Method | JsonStorage | DatabaseStorage |
|---|---|---|
| `find_all(entity, **filters)` | Read the file, keep records whose fields match | `Model.objects.filter(**filters)` |
| `find_by_id(entity, id)` | Loop until `record['id'] == id` | `Model.objects.filter(pk=id).first()` |
| `create(entity, record)` | Next id = highest id + 1, append, write the file | `Model.objects.create(...)` (the database assigns the id) |
| `update(entity, id, record)` | Replace the record in the list, write the file | `Model.objects.filter(pk=id).update(...)` |
| `delete(entity, id)` | Remove from the list, write the file | `Model.objects.filter(pk=id).delete()` |

`entity` is `REPORTERS` or `ISSUES`. `get_storage()` looks at `settings.STORAGE_BACKEND` and returns a `JsonStorage()` or `DatabaseStorage()`. Because both follow `BaseStorage`, the views work with either one. That's **polymorphism**, the same idea as `describe()`.

### `issues/views.py`: the endpoint logic

**What we write here:** the functions that receive a request and return a response. A view reads the request, uses the OOP classes to validate, uses storage to save or load, and builds a `JsonResponse`.

Each URL has one **dispatcher** view that checks `request.method` and calls the right helper:

| Function | Called for | What it does |
|---|---|---|
| `reporters(request)` | `/api/reporters/` | Sends GET/POST/PATCH/DELETE to the helpers below, anything else → 405 |
| `get_reporters` | `GET` | All reporters, or one with `?id=` (404 if missing) |
| `create_reporter` | `POST` | Builds a `Reporter`, `validate()`, saves `to_dict()`, returns 201 with the new id |
| `update_reporter` | `PATCH ?id=` | Loads the reporter, merges the changed fields, `validate()`, saves, returns 200 |
| `delete_reporter` | `DELETE ?id=` | 409 if the reporter still has issues, otherwise deletes and returns 200 |
| `issues(request)` | `/api/issues/` | Sends GET/POST/PATCH/DELETE to the helpers below, anything else → 405 |
| `get_issues` | `GET` | One issue by `?id=` (404 if missing), issues filtered by `?status=`, or all issues |
| `create_issue` | `POST` | Chooses `CriticalIssue` / `LowPriorityIssue` / `Issue` from the priority, `validate()`, checks the reporter exists, saves, returns it with `"message": describe()` and 201 |
| `update_issue` | `PATCH ?id=` | Loads the issue, merges the changed fields, rebuilds the right subclass (the priority may have changed), `validate()`, saves, returns it with `message` and 200 |
| `delete_issue` | `DELETE ?id=` | Deletes and returns 200, or 404 if missing |

Helpers at the top of the file:

| Helper | Purpose |
|---|---|
| `error_response(message, status)` | Builds `{"error": message}` with the given status code |
| `method_not_allowed(request)` | 405 response with an `Allow: GET, POST, PATCH, DELETE` header |
| `parse_json_body(request)` | Turns `request.body` into a dict, or raises `ValueError` |
| `check_required_fields(data, fields)` | POST: raises `ValueError` listing any missing fields |
| `check_update_fields(data, fields)` | PATCH: rejects an empty body and fields that can't be changed (`id`, `created_at`) |
| `parse_id_param(value)` / `get_required_id(request)` | Read `?id=` as an `int`. PATCH and DELETE require it. |
| `build_issue(fields)` | Returns the `Issue` subclass that matches `fields['priority']` |
| `issue_response(issue, status)` | `issue.to_dict()` plus `"message": issue.describe()` |

Key Django pieces used:

- **`request.method`**: `'GET'`, `'POST'`, `'PATCH'`, `'DELETE'`, …
- **`request.GET.get('id')`**: reads query parameters from the URL (`?id=1` → `'1'`, a string, so it's converted with `int()`). This works for every method, not just GET.
- **`request.body`**: the raw request body, where the JSON sent from Postman is.
- **`JsonResponse(data, status=...)`**: turns a dict into a JSON HTTP response. For a list you need `safe=False`.
- **`@csrf_exempt`**: Django normally blocks POST/PATCH/DELETE requests without a CSRF token (a browser-form protection). API clients like Postman don't send one, so the API views are exempt.

### `issues/urls.py`: the app's routes

**What we write here:** the endpoints (URL paths), each linked to the view function that handles it.

```python
urlpatterns = [
    path('reporters/', views.reporters, name='reporters'),
    path('issues/', views.issues, name='issues'),
]
```

Combined with `path('api/', include('issues.urls'))` in `devtrack/urls.py`, this gives the final URLs `/api/reporters/` and `/api/issues/`.

Query parameters (`?id=1`, `?status=open`) and HTTP methods are **not** part of the route. Django matches only the path, and the view reads the method and parameters. That's why one route handles create, list, get-one, filter, update and delete.

### `issues/tests.py`: automated tests

**What we write here:** tests that call the API with Django's test client and check the responses. Run them with `python manage.py test`. There are 67 tests:

- **`ModelTests`**: the OOP rules (`BaseEntity` can't be created, `validate()` errors, `describe()` overrides, `to_dict()`)
- **`ReporterApiTestsMixin`** and **`IssueApiTestsMixin`**: every endpoint's success and failure cases (200/201/400/404/405/409), including the brief's exact sample response
- These API tests run **twice** through four classes:
  - `JsonReporterApiTests` / `JsonIssueApiTests`: JSON backend in a temporary folder. They're `SimpleTestCase`s, which fail on any database query, which proves JSON mode never touches the database.
  - `DatabaseReporterApiTests` / `DatabaseIssueApiTests`: database backend. Django creates a separate `test_devtrack` database, runs the tests, and drops it, so your real data is safe. `reset_sequences = True` restarts ids at 1 for each test.

PostgreSQL must be running for the database tests. With `STORAGE_BACKEND=json` they're skipped.

### `issues/apps.py`

The app's configuration class (`IssuesConfig`, `name = 'issues'`). Django uses it when the app is listed in `INSTALLED_APPS`.

### `issues/__init__.py` and `issues/migrations/__init__.py`

Empty files that mark these folders as Python packages.

---

## 5. `docs/`

| File | What it is |
|---|---|
| `docs/DevTrack.postman_collection.json` | Every API request, ready to import into Postman (**Import** → select the file). The `base_url` variable is set to `http://127.0.0.1:8000`. |
| `docs/screenshots/` | Postman screenshots shown in the README |

---

## 6. Checklists

**Adding a new endpoint**, e.g. `GET /api/issues/count/`:

1. **`issues/views.py`**: write the function, e.g. `def issue_count(request): ...` returning a `JsonResponse`.
2. **`issues/urls.py`**: add `path('issues/count/', views.issue_count, name='issue-count')`.
3. **`issues/tests.py`**: add a test that calls the URL and checks the response.
4. **`README.md`**: document the endpoint.

**Adding a new field**, e.g. `assignee` on issues:

1. **`issues/models.py`**: add it to `Issue.__init__` (and to `validate()` if it has rules).
2. **`issues/db_models.py`**: add the column to `IssueModel` and to its `to_dict()`.
3. Run **`python manage.py makemigrations`** then **`python manage.py migrate`**.
4. **`issues/views.py`**: add it to `ISSUE_FIELDS` so POST requires it and PATCH accepts it.
5. Update the tests and the README.
