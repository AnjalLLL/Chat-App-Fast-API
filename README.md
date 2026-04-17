# Web Socket Testing

## Run the server

Set your Neon database connection string in `DATABASE_URL` or `NEON_DATABASE_URL` before starting.

Example:

```powershell
$env:DATABASE_URL = "postgresql://<user>:<password>@<host>:<port>/<database>"
python -m uvicorn app.main:app --reload
```

The app automatically converts `postgres://` or `postgresql://` into the async `postgresql+asyncpg://` URL format.

This works because `app/main.py` re-exports the actual server app from `Server/app/main.py`.

