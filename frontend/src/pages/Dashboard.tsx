import { Link } from "react-router-dom";
import { getReviews, getStats } from "../api";
import {
  CountPills,
  ErrorNote,
  Loading,
  VerdictBadge,
  fmtDate,
  useAsync,
  worstTick,
} from "../ui";

function Metric({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="card p-5">
      <div className="eyebrow">{label}</div>
      <div className="font-mono text-3xl font-semibold mt-2">{value}</div>
      {hint && <div className="text-sm text-[var(--color-muted)] mt-1">{hint}</div>}
    </div>
  );
}

export default function Dashboard() {
  const stats = useAsync(getStats);
  const reviews = useAsync(getReviews);

  if (stats.error) return <ErrorNote error={stats.error} />;
  if (stats.loading || !stats.data) return <Loading />;

  const s = stats.data;
  const recent = (reviews.data ?? []).slice(0, 6);

  return (
    <div className="flex flex-col gap-8">
      {/* hero: the thesis — what this bot has done, in its own terminal voice */}
      <header className="rise">
        <div className="eyebrow">dashboard</div>
        <h1 className="font-mono text-4xl font-bold tracking-tight mt-1">
          Every PR, reviewed four ways.
        </h1>
        <p className="text-[var(--color-ink-soft)] mt-2 max-w-2xl">
          Correctness, security, style, and test-coverage passes run on each
          diff, then post inline comments and a verdict back to GitHub.
        </p>
      </header>

      <section className="grid grid-cols-2 md:grid-cols-4 gap-4 rise">
        <Metric label="reviews" value={String(s.total_reviews)} />
        <Metric label="findings" value={String(s.total_findings)} />
        <Metric label="repositories" value={String(s.total_repos)} />
        <Metric
          label="avg latency"
          value={s.avg_latency_ms ? `${(s.avg_latency_ms / 1000).toFixed(1)}s` : "—"}
        />
      </section>

      <section>
        <div className="flex items-baseline justify-between mb-3">
          <h2 className="eyebrow">recent reviews</h2>
          <Link to="/reviews" className="text-sm text-[var(--color-brand)] font-medium">
            view all →
          </Link>
        </div>
        <div className="card divide-y">
          {recent.length === 0 && (
            <div className="p-6 text-sm text-[var(--color-muted)]">
              No reviews yet. Open a pull request on a connected repo, or run
              the Action, to see results here.
            </div>
          )}
          {recent.map((r) => (
            <Link
              to={`/reviews/${r.id}`}
              key={r.id}
              className={`gutter-row ${worstTick(r.counts)} flex items-center gap-4 px-4 py-3`}
            >
              <div className="flex-1 min-w-0">
                <div className="font-mono text-sm truncate">
                  {r.repo_full_name}
                  <span className="text-[var(--color-muted)]"> #{r.pr_number}</span>
                </div>
                <div className="text-xs text-[var(--color-muted)]">{fmtDate(r.created_at)}</div>
              </div>
              <CountPills counts={r.counts} />
              <VerdictBadge verdict={r.verdict} status={r.status} />
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
