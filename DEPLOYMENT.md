# Deployment Guide

This project is dev-ready out of the box (zero env vars needed to run
`manage.py runserver` locally). Going to production requires a few
manual steps that can't be baked into defaults, because dev and prod
need genuinely different values.

## 1. Required environment variables

Set these on the actual server/host (not in a committed file):

| Variable | Required | Purpose |
|---|---|---|
| `DJANGO_DEBUG` | **Yes** — set to `False` | Dev default is `True`; leaving it `True` in production exposes stack traces, settings, and query data to visitors. |
| `DJANGO_SECRET_KEY` | **Yes** | App refuses to start without one when `DJANGO_DEBUG=False`. Generate with `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`. |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT` | **Yes** | Dev defaults (including a `123456` password) must never be reachable in production. |
| `DJANGO_ALLOWED_HOSTS` | Yes | Comma-separated list of the real domain(s)/IP(s) serving the site. |
| `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | Yes, for email to work | Currently placeholder values — password reset emails and notification emails will fail (silently, logged) until real SMTP credentials are set. A Gmail "App Password" works with the current `smtp.gmail.com` config. |
| `DJANGO_MEDIA_ROOT` | Recommended | Points student/staff photo storage at a **persistent** volume — see §4. |
| `DJANGO_SESSION_COOKIE_SECURE`, `DJANGO_CSRF_COOKIE_SECURE` | Auto | Already default to `True` whenever `DJANGO_DEBUG=False`. |

## 2. Running the app

Don't use `manage.py runserver` in production — it's single-threaded
and not hardened for real traffic. Use the included waitress-based
entry point instead:

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
python run_production.py
```

Tune with `DJANGO_SERVE_HOST`, `DJANGO_SERVE_PORT`, `DJANGO_SERVE_THREADS`
env vars. Put a reverse proxy (nginx/IIS) in front of it for TLS
termination and to serve `/media/` directly (see §4).

If you'd rather run on Linux behind gunicorn+nginx instead of
waitress, that works too — `gunicorn config.wsgi:application` is a
drop-in alternative; just add `gunicorn` to `requirements.txt`.

**Whenever you add or change a static file** (CSS/JS/images under any
app's `static/` folder), re-run `collectstatic` — the static storage
backend (whitenoise, manifest-hashed) won't serve a file it doesn't
know about, and `{% static %}` tags will raise instead of silently
falling back.

## 3. Database backups

```bash
python manage.py backup_database            # writes to backups/, keeps last 14
python manage.py backup_database --keep 30  # keep more history
```

Requires the PostgreSQL client tools (`pg_dump`) on PATH — same major
version as the server. Restore with:

```bash
pg_restore -h <host> -U <user> -d <dbname> --clean backups/<file>.dump
```

Schedule it to run automatically:
- **Linux**: cron, e.g. `0 2 * * * cd /path/to/app && venv/bin/python manage.py backup_database`
- **Windows**: Task Scheduler running the same command daily.

Back up the `backups/` output itself off-server too (e.g. sync to
cloud storage) — a nightly dump sitting on the same disk as the
database doesn't protect against disk/server loss.

## 4. Media files (student/staff photos)

Two things to get right before real students are enrolled with photos:

1. **Persistence**: set `DJANGO_MEDIA_ROOT` to a path on a persistent,
   backed-up volume. Most hosting platforms (containers, PaaS) wipe
   local disk on redeploy — losing this silently deletes every photo.
2. **Serving**: `config/urls.py` only serves `/media/` when
   `DEBUG=True`. In production, your reverse proxy (nginx, IIS, etc.)
   must serve `/media/` directly from `MEDIA_ROOT`, or nothing will
   return uploaded photos at all.

If a persistent local volume isn't available (common on PaaS), switch
to object storage (e.g. S3-compatible) via `django-storages` instead —
that requires provider credentials this deployment guide can't supply
for you.

## 5. First deploy checklist

- [ ] All env vars from §1 set
- [ ] `python manage.py migrate` run
- [ ] `python manage.py collectstatic --noinput` run
- [ ] `python manage.py createsuperuser` run (or a superuser already exists)
- [ ] `DJANGO_MEDIA_ROOT` points at a persistent volume
- [ ] Reverse proxy configured for TLS + `/media/` + (optionally) `/static/`
- [ ] `python manage.py backup_database` scheduled
- [ ] `python manage.py check --deploy` run with production env vars and shows no warnings
