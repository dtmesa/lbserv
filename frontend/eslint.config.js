// @ts-check
import js from '@eslint/js';
import { defineConfig } from 'eslint/config';
import reactHooks from 'eslint-plugin-react-hooks';
import globals from 'globals';
import tseslint from 'typescript-eslint';

/*
 * RULE: no hand-written API types on the frontend.
 * Every request/response/error shape comes from src/api/generated, which is generated from the
 * OpenAPI document exported by the Pydantic backend (`make openapi gen`). See CLAUDE.md.
 */
const GENERATED_MSG =
  'Hand-written API types are forbidden. Import types/schemas from src/api/generated ' +
  '(regenerate with `make gen` after changing backend/app/schemas.py).';

// Type names that look like API contract shapes.
const API_TYPE_NAME =
  '/(Request|Response|Result|Problem|Error|Entry|Score|Submission|Leaderboard|Game|Event|Context|Health|Dto|Payload|Body|Params|Query)s?$/';

export default defineConfig(
  { ignores: ['dist', 'coverage', 'playwright-report', 'test-results', 'src/api/generated/**'] },

  {
    files: ['**/*.{ts,tsx,js}'],
    extends: [js.configs.recommended, tseslint.configs.strictTypeChecked],
    languageOptions: {
      parserOptions: { projectService: true, tsconfigRootDir: import.meta.dirname },
      globals: { ...globals.browser },
    },
  },

  {
    files: ['src/**/*.{ts,tsx}'],
    extends: [reactHooks.configs.flat['recommended-latest']],
  },

  {
    // The generated-types rule also applies to E2E tests.
    files: ['src/**/*.{ts,tsx}', 'e2e/**/*.ts'],
    rules: {
      // Never cast data into a shape; let the generated types/validators prove it.
      '@typescript-eslint/consistent-type-assertions': ['error', { assertionStyle: 'never' }],
      '@typescript-eslint/no-non-null-assertion': 'error',
      'no-restricted-syntax': [
        'error',
        { selector: `TSInterfaceDeclaration[id.name=${API_TYPE_NAME}]`, message: GENERATED_MSG },
        { selector: `TSTypeAliasDeclaration[id.name=${API_TYPE_NAME}]`, message: GENERATED_MSG },
        {
          // The API is snake_case and app code is camelCase: a snake_case property in a
          // hand-written type is a copy of a contract shape.
          selector: 'TSPropertySignature[key.name=/^[a-z][a-z0-9]*(_[a-z0-9]+)+$/]',
          message: GENERATED_MSG,
        },
        {
          selector: "CallExpression[callee.name='fetch']",
          message: 'Use the generated SDK / TanStack Query options instead of fetch().',
        },
        {
          selector: "NewExpression[callee.name='EventSource']",
          message: 'Use the generated streamLeaderboardEvents() SSE client.',
        },
      ],
      'no-restricted-properties': [
        'error',
        { object: 'window', property: 'fetch', message: 'Use the generated SDK.' },
        { object: 'globalThis', property: 'fetch', message: 'Use the generated SDK.' },
      ],
      'no-restricted-imports': [
        'error',
        {
          paths: [
            { name: 'axios', message: 'Use the generated SDK.' },
            { name: 'ky', message: 'Use the generated SDK.' },
            { name: 'zod', message: 'Use schemas from src/api/generated/zod.gen.' },
            { name: 'zod/v4', message: 'Use schemas from src/api/generated/zod.gen.' },
          ],
          patterns: [
            {
              group: ['**/generated/client', '**/generated/client/*', '**/generated/core/*'],
              message: 'Import from generated sdk.gen / types.gen / zod.gen / @tanstack entry points.',
            },
          ],
        },
      ],
    },
  },

  {
    // The API boundary may inspect raw zod errors when normalizing failures into problems.
    files: ['src/api/*.ts'],
    rules: { 'no-restricted-imports': 'off' },
  },

  {
    files: ['*.config.{ts,js}'],
    languageOptions: { globals: { ...globals.node } },
  },
);
