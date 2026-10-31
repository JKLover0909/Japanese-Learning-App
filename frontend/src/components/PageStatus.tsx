export function PageStatus({ label }: { label: string }) {
  return (
    <div className="status-page" role="status">
      <span className="status-mark" aria-hidden="true">日</span>
      <p>{label}</p>
    </div>
  );
}
