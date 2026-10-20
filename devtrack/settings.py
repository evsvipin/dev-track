"""
Django settings for the DevTrack project.

DevTrack can store its data in two ways, chosen by STORAGE_BACKEND:
  - 'database' (default): PostgreSQL running in Docker (see docker-compose.yaml)
  - 'json':               the files data/reporters.json and data/issues.json

https://docs.djangoproject.com/en/6.1/ref/settings/
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Values in .env (if present) become environment variables.
load_dotenv(BASE_DIR / '.env')


# SECURITY WARNING: keep the secret key used in production secret!
# The fallback key is for local development only; set DJANGO_SECRET_KEY
# in .env for anything else.
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-local-dev-only-key')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DJANGO_DEBUG', 'True') == 'True'

ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')


# Application definition

INSTALLED_APPS = [
    'issues',  # DevTrack reporters and issues API
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'devtrack.urls'

WSGI_APPLICATION = 'devtrack.wsgi.application'


# Storage backend: 'database' or 'json' (see issues/storage.py)

STORAGE_BACKEND = os.environ.get('STORAGE_BACKEND', 'database')


# Database
# PostgreSQL in Docker. The defaults match docker-compose.yaml.
# https://docs.djangoproject.com/en/6.1/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('POSTGRES_DB', 'devtrack'),
        'USER': os.environ.get('POSTGRES_USER', 'postgres'),
        'PASSWORD': os.environ.get('POSTGRES_PASSWORD', 'admin'),
        'HOST': os.environ.get('POSTGRES_HOST', 'localhost'),
        'PORT': os.environ.get('POSTGRES_PORT', '5433'),
    }
}

# JSON mode needs no database, so it runs without Docker.
if STORAGE_BACKEND == 'json':
    DATABASES = {}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# JSON file storage
# reporters.json and issues.json live in this folder.

DATA_DIR = BASE_DIR / 'data'


# Internationalization
# https://docs.djangoproject.com/en/6.1/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

# Timestamps are plain local times, matching the brief's str(datetime.now()),
# so created_at looks the same whichever storage backend is used.
USE_TZ = False
