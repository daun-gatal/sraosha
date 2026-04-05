# Sraosha web UI

React + TypeScript + Vite + Tailwind v4. Uses Bun for installs.

- **Dev:** `bun run dev` — Vite proxies `/api` and `/openapi.json` to `http://127.0.0.1:8000`. Run the API with `sraosha serve --reload` in another shell.
- **Prod:** `bun run build` outputs `dist/`. The FastAPI app serves the SPA under `/app/` when `frontend/dist/index.html` exists.
- **Env:** copy `.env.example` to `.env` and set `VITE_API_BASE_URL` if the API is on another origin.

The app uses **client-side routing** with basename `/app` (see `vite.config.ts` `base`).
