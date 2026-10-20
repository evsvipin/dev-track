"""
Django settings for the DevTrack project.

DevTrack stores its data in JSON files (see DATA_DIR below), so no database
is configured and none of Django's database-backed apps (admin, auth,
sessions) are installed.

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


# Database
# Not used: records are stored in JSON files instead.

DATABASES = {}


# JSON file storage
# reporters.json and issues.json live in this folder.

DATA_DIR = BASE_DIR / 'data'


# Internationalization
# https://docs.djangoproject.com/en/6.1/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True
