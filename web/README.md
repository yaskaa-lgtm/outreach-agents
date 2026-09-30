# outreach-agents — web app

Next.js (App Router) + TypeScript + Tailwind CSS + shadcn/ui.

```bash
npm install          # once
npm run dev          # http://localhost:3000 (expects the API on http://localhost:8000)
npm run lint         # ESLint
npm run typecheck    # TypeScript
npm run format       # Prettier
npm run build        # production build (standalone output, used by the Docker image)
```

Server components call the API through `API_INTERNAL_URL` (default `http://127.0.0.1:8000`,
`http://api:8000` inside docker compose). See the root [README](../README.md).
