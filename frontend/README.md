# Frontend

The frontend is a Vite + React app that talks to the backend API.

## Local development

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

By default the app calls `/api` (same-origin). Local Vite development and the static deployment server both proxy `/api` to the backend service.

For one-command personal and deployment startup, see the root project [README](../README.md).
