import { useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';

import {
  getLeaderboardQueryKey,
  getUserContextQueryKey,
} from '../api/generated/@tanstack/react-query.gen';
import { streamLeaderboardEvents } from '../api/generated/sdk.gen';
import type { LeaderboardEvent } from '../api/generated/types.gen';

export type StreamStatus = 'idle' | 'connecting' | 'live' | 'reconnecting';

const INVALIDATE_THROTTLE_MS = 300;

function isQueryForGame(queryKey: readonly unknown[], ids: readonly string[], gameId: string) {
  const [key] = queryKey;
  if (typeof key !== 'object' || key === null || !('_id' in key) || !('path' in key)) {
    return false;
  }
  const { path } = key;
  return (
    typeof key._id === 'string' &&
    ids.includes(key._id) &&
    typeof path === 'object' &&
    path !== null &&
    'game_id' in path &&
    path.game_id === gameId
  );
}

/**
 * Subscribes to a game's Server-Sent Events and refreshes its leaderboard and user-context
 * queries when scores change. Events are validated against the generated zod schema.
 */
export function useLeaderboardEvents(gameId: string | undefined) {
  const queryClient = useQueryClient();
  // State is tagged with its game so switching games never shows the previous game's stream.
  const [streamState, setStreamState] = useState<{ gameId: string; status: StreamStatus }>();
  const [eventState, setEventState] = useState<{ gameId: string; event: LeaderboardEvent }>();

  useEffect(() => {
    if (!gameId) return;
    const controller = new AbortController();
    const aborted = () => controller.signal.aborted;
    const setStatus = (status: StreamStatus) => {
      if (!aborted()) setStreamState({ gameId, status });
    };
    const queryIds = [
      getLeaderboardQueryKey({ path: { game_id: gameId } })[0]._id,
      getUserContextQueryKey({ path: { game_id: gameId, user_id: '_' } })[0]._id,
    ];
    let timer: ReturnType<typeof setTimeout> | undefined;

    const invalidate = () => {
      if (timer) return;
      timer = setTimeout(() => {
        timer = undefined;
        void queryClient.invalidateQueries({
          predicate: (query) => isQueryForGame(query.queryKey, queryIds, gameId),
        });
      }, INVALIDATE_THROTTLE_MS);
    };

    const run = async () => {
      // The generated client retries dropped connections; restart if the server ends the stream.
      while (!aborted()) {
        const { stream } = await streamLeaderboardEvents({
          path: { game_id: gameId },
          signal: controller.signal,
          sseMaxRetryDelay: 10_000,
          onSseEvent: () => {
            setStatus('live');
          },
          onSseError: () => {
            setStatus('reconnecting');
          },
        });
        for await (const event of stream) {
          setEventState({ gameId, event });
          invalidate();
        }
        if (!aborted()) {
          setStatus('reconnecting');
          // Refetch anything we might have missed while disconnected.
          invalidate();
        }
      }
    };
    void run();

    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [gameId, queryClient]);

  const status: StreamStatus = !gameId
    ? 'idle'
    : streamState?.gameId === gameId
      ? streamState.status
      : 'connecting';
  const lastEvent = eventState && eventState.gameId === gameId ? eventState.event : null;
  return { status, lastEvent };
}
