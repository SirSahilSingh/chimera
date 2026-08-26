export function StatBlock({ label, value, note, tone = "default" }: { label: string; value: string; note?: string; tone?: "default" | "mint" | "amber" | "blue" }) {
  return <div className={`stat-block ${tone}`}><div className="stat-label">{label}</div><div className="stat-value">{value}</div>{note && <div className="stat-note">{note}</div>}</div>;
}
