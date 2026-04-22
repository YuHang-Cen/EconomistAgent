# Frontend

The frontend is a Vite + React app that talks to the backend API.

## Local development (without Docker)

1. Install dependencies:
   ```bash
   npm install
   ```
2. Create env file:
   ```bash
   cp .env.example .env
   ```
3. Start:
   ```bash
   npm run dev
   ```

By default the app calls `http://127.0.0.1:8000/api`.
