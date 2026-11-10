export default function Loading({ children = "Loading your financial data…" }) {
  return <div className="db-loading" role="status"><span className="db-loader" aria-hidden="true"/>{children}</div>;
}
