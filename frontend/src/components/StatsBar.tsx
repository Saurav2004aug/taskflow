import type { Stats } from "../api/types";

export default function StatsBar({ stats }: { stats: Stats | null }) {
  const pct = stats ? Math.round(stats.completion_rate * 100) : 0;
  const items = [
    { label: "Total tasks", value: stats?.total ?? "–" },
    { label: "High priority open", value: stats?.high_priority_open ?? "–", tone: "warn" },
    { label: "Due this week", value: stats?.due_this_week ?? "–" },
    { label: "Overdue", value: stats?.overdue ?? "–", tone: stats && stats.overdue > 0 ? "bad" : undefined },
  ];
  return (
    <section className="stats" aria-label="Summary">
      {items.map((it) => (
        <div className={`stat${it.tone ? ` stat-${it.tone}` : ""}`} key={it.label}>
          <span className="stat-value">{it.value}</span>
          <span className="stat-label">{it.label}</span>
        </div>
      ))}
      <div className="stat stat-progress">
        <span className="stat-value">{pct}%</span>
        <span className="stat-label">Completed</span>
        <div className="progress" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
          <div className="progress-fill" style={{ width: `${pct}%` }} />
        </div>
      </div>
    </section>
  );
}
