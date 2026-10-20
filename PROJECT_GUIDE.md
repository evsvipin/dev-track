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
  │   └── issues/storage.py    reads data/issues.json and data/reporters.json, writes data/issues.json
  ▼
JsonResponse                   { ..., "message": "[URGENT] ..." }   status 201
  ▼
Postman shows the response
```

Each file has one job:

| Layer | File | Job |
|---|---|---|
| Configuration | `devtrack/settings.py` | How Django is set up |
| Routing | `devtrack/urls.py`, `issues/urls.py` | Which URL goes to which function |
| Request handling | `issues/views.py` | Read the request, decide the response |
| Business rules | `issues/models.py` | What a Reporter/Issue is and what makes one valid |
| Storage | `issues/storage.py` | Reading and writing the JSON files |
| Data | `data/*.json` | The saved records |

---

## 2. Root folder

### `manage.py`

Django's command-line tool for this project. You don't edit it. It sets `DJANGO_SETTINGS_MODULE` to `devtrack.settings` so Django knows which settings to load, and then runs the command you give it:

| Command | What it does |
|---|---|
| `python manage.py runserver` | Starts the development server at http://127.0.0.1:8000 |
| `python manage.py test` | Runs the tests in `issues/tests.py` |
| `python manage.py check` | Checks the project for configuration errors |

### `requirements.txt`

The list of Python packages the project needs, with exact versions, so everyone installs the same thing with `pip install -r requirements.txt`.

| Package | Why it is needed |
|---|---|
| `Django` | The web framework |
| `asgiref`, `sqlparse`, `tzdata` | Packages Django itself depends on (`tzdata` provides time zone data on Windows) |
| `python-dotenv` | Loads settings from the optional `.env` file |

### `.env.example` and `.env`

`.env` holds settings that may differ per machine or should stay secret (the secret key, the debug flag, allowed hosts). It is listed in `.gitignore`, so it never gets pushed. `.env.example` is the template that is pushed so others know which variables exist. The project runs without a `.env` file by using development defaults.

### `.gitignore`

Tells Git which files to keep only on your machine: the virtual environment (`.venv/`), Python cache files (`__pycache__/`), `.env`, local databases and editor settings.

### `data/reporters.json` and `data/issues.json`

The "database". Each file is a JSON list of records, and they start empty (`[]`). The POST endpoints append to them and the GET endpoints read from them. Example contents of `issues.json` after one POST:

```json
[
    {
        "id": 1,
        "title": "Login button not working on mobile",
        "description": "Users on iOS 17 cannot tap the login button",
        "status": "open",
        "priority": "critical",
        "reporter_id": 1,
        "created_at": "2026-10-20 17:53:51.216222"
    }
]
```

`reporter_id` is what links an issue to its reporter (the one-to-many relationship).

---

## 3. `devtrack/`: the Django project

This folder is the **project**. It holds configuration that applies to the whole site. It was created by `django-admin startproject`.

### `devtrack/settings.py`

The configuration for the whole project. The important parts:

| Setting | Value | Meaning |
|---|---|---|
| `SECRET_KEY` | from `.env`, or a dev default | Used by Django for signing. Must be secret in production. |
| `DEBUG` | `True` by default | Shows detailed error pages. Turn off in production. |
| `ALLOWED_HOSTS` | `localhost`, `127.0.0.1` | Host names the server will answer to |
| `INSTALLED_APPS` | `['issues']` | **Registers the `issues` app** so Django knows it exists |
| `MIDDLEWARE` | security, common, CSRF, clickjacking | Code that runs on every request and response |
| `ROOT_URLCONF` | `'devtrack.urls'` | The first URL file Django looks at |
| `DATABASES` | `{}` | No database: data lives in JSON files |
| `DATA_DIR` | `BASE_DIR / 'data'` | **Custom setting**: the folder where the JSON files are kept |

Django's built-in admin, auth and sessions apps are not installed, because they need a database and this project doesn't use one.

### `devtrack/urls.py`

The **root URL file**. Django checks every incoming URL against `urlpatterns` here first.

```python
urlpatterns = [
    path('api/', include('issues.urls')),
]
```

This means: "any URL starting with `api/` belongs to the issues app. Remove the `api/` part and look up the rest in `issues/urls.py`." This is how the app's URLs get **wired into the project**.

### `devtrack/wsgi.py` and `devtrack/asgi.py`

Entry points used by production web servers (WSGI for servers like Gunicorn, ASGI for async servers like Uvicorn). They load `devtrack.settings` and expose the application. `runserver` uses WSGI. You don't need to edit them.

### `devtrack/__init__.py`

An empty file that marks `devtrack/` as a Python package so it can be imported (for example `devtrack.settings`).

---

## 4. `issues/`: the Django app

This folder is an **app**: a self-contained feature of the project. It was created by `python manage.py startapp`. Everything about reporters and issues lives here.

### `issues/models.py`: the OOP classes

**What we write here:** the classes that describe our data and its rules. In a typical Django project this file holds database models (`models.Model`). Here it holds **plain Python classes**, because the data is stored in JSON files.

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
| `BaseEntity` | Abstract parent class. Declares `validate()` and provides `to_dict()`. | **Abstraction**: `ABC` + `@abstractmethod` mean `BaseEntity()` cannot be created, and every subclass must write its own `validate()` |
| `BaseEntity.to_dict()` | Returns `self.__dict__` as a plain dict (all the object's attributes) | **Inheritance**: written once, used by every subclass |
| `Reporter` | Stores `id`, `name`, `email`, `team`. `validate()` checks the name and team aren't empty and the email has `@`. | Inherits from `BaseEntity` |
| `Issue` | Stores `id`, `title`, `description`, `status`, `priority`, `reporter_id`, `created_at`. `validate()` checks the title isn't empty and status/priority are allowed values. `describe()` returns `"<title> [<priority>]"`. | Inherits from `BaseEntity` |
| `CriticalIssue` | Overrides `describe()` → `"[URGENT] <title> — needs immediate attention"` | **Method overriding / polymorphism** |
| `LowPriorityIssue` | Overrides `describe()` → `"<title> — low priority, handle when free"` | **Method overriding / polymorphism** |
| `validate_positive_int()`, `validate_non_empty_string()` | Small helpers so `validate()` methods don't repeat the same checks | Reuse |

`validate()` signals a problem by **raising `ValueError`** with a readable message. The view catches it and returns it as a 400 error. So the message in `{"error": "Title cannot be empty"}` comes straight from `Issue.validate()`.

### `issues/views.py`: the endpoint logic

**What we write here:** the functions that receive a request and return a response. A view's job is to read the request, use the models and storage, and build a `JsonResponse`.

Each URL has one **dispatcher** view that checks `request.method` and calls the right helper:

| Function | Called for | What it does |
|---|---|---|
| `reporters(request)` | `/api/reporters/` | GET → `get_reporters`, POST → `create_reporter`, anything else → 405 |
| `get_reporters(request)` | `GET /api/reporters/` and `?id=` | Reads `reporters.json`. Without `?id=` returns all. With `?id=` returns one, or 404. |
| `create_reporter(request)` | `POST /api/reporters/` | Parses the JSON body, builds a `Reporter`, calls `validate()`, checks the id is unused, saves `to_dict()`, returns 201 |
| `issues(request)` | `/api/issues/` | GET → `get_issues`, POST → `create_issue`, anything else → 405 |
| `get_issues(request)` | `GET /api/issues/`, `?id=`, `?status=` | Returns one issue by id (or 404), issues filtered by status, or all issues |
| `create_issue(request)` | `POST /api/issues/` | Chooses `CriticalIssue` / `LowPriorityIssue` / `Issue` from the priority, calls `validate()`, checks the reporter exists and the id is unused, saves `to_dict()`, returns it plus `"message": describe()` with 201 |

Helpers at the top of the file:

| Helper | Purpose |
|---|---|
| `error_response(message, status)` | Builds `{"error": message}` with the given status code |
| `method_not_allowed(...)` | 405 response with an `Allow: GET, POST` header |
| `parse_json_body(request)` | Turns `request.body` into a dict, or raises `ValueError` if it isn't valid JSON |
| `check_required_fields(data, fields)` | Raises `ValueError` listing any missing fields |
| `parse_id_param(value)` | Converts `?id=` to `int`, or raises `ValueError` |

Key Django pieces used:

- **`request.GET.get('id')`** reads query parameters from the URL (`?id=1` → `'1'`, a string, so it's converted with `int()`).
- **`request.body`** is the raw request body. The JSON sent from Postman is read from here.
- **`JsonResponse(data, status=...)`** turns a dict into a JSON HTTP response. For a list you need `safe=False`.
- **`@csrf_exempt`**: Django normally blocks POST requests that don't carry a CSRF token (a browser-form protection). API clients like Postman don't send one, so the API views are exempt.

### `issues/urls.py`: the app's routes

**What we write here:** the endpoints (URL paths), each linked to the view function that handles it.

```python
urlpatterns = [
    path('reporters/', views.reporters, name='reporters'),
    path('issues/', views.issues, name='issues'),
]
```

Combined with `path('api/', include('issues.urls'))` in `devtrack/urls.py`, this gives the final URLs `/api/reporters/` and `/api/issues/`.

Query parameters (`?id=1`, `?status=open`) are **not** part of the route. Django matches only the path, and the view reads the parameters with `request.GET`. That's why one route handles "all", "by id" and "by status".

### `issues/storage.py`: JSON file helpers

**What we write here:** all reading and writing of the JSON files, so views never open files themselves.

| Function | What it does |
|---|---|
| `get_file_path(filename)` | Builds the full path, e.g. `data/issues.json`, from `settings.DATA_DIR` |
| `read_records(filename)` | Returns the list stored in the file, or `[]` if the file is missing or empty |
| `write_records(filename, records)` | Saves the list back to the file as formatted JSON |
| `find_by_id(records, record_id)` | Loops through the records and returns the one with a matching `id`, or `None` |
| `next_id(records)` | Highest existing id + 1, used when a POST doesn't include an `id` |

`REPORTERS_FILE` and `ISSUES_FILE` hold the two file names.

### `issues/tests.py`: automated tests

**What we write here:** tests that call the API with Django's test client and check the responses, so you can confirm everything works with one command (`python manage.py test`). They cover:

- the OOP rules: `BaseEntity` can't be created, `validate()` errors, the `describe()` overrides, `to_dict()`
- every endpoint's success case (200/201)
- the failure cases (400, 404, 405, 409)
- the exact sample response from the project brief

Each test points `DATA_DIR` at a temporary folder (`override_settings`), so running the tests never changes your real `data/*.json` files. The tests use `SimpleTestCase` because there is no database.

### `issues/apps.py`

The app's configuration class (`IssuesConfig`, `name = 'issues'`). Django uses it when the app is listed in `INSTALLED_APPS`.

### `issues/__init__.py` and `issues/migrations/__init__.py`

Empty files that mark these folders as Python packages. The `migrations/` folder is where Django puts database migration files. It stays empty here because nothing is stored in a database.

---

## 5. `docs/`

| File | What it is |
|---|---|
| `docs/DevTrack.postman_collection.json` | Every API request, ready to import into Postman (**Import** → select the file). The `base_url` variable is set to `http://127.0.0.1:8000`. |
| `docs/screenshots/` | Postman screenshots shown in the README |

---

## 6. Adding a new endpoint: the checklist

To add, for example, `GET /api/issues/count/`:

1. **`issues/views.py`**: write the function, e.g. `def issue_count(request): ...` returning a `JsonResponse`.
2. **`issues/urls.py`**: add `path('issues/count/', views.issue_count, name='issue-count')`.
3. **`issues/tests.py`**: add a test that calls the URL and checks the response.
4. **`README.md`**: document the new endpoint.

`devtrack/urls.py` doesn't need to change, because everything under `api/` is already routed to the app.
