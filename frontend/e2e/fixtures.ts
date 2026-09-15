import { type APIRequestContext, test as base, expect } from '@playwright/test';

import {
  zGame,
  zLeaderboard,
  zProblemDetails,
  zScoreSubmissionResult,
} from '../src/api/generated/zod.gen';
import { E2E_API_KEY } from '../playwright.config';

/** Thin helpers over the real API. Responses are validated with the generated zod schemas. */
export class Api {
  constructor(private readonly request: APIRequestContext) {}

  async createGame(id: string, name = id) {
    const res = await this.request.post('/api/v1/games', {
      data: { id, name },
      headers: { 'X-API-Key': E2E_API_KEY },
    });
    expect(res.status(), await res.text()).toBe(201);
    return zGame.parse(await res.json());
  }

  async submitScore(gameId: string, userId: string, score: number) {
    const res = await this.request.post(`/api/v1/games/${gameId}/scores`, {
      data: { user_id: userId, score },
      headers: { 'X-API-Key': E2E_API_KEY },
    });
    expect(res.status(), await res.text()).toBe(200);
    return zScoreSubmissionResult.parse(await res.json());
  }

  async leaderboard(gameId: string, limit = 10) {
    const res = await this.request.get(`/api/v1/games/${gameId}/leaderboard`, { params: { limit } });
    expect(res.ok()).toBe(true);
    return zLeaderboard.parse(await res.json());
  }

  async problem(response: Awaited<ReturnType<APIRequestContext['get']>>) {
    expect(response.headers()['content-type']).toBe('application/problem+json');
    return zProblemDetails.parse(await response.json());
  }
}

export const test = base.extend<{ api: Api; gameId: string }>({
  api: async ({ request }, use) => {
    await use(new Api(request));
  },
  // A fresh game per test keeps tests independent when running in parallel.
  gameId: async ({ api }, use, testInfo) => {
    const id = `e2e-${testInfo.workerIndex.toString()}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`;
    await api.createGame(id, `E2E ${id}`);
    await use(id);
  },
});

export { E2E_API_KEY, expect };
