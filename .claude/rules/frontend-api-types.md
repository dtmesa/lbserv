---
paths:
  - "frontend/**"
---

# Frontend: generated API types only

- Import every API type, schema, SDK function, and query/mutation option from
  `frontend/src/api/generated/`. Do not declare interfaces/types/zod schemas that mirror API
  shapes, do not call `fetch`/`EventSource` directly, and do not use `as` casts on API data.
- Do not edit files under `frontend/src/api/generated/`. If the shape you need is missing or wrong,
  change `backend/app/schemas.py`, then run `make openapi gen`.
- Component props types are fine; name them `<Component>Props` and use camelCase keys.
- Errors reaching components are `ProblemDetails` (RFC 9457). Render them with `ProblemAlert` and
  map field errors with `problemFieldErrors()` from `src/api/client.ts`.
- Before finishing: `npm run lint && npm run typecheck && npm test` in `frontend/`.
