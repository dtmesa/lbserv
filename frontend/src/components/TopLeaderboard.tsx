import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { useState } from 'react';

import { getLeaderboardOptions } from '../api/generated/@tanstack/react-query.gen';
import { ProblemAlert } from './ProblemAlert';
import { RankTable } from './RankTable';

const LIMITS = [10, 100] as const;

type TopLeaderboardProps = {
  gameId: string;
  flashUserId?: string;
};

export function TopLeaderboard({ gameId, flashUserId }: TopLeaderboardProps) {
  const [limit, setLimit] = useState<(typeof LIMITS)[number]>(10);
  const { data, error, isPending, isFetching } = useQuery({
    ...getLeaderboardOptions({ path: { game_id: gameId }, query: { limit } }),
    placeholderData: keepPreviousData,
  });

  return (
    <section className="card">
      <header className="card-head">
        <h2>
          Top {limit}
          {isFetching && !isPending && <span className="spinner" aria-label="Refreshing" />}
        </h2>
        <div className="segmented" role="group" aria-label="Number of users">
          {LIMITS.map((n) => (
            <button
              key={n}
              type="button"
              aria-pressed={limit === n}
              onClick={() => {
                setLimit(n);
              }}
            >
              {n}
            </button>
          ))}
        </div>
      </header>
      {data && <p className="muted">{data.total_players} players</p>}
      <ProblemAlert problem={error} />
      {isPending ? (
        <p className="muted">Loading…</p>
      ) : (
        data && <RankTable entries={data.entries} flashUserId={flashUserId} />
      )}
    </section>
  );
}
