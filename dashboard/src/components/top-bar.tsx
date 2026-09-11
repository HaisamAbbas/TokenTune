export function TopBar({
  title,
  subtitle,
  breadcrumb,
  action,
}: {
  title: string;
  subtitle?: string;
  breadcrumb?: { label: string; href?: string }[];
  action?: React.ReactNode;
}) {
  return (
    <div className="h-16 shrink-0 flex items-center justify-between px-7">
      <div className="flex items-baseline gap-3 min-w-0">
        {breadcrumb ? (
          <div className="flex items-baseline gap-2.5 min-w-0">
            {breadcrumb.map((b, i) => (
              <span key={i} className="t-body-sm" style={{ color: "var(--on-surface-variant)" }}>
                {b.label} /
              </span>
            ))}
            <span className="t-headline truncate" style={{ fontSize: 17 }}>
              {title}
            </span>
          </div>
        ) : (
          <>
            <span className="t-headline">{title}</span>
            {subtitle && (
              <span className="t-body-sm" style={{ color: "var(--on-surface-variant)" }}>
                {subtitle}
              </span>
            )}
          </>
        )}
      </div>
      <div className="flex items-center gap-3 shrink-0">
        {action}
        <div
          className="w-8 h-8 rounded-full flex items-center justify-center text-[12px] font-medium"
          style={{ background: "var(--primary-container)", color: "var(--on-primary-container)" }}
        >
          HA
        </div>
      </div>
    </div>
  );
}
