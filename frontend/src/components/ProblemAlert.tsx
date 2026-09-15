import type { ProblemDetails } from '../api/generated/types.gen';

type ProblemAlertProps = {
  problem: ProblemDetails | null | undefined;
  /** Field names already shown inline next to their inputs. */
  hideFields?: readonly string[];
};

export function ProblemAlert({ problem, hideFields = [] }: ProblemAlertProps) {
  if (!problem) return null;

  const remaining = (problem.errors ?? []).filter(
    (err) => !err.pointer || !hideFields.includes(err.pointer.replace(/^#\//, '')),
  );

  return (
    <div className="problem" role="alert">
      <strong>{problem.title}</strong>
      {problem.detail && <p>{problem.detail}</p>}
      {remaining.length > 0 && (
        <ul>
          {remaining.map((err, i) => (
            <li key={i}>
              {(err.pointer ?? err.parameter ?? err.header) && (
                <code>{err.pointer ?? err.parameter ?? err.header}</code>
              )}{' '}
              {err.detail}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
