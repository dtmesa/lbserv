/**
 * API boundary: configures the generated client and normalizes every failure into an
 * RFC 9457 ProblemDetails, so components only ever deal with one (generated) error type.
 */
import * as Sentry from '@sentry/react';
import { ZodError } from 'zod';

import { client } from './generated/client.gen';
import type { ProblemDetails, ProblemError } from './generated/types.gen';
import { zProblemDetails } from './generated/zod.gen';

const PROBLEM_BASE = 'https://lbserv.dev/problems/';

client.setConfig({ baseUrl: import.meta.env.VITE_API_BASE_URL ?? '' });

function zodIssuesToErrors(error: ZodError): ProblemError[] {
  // Request validators check { body, path, query }; map issue paths onto RFC 9457 locations.
  return error.issues.map((issue) => {
    const [source, ...rest] = issue.path.map(String);
    if (source === 'body') {
      return { detail: issue.message, pointer: `#/${rest.join('/')}` };
    }
    return { detail: issue.message, parameter: rest[0] ?? source ?? '' };
  });
}

function clientProblem(status: number, code: string, title: string, detail?: string): ProblemDetails {
  return { type: `${PROBLEM_BASE}${code}`, title, status, code, detail: detail ?? null };
}

export function toProblem(error: unknown, response?: Response): ProblemDetails {
  const parsed = zProblemDetails.safeParse(error);
  if (parsed.success) {
    return parsed.data;
  }

  if (error instanceof ZodError) {
    if (!response) {
      return {
        ...clientProblem(422, 'validation-failed', 'Validation failed'),
        errors: zodIssuesToErrors(error),
      };
    }
    // The server answered with something that doesn't match the OpenAPI contract.
    Sentry.captureException(error, { tags: { kind: 'contract-violation' } });
    return clientProblem(502, 'invalid-response', 'Unexpected response from server');
  }

  if (error instanceof TypeError) {
    return clientProblem(503, 'network-error', 'Network error', error.message);
  }

  if (response && response.status >= 400) {
    return {
      type: 'about:blank',
      title: response.statusText || 'Request failed',
      status: response.status,
      detail: typeof error === 'string' && error ? error : null,
    };
  }

  Sentry.captureException(error);
  return clientProblem(500, 'unknown-error', 'Something went wrong');
}

client.interceptors.error.use((error, response) => {
  if (error instanceof DOMException && error.name === 'AbortError') {
    return error; // let TanStack Query handle cancellation
  }
  return toProblem(error, response);
});

/** Map `#/field` pointers from a problem onto form field names. */
export function problemFieldErrors(problem: ProblemDetails): Map<string, string> {
  const fields = new Map<string, string>();
  for (const err of problem.errors ?? []) {
    const name = err.pointer?.replace(/^#\//, '');
    if (name && !fields.has(name)) {
      fields.set(name, err.detail);
    }
  }
  return fields;
}

export { client };
