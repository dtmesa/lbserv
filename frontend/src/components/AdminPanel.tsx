import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useForm } from 'react-hook-form';

import { problemFieldErrors } from '../api/client';
import {
  createGameMutation,
  listGamesQueryKey,
  submitScoreMutation,
} from '../api/generated/@tanstack/react-query.gen';
import { zGameCreate, zScoreSubmission } from '../api/generated/zod.gen';
import { ProblemAlert } from './ProblemAlert';

type AdminPanelProps = {
  gameId: string | undefined;
  onGameCreated: (gameId: string) => void;
};

const SCORE_FIELDS = ['user_id', 'score'] as const;
const GAME_FIELDS = ['id', 'name'] as const;

/** Write operations. The API key lives only in memory for this browser tab. */
export function AdminPanel({ gameId, onGameCreated }: AdminPanelProps) {
  const [apiKey, setApiKey] = useState('');

  return (
    <details className="card admin" open>
      <summary>
        <h2>Admin</h2>
      </summary>
      <div className="field">
        <label htmlFor="api-key">API key</label>
        <input
          id="api-key"
          type="password"
          autoComplete="off"
          value={apiKey}
          placeholder="Required for writes"
          onChange={(e) => {
            setApiKey(e.target.value);
          }}
        />
      </div>
      {gameId && <SubmitScoreForm gameId={gameId} apiKey={apiKey} />}
      <CreateGameForm apiKey={apiKey} onCreated={onGameCreated} />
    </details>
  );
}

function SubmitScoreForm({ gameId, apiKey }: { gameId: string; apiKey: string }) {
  const form = useForm({
    resolver: zodResolver(zScoreSubmission),
    defaultValues: { user_id: '', score: 0 },
  });
  const mutation = useMutation({
    ...submitScoreMutation(),
    onSuccess: () => {
      form.setValue('score', 0);
    },
    onError: (problem) => {
      for (const field of SCORE_FIELDS) {
        const message = problemFieldErrors(problem).get(field);
        if (message) form.setError(field, { message });
      }
    },
  });

  const result = mutation.data;
  const { errors } = form.formState;

  return (
    <form
      className="stack"
      noValidate
      onSubmit={(e) =>
        void form.handleSubmit((body) => {
          mutation.mutate({ path: { game_id: gameId }, body, auth: apiKey });
        })(e)
      }
    >
      <h3>Submit score</h3>
      <div className="inline-form">
        <div className="field">
          <label htmlFor="score-user">User ID</label>
          <input id="score-user" autoComplete="off" {...form.register('user_id')} />
          {errors.user_id && <span className="field-error">{errors.user_id.message}</span>}
        </div>
        <div className="field">
          <label htmlFor="score-value">Score</label>
          <input
            id="score-value"
            type="number"
            min={0}
            step={1}
            {...form.register('score', { valueAsNumber: true })}
          />
          {errors.score && <span className="field-error">{errors.score.message}</span>}
        </div>
        <button type="submit" disabled={mutation.isPending}>
          Submit
        </button>
      </div>
      <ProblemAlert problem={mutation.error} hideFields={SCORE_FIELDS} />
      {result && (
        <p className="success" role="status">
          {result.improved ? 'New best!' : 'Not a personal best.'} {result.user_id} is #{result.rank}{' '}
          with {result.best_score}.
        </p>
      )}
    </form>
  );
}

function CreateGameForm({ apiKey, onCreated }: { apiKey: string; onCreated: (id: string) => void }) {
  const queryClient = useQueryClient();
  const form = useForm({ resolver: zodResolver(zGameCreate), defaultValues: { id: '', name: '' } });
  const mutation = useMutation({
    ...createGameMutation(),
    onSuccess: async (game) => {
      form.reset();
      await queryClient.invalidateQueries({ queryKey: listGamesQueryKey() });
      onCreated(game.id);
    },
    onError: (problem) => {
      for (const field of GAME_FIELDS) {
        const message = problemFieldErrors(problem).get(field);
        if (message) form.setError(field, { message });
      }
    },
  });
  const { errors } = form.formState;

  return (
    <form
      className="stack"
      noValidate
      onSubmit={(e) =>
        void form.handleSubmit((body) => {
          mutation.mutate({ body, auth: apiKey });
        })(e)
      }
    >
      <h3>Create game</h3>
      <div className="inline-form">
        <div className="field">
          <label htmlFor="game-id">Slug</label>
          <input id="game-id" autoComplete="off" placeholder="space-invaders" {...form.register('id')} />
          {errors.id && <span className="field-error">{errors.id.message}</span>}
        </div>
        <div className="field">
          <label htmlFor="game-name">Name</label>
          <input id="game-name" autoComplete="off" placeholder="Space Invaders" {...form.register('name')} />
          {errors.name && <span className="field-error">{errors.name.message}</span>}
        </div>
        <button type="submit" disabled={mutation.isPending}>
          Create
        </button>
      </div>
      <ProblemAlert problem={mutation.error} hideFields={GAME_FIELDS} />
    </form>
  );
}
