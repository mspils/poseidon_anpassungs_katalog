Code and data for the collection of climate adaption measures from the Poseidon project.

This is a very early version, text still contain errors.
TODO:
-# HTTPS=True   <- leave commented until certbot is done (Phase 2) in .env
- Ip adresse aus allowed hosts nehmen


To run locally:
- Clone repo
- Install uv if not installed
- run `uv sync`
- run `uv run python manage.py runserver`

For production deployment (Ubuntu VM with nginx + gunicorn), see
[deploy/README.md](deploy/README.md).

Some technical notes:

Re-running translations after edits: whenever you add/change a {% trans %} string, run
```
uv run python manage.py makemessages -l da -l de -l en --ignore=.venv
```
, fill the new msgstr, then compilemessages


Due to licencing restriction the intended font file ABCDiatypeRounded-Regular.woff2 is not in this repository.
