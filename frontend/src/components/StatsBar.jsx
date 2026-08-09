export default function StatsBar({ stats }) {
  if (!stats) return null;

  const cards = [
    { label: 'Total Processed', value: stats.total_processed, color: 'blue' },
    { label: 'Created', value: stats.created, color: 'green' },
    { label: 'Updated', value: stats.updated, color: 'purple' },
    { label: 'Skipped', value: stats.skipped, color: 'amber' },
    { label: 'Errors', value: stats.errors, color: 'red' },
  ];

  return (
    <div className="stats-bar">
      {cards.map((card) => (
        <div key={card.label} className={`stat-card ${card.color}`}>
          <div className="stat-label">{card.label}</div>
          <div className="stat-value">{card.value}</div>
        </div>
      ))}
    </div>
  );
}
