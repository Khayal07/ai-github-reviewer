import { NavLink, Route, Routes } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import Reviews from "./pages/Reviews";
import ReviewDetail from "./pages/ReviewDetail";
import Repos from "./pages/Repos";
import EvalPage from "./pages/Eval";

const NAV = [
  { to: "/", label: "Overview", end: true },
  { to: "/reviews", label: "Reviews", end: false },
  { to: "/repos", label: "Repositories", end: false },
  { to: "/eval", label: "Evaluation", end: false },
];

export default function App() {
  return (
    <div className="min-h-screen flex">
      {/* left rail — the console's spine */}
      <aside className="w-60 shrink-0 border-r bg-[var(--color-surface)] px-4 py-6 flex flex-col gap-8 sticky top-0 h-screen">
        <div>
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-sm" style={{ background: "var(--color-brand)" }} />
            <span className="font-mono font-bold tracking-tight">ai-review</span>
          </div>
          <p className="eyebrow mt-2">pull-request auditor</p>
        </div>

        <nav className="flex flex-col gap-1">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}
            >
              {n.label}
            </NavLink>
          ))}
        </nav>

        <div className="mt-auto eyebrow leading-relaxed">
          multi-pass review
          <br />
          correctness · security
          <br />
          style · tests
        </div>
      </aside>

      <main className="flex-1 min-w-0 px-8 py-8 max-w-6xl">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/reviews" element={<Reviews />} />
          <Route path="/reviews/:id" element={<ReviewDetail />} />
          <Route path="/repos" element={<Repos />} />
          <Route path="/eval" element={<EvalPage />} />
        </Routes>
      </main>
    </div>
  );
}
