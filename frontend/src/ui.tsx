import { useEffect, useState } from "react";

/* tiny data-fetching hook — loading / error / data in one shot */
export function useAsync<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    fn()
      .then((d) => alive && (setData(d), setError(null)))
      .catch((e) => alive && setError(String(e)))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { data, error, loading };
}

export const SEVERITIES = ["critical", "high", "medium", "low", "info"] as const;

const SEV_TICK: Record<string, string> = {
  critical: "tick-crit",
  high: "tick-high",
  medium: "tick-med",
  low: "tick-low",
  info: "tick-info",
};

const SEV_COLOR: Record<string, string> = {
  critical: "var(--color-crit)",
  high: "var(--color-high)",
  medium: "var(--color-med)",
  low: "var(--color-low)",
  info: "var(--color-info)",
};

/** Worst severity present in a counts map, for the row gutter colour. */
export function worstTick(counts: Record<string, number> | undefined): string {
  if (!counts) return "tick-none";
  for (const s of SEVERITIES) if (counts[s]) return SEV_TICK[s];
  return "tick-none";
}

export function SeverityDot({ severity }: { severity: string }) {
  return (
    <span
      className="inline-block w-2.5 h-2.5 rounded-full"
      style={{ background: SEV_COLOR[severity] ?? "var(--color-muted)" }}
    />
  );
}

const VERDICT_STYLE: Record<string, { label: string; color: string }> = {
  approve: { label: "approved", color: "var(--color-approve)" },
  comment: { label: "commented", color: "var(--color-brand)" },
  request_changes: { label: "changes requested", color: "var(--color-high)" },
};

export function VerdictBadge({ verdict, status }: { verdict: string | null; status?: string }) {
  if (status && status !== "completed") {
    const c = status === "failed" ? "var(--color-crit)" : "var(--color-muted)";
    return (
      <span className="badge" style={{ color: c }}>
        {status}
      </span>
    );
  }
  const v = verdict ? VERDICT_STYLE[verdict] : null;
  if (!v) return <span className="badge" style={{ color: "var(--color-muted)" }}>—</span>;
  return (
    <span className="badge" style={{ color: v.color }}>
      {v.label}
    </span>
  );
}

export function CountPills({ counts }: { counts: Record<string, number> }) {
  const present = SEVERITIES.filter((s) => counts[s]);
  if (present.length === 0)
    return <span className="text-[var(--color-muted)] text-sm">clean</span>;
  return (
    <span className="flex items-center gap-2">
      {present.map((s) => (
        <span key={s} className="flex items-center gap-1 text-sm">
          <SeverityDot severity={s} />
          <span className="font-mono text-xs">{counts[s]}</span>
        </span>
      ))}
    </span>
  );
}

export function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function Loading() {
  return <div className="eyebrow p-6">loading…</div>;
}

export function ErrorNote({ error }: { error: string }) {
  return (
    <div className="card p-6 text-sm" style={{ color: "var(--color-crit)" }}>
      Couldn’t reach the API — {error}. Is the backend running on :8000?
    </div>
  );
}

export function Empty({ children }: { children: React.ReactNode }) {
  return (
    <div className="card p-10 text-center">
      <div className="eyebrow mb-2">nothing here yet</div>
      <div className="text-[var(--color-ink-soft)]">{children}</div>
    </div>
  );
}
