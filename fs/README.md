# deploy-utils/fs

Tiny file management REST API and single-page Web portal built with Flask and SQLAlchemy.

## Quick start (Docker Compose)

1. Copy `.env.example` to `.env` and set the target directory (`HOST_DIR`) and the user/group IDs (`UID`, `GID`) that have permission to read/write it:

   ```sh
   cp .env.example .env
   # e.g. run as current user:
   # UID=$(id -u) GID=$(id -g) HOST_DIR=/srv/statements docker compose up -d --build
   docker compose up -d --build
   ```

2. Create a user and (optionally) mint an API token using `run-auth.sh`:

   ```sh
   ./run-auth.sh create-user alice
   ./run-auth.sh issue-token statements-bot alice --days 90
   ```

3. Open `http://localhost:8004` in your browser or call the API with `X-Api-Key`.

## REST API

All `/api/fs*` endpoints accept either the `session` cookie (from `POST /api/login`) or the `X-Api-Key` header.

- **`GET /api/fs?path=<rel_path>`** — list directory contents (`name`, `path`, `type`, `size`, `mtime`).
- **`GET /api/fs/download?path=<rel_path>`** — download a file.
- **`POST /api/fs/upload`** — multipart upload:
  ```sh
  curl -X POST http://localhost:8004/api/fs/upload \
    -H "X-Api-Key: <token>" \
    -F path=raw/santander -F mkdir=1 -F overwrite=1 -F file=@2026-01.pdf
  ```
- **`POST /api/fs/rename`** — rename or move an entry:
  ```sh
  curl -X POST http://localhost:8004/api/fs/rename \
    -H "X-Api-Key: <token>" -H "Content-Type: application/json" \
    -d '{"path": "raw/santander/2026-01.pdf", "new_name": "2026-02.pdf"}'
  ```
- **`POST /api/fs/mkdir`** — create a directory (`{"path": "raw/new_source"}`).
- **`DELETE /api/fs?path=<rel_path>`** — delete a file or directory tree.
