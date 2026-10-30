# Mayl frontend

React 19 + Vite app for Mayl. See the [main README](../README.md) for what it does and how to run
the whole project.

```bash
npm install
npm run dev      # http://localhost:5173, talks to the API on http://localhost:8000
npm run build    # production build in dist/
npm run lint     # oxlint
```

Set `VITE_API_URL` (see `.env.example`) to point at another API.
