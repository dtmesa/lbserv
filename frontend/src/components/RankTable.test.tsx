import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { LeaderboardEntry } from '../api/generated/types.gen';
import { RankTable } from './RankTable';

const entries: LeaderboardEntry[] = [
  { rank: 1, user_id: 'eve', score: 500, achieved_at: '2026-09-15T19:28:13Z' },
  { rank: 2, user_id: 'bob', score: 300, achieved_at: '2026-09-15T19:28:12Z' },
];

describe('RankTable', () => {
  it('renders ranks in order and highlights the selected user', () => {
    render(<RankTable entries={entries} highlightUserId="bob" />);
    const rows = screen.getAllByRole('row').slice(1);
    expect(rows.map((row) => within(row).getAllByRole('cell')[1]?.textContent)).toEqual(['eve', 'bob']);
    expect(rows[1]).toHaveClass('is-self');
  });

  it('shows an empty state', () => {
    render(<RankTable entries={[]} />);
    expect(screen.getByText('No scores yet.')).toBeInTheDocument();
  });
});
