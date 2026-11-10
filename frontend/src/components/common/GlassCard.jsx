
export default function GlassCard({ title, subtitle, action, children, className = "" }) {
  return <section className={`db-panel glass-card ${className}`}>
    {(title || action) && <div className="db-panel-heading"><div><h3>{title}</h3>{subtitle && <p>{subtitle}</p>}</div>{action}</div>}
    {children}
  </section>;
}
