import { getRepos } from "../api";
import { Empty, ErrorNote, Loading, fmtDate, useAsync } from "../ui";

export default function Repos() {
  const { data, error, loading } = useAsync(getRepos);
  if (error) return <ErrorNote error={error} />;
  if (loading || !data) return <Loading />;

  return (
    <div className="flex flex-col gap-4">
      <header>
        <div className="eyebrow">repositories</div>
        <h1 className="font-mono text-3xl font-bold tracking-tight mt-1">Connected repos</h1>
      </header>

      {data.length === 0 ? (
        <Empty>
          Install the GitHub App on a repository, or run the Action, and it
          shows up here.
        </Empty>
      ) : (
        <div className="grid sm:grid-cols-2 gap-4 rise">
          {data.map((r) => (
            <div key={r.full_name} className="card p-5">
              <div className="font-mono text-sm break-all">{r.full_name}</div>
              <div className="flex items-center justify-between mt-4">
                <div>
                  <div className="font-mono text-2xl font-semibold">{r.review_count}</div>
                  <div className="eyebrow">reviews</div>
                </div>
                <div className="text-right text-xs text-[var(--color-muted)]">
                  {r.installation_id ? (
                    <span className="badge" style={{ color: "var(--color-approve)" }}>
                      app installed
                    </span>
                  ) : (
                    <span className="badge" style={{ color: "var(--color-muted)" }}>
                      action / manual
                    </span>
                  )}
                  <div className="mt-2">{fmtDate(r.created_at)}</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
