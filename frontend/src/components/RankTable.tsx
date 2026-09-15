import type { LeaderboardEntry } from '../api/generated/types.gen';

type RankTableProps = {
  entries: readonly LeaderboardEntry[];
  highlightUserId?: string;
  flashUserId?: string;
  emptyMessage?: string;
};

const numberFormat = new Intl.NumberFormat();

export function RankTable({ entries, highlightUserId, flashUserId, emptyMessage }: RankTableProps) {
  if (entries.length === 0) {
    return <p className="muted">{emptyMessage ?? 'No scores yet.'}</p>;
  }
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th className="num">Rank</th>
            <th>User</th>
            <th className="num">Score</th>
            <th className="hide-narrow">Achieved</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((entry) => {
            const classes = [
              entry.user_id === highlightUserId ? 'is-self' : '',
              entry.user_id === flashUserId ? 'is-updated' : '',
            ].join(' ');
            return (
              <tr key={`${entry.user_id}-${String(entry.score)}`} className={classes.trim() || undefined}>
                <td className="num">#{entry.rank}</td>
                <td>{entry.user_id}</td>
                <td className="num">{numberFormat.format(entry.score)}</td>
                <td className="hide-narrow muted">{new Date(entry.achieved_at).toLocaleString()}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
