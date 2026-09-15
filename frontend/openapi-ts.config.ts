import { defineConfig } from '@hey-api/openapi-ts';

// Source of truth: the Pydantic models in backend/app/schemas.py, exported by `make openapi`.
export default defineConfig({
  input: '../openapi/openapi.json',
  output: {
    path: 'src/api/generated',
    postProcess: [],
  },
  plugins: [
    '@hey-api/typescript',
    '@hey-api/client-fetch',
    'zod',
    {
      name: '@hey-api/sdk',
      validator: true, // validate requests and responses at runtime with the generated zod schemas
    },
    '@tanstack/react-query',
  ],
});
