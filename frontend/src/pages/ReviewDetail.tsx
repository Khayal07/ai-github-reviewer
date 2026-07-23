import { Link, useParams } from "react-router-dom";
import { Finding, getReview } from "../api";
import {
  CountPills,
  ErrorNote,
  Loading,
  SeverityDot,
  VerdictBadge,
  fmtDate,
  useAsync,
} from "../ui";

const PASS_LABEL: Record<string, string> = {
  correctness: "correctness",
  security: "security",
  style: "style",
  tests: "tests",
};

function FindingCard({ f }: { f: Finding }) {
  return (
    <div className={`gutter-row tick-${sevClass(f.severity)} card p-4 flex gap-3`}>
      <span className="lineno pt-0.5">
        {f.file.split("/").pop()}:{f.line}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 flex-wrap">
          <SeverityDot severity={f.severity} />
          <span className="font-medium">{f.title}</span>
          <span className="eyebrow">{PASS_LABEL[f.pass_type] ?? f.pass_type}</span>
          <span className="eyebrow">· conf {(f.confidence * 100).toFixed(0)}%</span>
        </div>
        <p className="text-sm text-[var(--color-ink-soft)] mt-1">{f.message}</p>
        {f.suggestion && (
          <pre className="mt-2 bg-[var(--color-paper)] rounded-md p-2 text-xs font-mono overflow-x-auto">
            {f.suggestion}
          </pre>
        )}
        <div className="font-mono text-xs text-[var(--color-muted)] mt-2">{f.file}</div>
      </div>
    </div>
  );
}

function sevClass(s: string): string {
  return { critical: "crit", high: "high", medium: "med", low: "low", info: "info" }[s] ?? "info";
}

export default function ReviewDetail() {
  const { id } = useParams();
  const { data, error, loading } = useAsync(() => getReview(id!), [id]);
  if (error) return <ErrorNote error={error} />;
  if (loading || !data) return <Loading />;

  return (
    <div className="flex flex-col gap-6">
      <Link to="/reviews" className="text-sm text-[var(--color-brand)]">
        ← reviews
      </Link>

      <header className="card p-6">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <div className="eyebrow">review #{data.id}</div>
            <h1 className="font-mono text-2xl font-bold tracking-tight mt-1">
              {data.repo_full_name}{" "}
              <span className="text-[var(--color-muted)]">#{data.pr_number}</span>
            </h1>
            <div className="text-sm text-[var(--color-muted)] mt-1">
              {fmtDate(data.created_at)}
              {data.head_sha && ` · ${data.head_sha.slice(0, 7)}`}
              {data.latency_ms != null && ` · ${(data.latency_ms / 1000).toFixed(1)}s`}
            </div>
          </div>
          <div className="flex items-center gap-4">
            <CountPills counts={data.counts} />
            <VerdictBadge verdict={data.verdict} status={data.status} />
          </div>
        </div>
      </header>

      <section className="flex flex-col gap-3">
        <h2 className="eyebrow">
          findings ({data.findings.length})
        </h2>
        {data.findings.length === 0 ? (
          <div className="card p-6 text-sm text-[var(--color-muted)]">
            No findings — this diff came back clean.
          </div>
        ) : (
          data.findings.map((f) => <FindingCard key={f.id} f={f} />)
        )}
      </section>
    </div>
  );
}
