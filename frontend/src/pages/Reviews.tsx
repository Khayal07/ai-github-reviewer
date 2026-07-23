import { Link } from "react-router-dom";
import { getReviews } from "../api";
import {
  CountPills,
  Empty,
  ErrorNote,
  Loading,
  VerdictBadge,
  fmtDate,
  useAsync,
  worstTick,
} from "../ui";

export default function Reviews() {
  const { data, error, loading } = useAsync(getReviews);
  if (error) return <ErrorNote error={error} />;
  if (loading || !data) return <Loading />;

  return (
    <div className="flex flex-col gap-4">
      <header>
        <div className="eyebrow">reviews</div>
        <h1 className="font-mono text-3xl font-bold tracking-tight mt-1">Review log</h1>
      </header>

      {data.length === 0 ? (
        <Empty>Reviews appear here as PRs are opened or the Action runs.</Empty>
      ) : (
        <div className="card divide-y rise">
          {data.map((r) => (
            <Link
              key={r.id}
              to={`/reviews/${r.id}`}
              className={`gutter-row ${worstTick(r.counts)} grid grid-cols-[1fr_auto_auto] items-center gap-4 px-4 py-3`}
            >
              <div className="min-w-0">
                <div className="font-mono text-sm truncate">
                  {r.repo_full_name}
                  <span className="text-[var(--color-muted)]"> #{r.pr_number}</span>
                  {r.head_sha && (
                    <span className="text-[var(--color-muted)]"> · {r.head_sha.slice(0, 7)}</span>
                  )}
                </div>
                <div className="text-xs text-[var(--color-muted)]">
                  {fmtDate(r.created_at)}
                  {r.latency_ms != null && ` · ${(r.latency_ms / 1000).toFixed(1)}s`}
                </div>
              </div>
              <CountPills counts={r.counts} />
              <VerdictBadge verdict={r.verdict} status={r.status} />
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
