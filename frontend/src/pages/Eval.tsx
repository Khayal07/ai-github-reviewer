import { EvalRun, getEvalRuns } from "../api";
import { Empty, ErrorNote, Loading, fmtDate, useAsync } from "../ui";

function pct(v: number | null | undefined): string {
  return v == null ? "—" : `${(v * 100).toFixed(0)}%`;
}

function Bar({ value }: { value: number | null | undefined }) {
  const w = value == null ? 0 : Math.round(value * 100);
  return (
    <div className="h-2 rounded-full bg-[var(--color-paper)] overflow-hidden">
      <div className="h-full rounded-full" style={{ width: `${w}%`, background: "var(--color-brand)" }} />
    </div>
  );
}

function RunCard({ run }: { run: EvalRun }) {
  const perPass = (run.report?.per_pass ?? {}) as Record<
    string,
    { precision: number; recall: number }
  >;
  return (
    <div className="card p-6 rise">
      <div className="flex items-baseline justify-between">
        <div className="eyebrow">run #{run.id} · {run.num_cases} cases</div>
        <div className="text-xs text-[var(--color-muted)]">{fmtDate(run.created_at)}</div>
      </div>

      <div className="grid grid-cols-3 gap-6 mt-4">
        <div>
          <div className="eyebrow">precision</div>
          <div className="font-mono text-2xl font-semibold">{pct(run.precision)}</div>
          <div className="mt-2"><Bar value={run.precision} /></div>
        </div>
        <div>
          <div className="eyebrow">recall</div>
          <div className="font-mono text-2xl font-semibold">{pct(run.recall)}</div>
          <div className="mt-2"><Bar value={run.recall} /></div>
        </div>
        <div>
          <div className="eyebrow">avg latency</div>
          <div className="font-mono text-2xl font-semibold">
            {run.avg_latency_ms != null ? `${run.avg_latency_ms.toFixed(0)}ms` : "—"}
          </div>
        </div>
      </div>

      {Object.keys(perPass).length > 0 && (
        <div className="mt-5 border-t pt-4">
          <div className="eyebrow mb-2">by pass</div>
          <div className="grid grid-cols-2 gap-x-8 gap-y-1 text-sm">
            {Object.entries(perPass).map(([name, m]) => (
              <div key={name} className="flex justify-between font-mono text-xs">
                <span>{name}</span>
                <span className="text-[var(--color-muted)]">
                  P {pct(m.precision)} · R {pct(m.recall)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function EvalPage() {
  const { data, error, loading } = useAsync(getEvalRuns);
  if (error) return <ErrorNote error={error} />;
  if (loading || !data) return <Loading />;

  return (
    <div className="flex flex-col gap-5">
      <header>
        <div className="eyebrow">evaluation</div>
        <h1 className="font-mono text-3xl font-bold tracking-tight mt-1">Benchmark runs</h1>
        <p className="text-[var(--color-ink-soft)] mt-2 max-w-2xl">
          Each run scores the reviewer against synthetic PRs with known injected
          issues — recall is how many it caught, precision how few it invented.
        </p>
      </header>

      {data.length === 0 ? (
        <Empty>
          Run <code className="font-mono">python -m eval.run_eval</code> to record a
          benchmark here.
        </Empty>
      ) : (
        data.map((run) => <RunCard key={run.id} run={run} />)
      )}
    </div>
  );
}
