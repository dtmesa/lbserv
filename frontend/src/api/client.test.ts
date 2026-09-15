import { describe, expect, it } from 'vitest';
import { ZodError } from 'zod';

import { problemFieldErrors, toProblem } from './client';
import { zScoreSubmission } from './generated/zod.gen';

describe('toProblem', () => {
  it('passes through RFC 9457 problem bodies from the server', () => {
    const body = {
      type: 'https://lbserv.dev/problems/game-not-found',
      title: 'Game not found',
      status: 404,
      detail: "No game with id 'x'.",
      instance: '/api/v1/games/x/leaderboard',
      code: 'game-not-found',
    };
    expect(toProblem(body, new Response(null, { status: 404 }))).toMatchObject(body);
  });

  it('turns client-side request validation into a 422 problem with pointers', () => {
    const result = zScoreSubmission.safeParse({ user_id: 'bad id', score: -1 });
    if (result.success) throw new Error('expected failure');
    // The SDK validates { body, path, query }, so issue paths are prefixed with the source.
    const zodError = new ZodError(
      result.error.issues.map((issue) => ({ ...issue, path: ['body', ...issue.path] })),
    );

    const problem = toProblem(zodError);
    expect(problem.status).toBe(422);
    expect([...problemFieldErrors(problem).keys()].sort()).toEqual(['score', 'user_id']);
  });

  it('flags responses that break the contract', () => {
    const result = zScoreSubmission.safeParse({});
    if (result.success) throw new Error('expected failure');
    expect(toProblem(result.error, new Response('{}', { status: 200 })).code).toBe('invalid-response');
  });

  it('maps network failures', () => {
    expect(toProblem(new TypeError('Failed to fetch')).code).toBe('network-error');
  });
});
