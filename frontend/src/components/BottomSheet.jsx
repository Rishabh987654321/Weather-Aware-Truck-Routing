import { useState, useRef, useEffect } from 'react';

/**
 * Mobile BottomSheet with 3 snap points: 'peek' (100px), 'half' (45%), 'full' (85%)
 */
export default function BottomSheet({ children, defaultSnap = 'half' }) {
  const [snap, setSnap] = useState(defaultSnap);
  const dragStartY = useRef(0);
  const isDragging = useRef(false);

  useEffect(() => {
    if (defaultSnap) {
      setSnap(defaultSnap);
    }
  }, [defaultSnap]);

  const snapHeights = {
    peek: '100px',
    half: '50vh',
    full: '88vh',
  };

  const handleTouchStart = (e) => {
    dragStartY.current = e.touches[0].clientY;
    isDragging.current = true;
  };

  const handleTouchEnd = (e) => {
    if (!isDragging.current) return;
    isDragging.current = false;
    const diff = e.changedTouches[0].clientY - dragStartY.current;
    if (diff > 50) {
      // Drag down
      if (snap === 'full') setSnap('half');
      else if (snap === 'half') setSnap('peek');
    } else if (diff < -50) {
      // Drag up
      if (snap === 'peek') setSnap('half');
      else if (snap === 'half') setSnap('full');
    }
  };

  return (
    <div
      style={{
        position: 'fixed',
        bottom: 0,
        left: 0,
        right: 0,
        height: snapHeights[snap],
        background: 'var(--panel)',
        borderTop: '1px solid var(--line)',
        borderTopLeftRadius: 'var(--r-lg)',
        borderTopRightRadius: 'var(--r-lg)',
        boxShadow: '0 -8px 24px -4px rgba(20, 24, 27, 0.25)',
        zIndex: 1000,
        display: 'flex',
        flexDirection: 'column',
        transition: 'height var(--dur-base) var(--ease-out)',
        overflow: 'hidden',
      }}
    >
      {/* Drag handle */}
      <div
        onTouchStart={handleTouchStart}
        onTouchEnd={handleTouchEnd}
        onClick={() => {
          if (snap === 'peek') setSnap('half');
          else if (snap === 'half') setSnap('full');
          else setSnap('peek');
        }}
        style={{
          width: '100%',
          padding: '10px 0 6px 0',
          display: 'grid',
          placeItems: 'center',
          cursor: 'grab',
          flexShrink: 0,
        }}
      >
        <div
          style={{
            width: '36px',
            height: '4px',
            borderRadius: '2px',
            background: 'var(--line)',
          }}
        />
      </div>

      {/* Sheet Content */}
      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '0 16px 24px 16px',
        }}
      >
        {children}
      </div>
    </div>
  );
}
