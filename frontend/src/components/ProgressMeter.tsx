interface ProgressMeterProps {
  label: string;
  value: number;
  total: number;
  tone?: 'accent' | 'success' | 'warning';
  className?: string;
}

/** Accessible single-value progress meter; text always carries the value. */
export function ProgressMeter({ label, value, total, tone = 'accent', className = '' }: ProgressMeterProps) {
  const safeTotal = Math.max(0, total);
  const safeValue = Math.min(Math.max(0, value), safeTotal);
  const percent = safeTotal > 0 ? (safeValue / safeTotal) * 100 : 0;
  return (
    <div className={`meter ${className}`}>
      <div className="meter-label-row">
        <span>{label}</span>
        <span className="meter-value">{safeValue}<span className="meter-total"> / {safeTotal}</span></span>
      </div>
      <div
        className={`meter-track meter-${tone}`}
        role="progressbar"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={safeTotal}
        aria-valuenow={safeValue}
      >
        <span className="meter-fill" style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
}
