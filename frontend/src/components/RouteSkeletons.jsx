/**
 * RouteSkeletons per DESIGN_SYSTEM.md section 6 & 8
 * Shaped exactly like the real rows (featured + 2 compact)
 */
export default function RouteSkeletons() {
  return (
    <div
      aria-busy="true"
      aria-label="Loading route recommendations"
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '1px',
        background: 'var(--line)',
        width: '100%',
      }}
    >
      {/* Featured skeleton */}
      <div
        style={{
          padding: '16px 20px',
          background: 'var(--panel)',
          display: 'flex',
          flexDirection: 'column',
          gap: '12px',
        }}
      >
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <div className="skeleton" style={{ width: '92px', height: '22px' }} />
          <div className="skeleton" style={{ width: '70px', height: '22px' }} />
        </div>

        <div style={{ display: 'flex', gap: '20px', alignItems: 'baseline', margin: '6px 0' }}>
          <div className="skeleton" style={{ width: '130px', height: '42px' }} />
          <div className="skeleton" style={{ width: '90px', height: '42px' }} />
          <div className="skeleton" style={{ width: '50px', height: '24px', marginLeft: 'auto' }} />
        </div>

        <div className="skeleton" style={{ width: '100%', height: '16px' }} />
        <div className="skeleton" style={{ width: '85%', height: '16px' }} />
        <div className="skeleton" style={{ width: '50%', height: '14px' }} />
      </div>

      {/* Compact skeleton 1 */}
      <div
        style={{
          padding: '14px 20px',
          background: 'var(--panel)',
          display: 'flex',
          flexDirection: 'column',
          gap: '10px',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', gap: '10px' }}>
            <div className="skeleton" style={{ width: '60px', height: '20px' }} />
            <div className="skeleton" style={{ width: '75px', height: '20px' }} />
            <div className="skeleton" style={{ width: '55px', height: '18px' }} />
          </div>
          <div className="skeleton" style={{ width: '70px', height: '18px' }} />
        </div>
        <div className="skeleton" style={{ width: '100%', height: '12px' }} />
      </div>

      {/* Compact skeleton 2 */}
      <div
        style={{
          padding: '14px 20px',
          background: 'var(--panel)',
          display: 'flex',
          flexDirection: 'column',
          gap: '10px',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', gap: '10px' }}>
            <div className="skeleton" style={{ width: '60px', height: '20px' }} />
            <div className="skeleton" style={{ width: '75px', height: '20px' }} />
            <div className="skeleton" style={{ width: '55px', height: '18px' }} />
          </div>
          <div className="skeleton" style={{ width: '70px', height: '18px' }} />
        </div>
        <div className="skeleton" style={{ width: '100%', height: '12px' }} />
      </div>
    </div>
  );
}
