import { expect, test } from './fixtures';

test.describe('public leaderboard views', () => {
  test('top X toggles between 10 and 100 users', async ({ page, api, gameId }) => {
    for (let i = 1; i <= 12; i++) {
      await api.submitScore(gameId, `player_${String(i).padStart(2, '0')}`, i * 10);
    }
    await page.goto(`/?game=${gameId}`);

    const top10 = page.locator('section', { has: page.getByRole('heading', { name: 'Top 10' }) });
    await expect(top10.getByText('12 players')).toBeVisible();
    await expect(top10.getByRole('row')).toHaveCount(11); // header + 10
    await expect(top10.getByRole('row').nth(1)).toContainText('player_12');

    await page.getByRole('button', { name: '100', exact: true }).click();
    const top100 = page.locator('section', { has: page.getByRole('heading', { name: 'Top 100' }) });
    await expect(top100.getByRole('row')).toHaveCount(13);
    await expect(top100.getByRole('row').last()).toContainText('player_01');
  });

  test('user context shows rank with neighbors above and below', async ({ page, api, gameId }) => {
    for (const [user, score] of [
      ['ann', 50],
      ['ben', 40],
      ['cat', 30],
      ['dan', 20],
      ['eve', 10],
    ] as const) {
      await api.submitScore(gameId, user, score);
    }
    await page.goto(`/?game=${gameId}`);

    const card = page.locator('section', { has: page.getByRole('heading', { name: 'User rank' }) });
    await card.getByLabel('User ID').fill('cat');
    await card.getByLabel('Neighbors').selectOption('2');
    await card.getByRole('button', { name: 'Look up' }).click();

    await expect(card.getByText(/cat\s+is ranked\s+#3\s+of 5/)).toBeVisible();
    const rows = card.getByRole('row');
    await expect(rows).toHaveCount(6); // header + 2 above + self + 2 below
    await expect(rows.nth(1)).toContainText('ann');
    await expect(rows.nth(3)).toHaveClass(/is-self/);
    await expect(rows.nth(5)).toContainText('eve');
  });

  test('unknown user shows a user-not-ranked problem', async ({ page, gameId }) => {
    await page.goto(`/?game=${gameId}`);
    const card = page.locator('section', { has: page.getByRole('heading', { name: 'User rank' }) });
    await card.getByLabel('User ID').fill('ghost');
    await card.getByRole('button', { name: 'Look up' }).click();
    await expect(card.getByRole('alert')).toContainText('User not ranked');
  });

  test('unknown game deep link shows a game-not-found problem', async ({ page }) => {
    await page.goto('/?game=does-not-exist');
    await expect(page.getByRole('alert').filter({ hasText: 'Game not found' })).toBeVisible();
  });

  test('updates arrive live over SSE without reloading', async ({ page, api, gameId }) => {
    await api.submitScore(gameId, 'steady', 100);
    await page.goto(`/?game=${gameId}`);
    await expect(page.getByText('Live', { exact: true })).toBeVisible();

    const top = page.locator('section', { has: page.getByRole('heading', { name: 'Top 10' }) });
    await expect(top.getByRole('row')).toHaveCount(2);

    // Written from outside the page (another client).
    await api.submitScore(gameId, 'rocket', 9000);

    await expect(top.getByRole('row')).toHaveCount(3);
    const first = top.getByRole('row').nth(1);
    await expect(first).toContainText('rocket');
    await expect(first).toHaveClass(/is-updated/);
  });
});
