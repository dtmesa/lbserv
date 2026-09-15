import { useCallback, useState } from 'react';

import { AdminPanel } from './components/AdminPanel';
import { GameSelect } from './components/GameSelect';
import { TopLeaderboard } from './components/TopLeaderboard';
import { UserContext } from './components/UserContext';
import { type StreamStatus, useLeaderboardEvents } from './hooks/useLeaderboardEvents';

const STATUS_LABEL: Record<StreamStatus, string> = {
  idle: 'Idle',
  connecting: 'Connecting…',
  live: 'Live',
  reconnecting: 'Reconnecting…',
};

function readGameFromUrl(): string | undefined {
  return new URLSearchParams(window.location.search).get('game') ?? undefined;
}

export function App() {
  const [gameId, setGameIdState] = useState(readGameFromUrl);
  const { status, lastEvent } = useLeaderboardEvents(gameId);
  const flashUserId = lastEvent?.game_id === gameId ? lastEvent?.user_id : undefined;

  const setGameId = useCallback((id: string) => {
    setGameIdState(id);
    const url = new URL(window.location.href);
    url.searchParams.set('game', id);
    window.history.replaceState(null, '', url);
  }, []);

  return (
    <div className="app">
      <header className="topbar">
        <h1>🏆 lbserv</h1>
        <GameSelect value={gameId} onChange={setGameId} />
        <span className={`status status-${status}`} aria-live="polite">
          {STATUS_LABEL[status]}
        </span>
      </header>

      <main className="grid">
        {gameId ? (
          <>
            <TopLeaderboard gameId={gameId} flashUserId={flashUserId} />
            <div className="column">
              <UserContext gameId={gameId} flashUserId={flashUserId} />
              <AdminPanel gameId={gameId} onGameCreated={setGameId} />
            </div>
          </>
        ) : (
          <AdminPanel gameId={undefined} onGameCreated={setGameId} />
        )}
      </main>
    </div>
  );
}
