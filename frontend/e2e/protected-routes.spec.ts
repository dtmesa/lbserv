import { E2E_API_KEY, expect, test } from './fixtures';

/*
 * Protected (write) routes require X-API-Key. These tests cover both the HTTP contract and the
 * UI behaviour for missing, wrong, and valid keys.
 */

test.describe('API: protected write routes', () => {
  test('POST /games rejects a missing key with an RFC 9457 401', async ({ api, request }) => {
    const res = await request.post('/api/v1/games', { data: { id: 'nokey', name: 'No key' } });
    expect(res.status()).toBe(401);
    expect(res.headers()['www-authenticate']).toBe('ApiKey');
    const problem = await api.problem(res);
    expect(problem).toMatchObject({ status: 401, code: 'invalid-api-key', instance: '/api/v1/games' });
  });

  test('POST /scores rejects a wrong key and does not change the leaderboard', async ({
    api,
    request,
    gameId,
  }) => {
    const res = await request.post(`/api/v1/games/${gameId}/scores`, {
      data: { user_id: 'mallory', score: 999 },
      headers: { 'X-API-Key': 'wrong-key' },
    });
    expect(res.status()).toBe(401);
    expect((await api.problem(res)).code).toBe('invalid-api-key');
    expect((await api.leaderboard(gameId)).total_players).toBe(0);
  });

  test('read routes stay public', async ({ request, gameId }) => {
    for (const path of [
      '/api/v1/games',
      `/api/v1/games/${gameId}/leaderboard`,
    ]) {
      const res = await request.get(path);
      expect(res.status(), path).toBe(200);
    }
  });
});

test.describe('UI: admin panel writes', () => {
  test('submitting without an API key shows the problem and writes nothing', async ({
    page,
    api,
    gameId,
  }) => {
    await page.goto(`/?game=${gameId}`);
    await page.getByLabel('User ID').nth(1).fill('alice');
    await page.getByLabel('Score').fill('100');
    await page.getByRole('button', { name: 'Submit' }).click();

    const alert = page.getByRole('alert').filter({ hasText: 'Invalid API key' });
    await expect(alert).toBeVisible();
    await expect(alert).toContainText('A valid X-API-Key header is required.');
    expect((await api.leaderboard(gameId)).total_players).toBe(0);
  });

  test('a wrong API key is rejected', async ({ page, gameId }) => {
    await page.goto(`/?game=${gameId}`);
    await page.getByLabel('API key').fill('definitely-wrong');
    await page.getByLabel('User ID').nth(1).fill('alice');
    await page.getByLabel('Score').fill('100');
    await page.getByRole('button', { name: 'Submit' }).click();
    await expect(page.getByRole('alert').filter({ hasText: 'Invalid API key' })).toBeVisible();
  });

  test('with a valid key: create a game, submit scores, keep best score', async ({ page, api }) => {
    const id = `e2e-ui-${Date.now().toString(36)}`;
    await page.goto('/');
    await page.getByLabel('API key').fill(E2E_API_KEY);

    await page.getByLabel('Slug').fill(id);
    await page.getByLabel('Name').fill(`UI ${id}`);
    await page.getByRole('button', { name: 'Create' }).click();

    // The new game becomes the selection and is deep-linkable.
    await expect(page).toHaveURL(new RegExp(`[?&]game=${id}`));
    await expect(page.getByLabel('Game')).toHaveValue(id);

    const submit = async (user: string, score: number) => {
      await page.getByLabel('User ID').nth(1).fill(user);
      await page.getByLabel('Score').fill(String(score));
      await page.getByRole('button', { name: 'Submit' }).click();
    };

    await submit('alice', 300);
    await expect(page.getByRole('status')).toContainText('New best! alice is #1 with 300.');
    await submit('bob', 500);
    await expect(page.getByRole('status')).toContainText('bob is #1 with 500.');
    await submit('alice', 100);
    await expect(page.getByRole('status')).toContainText('Not a personal best. alice is #2 with 300.');

    const top = page.locator('section', { has: page.getByRole('heading', { name: 'Top 10' }) });
    await expect(top.getByRole('row')).toHaveCount(3);
    await expect(top.getByRole('row').nth(1)).toContainText('bob');
    await expect(top.getByRole('row').nth(2)).toContainText('alice');

    const board = await api.leaderboard(id);
    expect(board.entries.map((e) => [e.user_id, e.score])).toEqual([
      ['bob', 500],
      ['alice', 300],
    ]);
  });

  test('generated zod schema blocks invalid input before any request', async ({ page, gameId }) => {
    const scoreRequests: string[] = [];
    page.on('request', (req) => {
      if (req.url().includes('/scores')) scoreRequests.push(req.url());
    });

    await page.goto(`/?game=${gameId}`);
    await page.getByLabel('API key').fill(E2E_API_KEY);
    await page.getByLabel('User ID').nth(1).fill('not valid!');
    await page.getByLabel('Score').fill('-5');
    await page.getByRole('button', { name: 'Submit' }).click();

    await expect(page.getByText(/Invalid string: must match pattern/)).toBeVisible();
    await expect(page.getByText(/Too small: expected number to be >=0/)).toBeVisible();
    expect(scoreRequests).toEqual([]);
  });

  test('server conflicts surface as problem details', async ({ page, gameId }) => {
    await page.goto(`/?game=${gameId}`);
    await page.getByLabel('API key').fill(E2E_API_KEY);
    await page.getByLabel('Slug').fill(gameId);
    await page.getByLabel('Name').fill('Duplicate');
    await page.getByRole('button', { name: 'Create' }).click();

    const alert = page.getByRole('alert').filter({ hasText: 'Game already exists' });
    await expect(alert).toBeVisible();
    await expect(alert).toContainText(`A game with id '${gameId}' already exists.`);
  });
});
