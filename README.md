# semantic-photo

## Run With Docker

1. Ensure Docker and Docker Compose are installed.
2. Keep backend secrets in `backend/.env`.
3. Start everything:

```bash
docker compose up --build
```

4. Open:
- Frontend: `http://localhost:5173`
- Backend: `http://localhost:8000`
- Backend health: `http://localhost:8000/health`

5. Stop everything:

```bash
docker compose down
```
