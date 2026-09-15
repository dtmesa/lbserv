import { zodResolver } from '@hookform/resolvers/zod';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useForm } from 'react-hook-form';

import { getUserContextOptions } from '../api/generated/@tanstack/react-query.gen';
import { zGetUserContextPath } from '../api/generated/zod.gen';
import { ProblemAlert } from './ProblemAlert';
import { RankTable } from './RankTable';

const lookupSchema = zGetUserContextPath.pick({ user_id: true });
const NEIGHBOR_OPTIONS = [0, 1, 2, 3, 5, 10] as const;

type UserContextProps = {
  gameId: string;
  flashUserId?: string;
};

export function UserContext({ gameId, flashUserId }: UserContextProps) {
  const [userId, setUserId] = useState<string>();
  const [neighbors, setNeighbors] = useState<number>(1);
  const form = useForm({ resolver: zodResolver(lookupSchema), defaultValues: { user_id: '' } });

  const { data, error, isFetching } = useQuery({
    ...getUserContextOptions({
      path: { game_id: gameId, user_id: userId ?? '' },
      query: { neighbors },
    }),
    enabled: Boolean(userId),
    retry: false,
  });

  const entries = data ? [...data.above, data.user, ...data.below] : [];

  return (
    <section className="card">
      <header className="card-head">
        <h2>User rank</h2>
      </header>
      <form
        className="inline-form"
        onSubmit={(e) =>
          void form.handleSubmit((values) => {
            setUserId(values.user_id);
          })(e)
        }
        noValidate
      >
        <div className="field">
          <label htmlFor="lookup-user">User ID</label>
          <input id="lookup-user" autoComplete="off" {...form.register('user_id')} />
          {form.formState.errors.user_id && (
            <span className="field-error">{form.formState.errors.user_id.message}</span>
          )}
        </div>
        <div className="field">
          <label htmlFor="lookup-neighbors">Neighbors</label>
          <select
            id="lookup-neighbors"
            value={neighbors}
            onChange={(e) => {
              setNeighbors(Number(e.target.value));
            }}
          >
            {NEIGHBOR_OPTIONS.map((n) => (
              <option key={n} value={n}>
                ±{n}
              </option>
            ))}
          </select>
        </div>
        <button type="submit" disabled={isFetching}>
          Look up
        </button>
      </form>

      {userId && <ProblemAlert problem={error} />}
      {data && (
        <>
          <p className="rank-summary">
            <strong>{data.user.user_id}</strong> is ranked <strong>#{data.user.rank}</strong> of{' '}
            {data.total_players}
          </p>
          <RankTable entries={entries} highlightUserId={data.user.user_id} flashUserId={flashUserId} />
        </>
      )}
    </section>
  );
}
