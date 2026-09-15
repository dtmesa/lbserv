import { useQuery } from '@tanstack/react-query';
import { useEffect } from 'react';

import { listGamesOptions } from '../api/generated/@tanstack/react-query.gen';
import { ProblemAlert } from './ProblemAlert';

type GameSelectProps = {
  value: string | undefined;
  onChange: (gameId: string) => void;
};

export function GameSelect({ value, onChange }: GameSelectProps) {
  const { data, error, isPending } = useQuery(listGamesOptions());
  const games = data?.games ?? [];
  const firstGameId = games[0]?.id;

  useEffect(() => {
    if (!value && firstGameId) onChange(firstGameId);
  }, [value, firstGameId, onChange]);

  return (
    <div className="game-select">
      <label htmlFor="game">Game</label>
      <select
        id="game"
        value={value ?? ''}
        disabled={isPending || games.length === 0}
        onChange={(e) => {
          onChange(e.target.value);
        }}
      >
        {games.length === 0 && <option value="">{isPending ? 'Loading…' : 'No games yet'}</option>}
        {games.map((game) => (
          <option key={game.id} value={game.id}>
            {game.name}
          </option>
        ))}
      </select>
      <ProblemAlert problem={error} />
    </div>
  );
}
