# DESIGN_SYSTEM.md

Visual language, tokens, motion and copy for the frontend. `DESIGN.md` still defines **behaviour** (what each component does). This file defines **how it looks and moves**, and wins wherever the two disagree on look and feel.

---

## 1. Concept

**Who and what:** truck drivers and dispatchers deciding, in under 10 seconds, which of three routes is safest at a given departure time and load.

**Visual vernacular:** US highway signage and road-atlas strip maps. Sign colours, white paint on dark asphalt, barricade stripes for "road closed", the strip map you used to get from a motor club. Calm and legible at a glance. Not a weather app (no blue glass, no sun icons), not a SaaS dashboard (no grid of identical rounded cards).

**The one memorable element: the route ribbon.** Every route is shown as a horizontal ribbon, like a strip map. Each stretch of road is coloured by its risk, in the order it is driven, with width proportional to miles. Hover or focus a stretch and the matching checkpoint lights up on the map. Everything else stays quiet so the ribbon carries the page.

**Do not use** (these read as generated): purple/blue gradients, gradient text, glassmorphism, emoji as icons, cream background with serif and terracotta, near-black with a neon accent, identical rounded cards with the same soft shadow, spaced all-caps eyebrow labels, strings joined with middle dots, "word — fragment" labels, arrows appended to buttons, bouncy springs everywhere, fade-and-slide-up on every section, hover-lift on every card, default MUI blue and ripple.

---

## 2. Tokens

Put in `src/styles/tokens.css` and import once. Never hard-code colours elsewhere.

```css
:root {
  /* neutrals: cool, asphalt and concrete */
  --ink: #14181B;          /* primary text, route ink */
  --ink-2: #3A4247;        /* secondary text */
  --ink-3: #5F6A70;        /* tertiary text, units (>= 5:1 on --panel) */
  --ground: #E6E9EA;       /* behind panels, map loading colour */
  --panel: #F8F9F9;        /* side panel */
  --field: #FFFFFF;        /* inputs */
  --line: #D3D8DB;         /* hairlines */

  /* action */
  --primary: #1456A0;      /* service-sign blue: buttons, links, focus */
  --primary-press: #0F4682;

  /* risk: darker as it gets worse, so it still reads without hue */
  --risk-low: #2E9E6A;
  --risk-moderate: #F2C200;
  --risk-high: #EE7B1C;
  --risk-severe: #D1322F;
  --risk-no-travel: #1B1B1F;   /* always drawn with barricade hatch in bars */
  --risk-unknown: #9AA3A8;     /* always drawn with dotted fill in bars */

  /* shape: sign-like small radii, one panel edge, no blanket shadow */
  --r-sm: 4px;             /* badges, inputs, ribbon */
  --r-md: 8px;             /* buttons, popups */
  --r-lg: 14px;            /* bottom sheet top corners only */
  --panel-edge: 0 0 0 1px var(--line), 10px 0 28px -16px rgba(20, 24, 27, 0.35);

  /* motion */
  --ease-out: cubic-bezier(0.22, 1, 0.36, 1);
  --ease-inout: cubic-bezier(0.65, 0, 0.35, 1);
  --dur-fast: 140ms;
  --dur-base: 240ms;
  --dur-slow: 520ms;

  /* type */
  --font-ui: 'Barlow', system-ui, sans-serif;
  --font-display: 'Barlow Condensed', 'Barlow', system-ui, sans-serif;
}
```

**Letter colour on a risk fill (contrast checked):**

| Level | Fill | Letter |
|---|---|---|
| Low (L) | `--risk-low` | ink |
| Moderate (M) | `--risk-moderate` | ink |
| High (H) | `--risk-high` | ink |
| Severe (S) | `--risk-severe` | white |
| No Travel (X) | `--risk-no-travel` | white |
| Unknown (?) | `--risk-unknown` | ink |

Colour is never the only signal: markers carry the letter, ribbons carry hatch and dot patterns for X and ?, popups say the level in words.

---

## 3. Typography

One superfamily, two widths, clearly distinct: **Barlow Condensed** for numbers and headings, **Barlow** for everything else. Both descend from highway lettering, so the choice comes from the subject, not a trend.

Install self-hosted (no runtime font request, no flash):

```bash
npm i @fontsource/barlow @fontsource/barlow-condensed
```

```js
// src/main.jsx
import '@fontsource/barlow/400.css';
import '@fontsource/barlow/500.css';
import '@fontsource/barlow/600.css';
import '@fontsource/barlow-condensed/500.css';
import '@fontsource/barlow-condensed/600.css';
import '@fontsource/barlow-condensed/700.css';
```

| Role | Font | Size / line | Weight |
|---|---|---|---|
| Big figure (duration, distance on featured route) | Condensed | 44 / 44 | 600 |
| Route name, panel title | Condensed | 28 / 32 | 600 |
| Section title | Barlow | 16 / 22 | 600 |
| Body, inputs, reason line | Barlow | 14 / 20 | 400 |
| Small, helper, units | Barlow | 12.5 / 16 | 500 |
| Popup ETA | Condensed | 28 / 28 | 600 |

Rules:
- Sentence case everywhere. No all-caps labels, no letter-spaced eyebrows.
- Units sit next to their number, smaller and in `--ink-3`: `795` big, `mi` small, baseline aligned.
- Numbers use `font-variant-numeric: tabular-nums`. Check that digits do not jitter during count-up; if the font lacks tabular figures, give number boxes a fixed `min-width`.
- Body lines stay under 70 characters (panel width handles this).
- No mono font for labels.

---

## 4. Layout

**Desktop:** docked left panel 420 px (scrolls), map fills the rest. The panel has one edge treatment (`--panel-edge`), no inner boxes.

```
+--------------------------+-------------------------------------------+
| Haulwise                 |                                           |
|                          |                                           |
| o  Dallas, TX        [<>]|            MAP (light, muted)             |
| :                        |   routes, checkpoints, time-delta pills   |
| #  Denver, CO            |                                           |
| Leave   Tue 14 Oct 6:00  |                                           |
| Load    42,000 lb        |                                           |
| [ Find safest route ]    |                                           |
|--------------------------|                                           |
| Recommended              |                                           |
| Route 1                  |                                           |
| 15 h 43 m     795 mi     |                                           |
| [ribbon ...............] |                                           |
| Tied on weather risk...  |                                           |
|--------------------------|                                           |
| Route 2  16 h 41 m  881 mi                                           |
| [ribbon ...............] |                                           |
| Route 3  18 h 28 m  871 mi                                           |
| [ribbon ...............] |                                           |
+--------------------------+-------------------------------------------+
```

`Haulwise` is a placeholder wordmark. Plain text in Barlow Condensed 600, no logo mark. Rename freely.

**Mobile (<= 760 px):** map on top, bottom sheet with three snap points (peek 96 px showing the recommended route summary, half, full). Drag handle, `--r-lg` top corners, same tokens. The map re-fits its bounds with padding for the visible part.

**Hierarchy:** routes are rows separated by hairlines, not boxed cards. The recommended route is taller and carries the big figures. Selected row: 3 px ink bar on the left and a white background. No hover-lift.

---

## 5. Components

### Trip form (the "spine")
- Origin and destination share a vertical spine: a ringed dot, a dotted line, a square pin. A swap button sits at the right end of the spine and rotates the spine 180 degrees as the two values cross-fade.
- Fields: 44 px tall, white, 1 px `--line`, `--r-sm`. Focus is a 2 px `--primary` ring with 2 px offset. Inline error text under the field in `--risk-severe` (check contrast) with a short fix instruction.
- Departure: native `datetime-local`, styled, with the timezone abbreviation shown beside it.
- Load: number input with a fixed `lb` suffix and a hint: "Over 30,000 lb is stricter in high wind."
- Button: full width, `--primary`, white text, `--r-md`, 48 px. Press: `scale(0.98)`. Loading: label changes, a thin indeterminate bar runs along the button bottom. Disabled until valid.
- Idle only: example chips under the button ("Dallas to Denver", "Chicago to Atlanta", "Cheyenne to Rock Springs" with a tooltip "Often windy"). Click fills the form with hard-coded coordinates. This is the empty state's invitation to act, and it helps a reviewer try the app in one click.

### Route row
- Featured (recommended): label "Recommended" as a small solid `--ink` badge with white text and a check icon; route name in Condensed 28; big duration and distance in Condensed 44; ribbon; reason line in Barlow 14 (translate `r2` in the server text into "Route 2"); warning line if `warnings` or Unknown miles exist.
- Alternates: one compact row each: name, duration, distance, ribbon, and a delta against the recommended route ("26 min slower", "Fastest" if applicable).
- Blocked: ribbon shows barricade hatch; tag "No travel on this route" with a small barricade stripe fill.
- `avg_risk` null: show "n/a". Never "null" or 0.
- All routes blocked: banner above the rows, plain language (see copy).
- Rows are a `radiogroup` with arrow-key navigation.

### Route ribbon
- Height 12 px (featured 16 px), `--r-sm`, 1 px white gaps between stretches.
- Stretch width = miles owned by each checkpoint (midpoint rule, same as backend `RULES.md` A4), in route order.
- Patterns: no_travel is a 135 degree stripe of `--risk-no-travel` and `--panel`; unknown is a dot pattern on `--risk-unknown`.
- Tick marks at each checkpoint on the featured ribbon; a tooltip on hover or focus shows "Mile 150, 8:57 AM, High".
- Linked highlight: hovering a stretch pulses that checkpoint on the map, and hovering a map marker highlights its stretch.
- `role="img"` with an `aria-label` that summarises miles per level.

### Map
- Basemap: CARTO light, no labels, as the base tile layer, and a separate labels layer on a pane above routes (zIndex 450) so route lines never bury city names. Attribution: "OpenStreetMap contributors, CARTO". Page behind tiles uses `--ground`.
- Selected route: a 9 px white casing under a 6 px line, coloured per stretch by risk (stretches use the checkpoint ownership boundaries; compute per-point cumulative miles client-side with haversine, scaled so the total equals `distance_mi`).
- Alternate routes: 4 px `--ink-3` at 55% opacity, clickable.
- Time-delta pills on alternates at the route midpoint: "+26 min". Small white pill, 1 px `--line`, Condensed 600.
- Checkpoint markers: only for the selected route (at most about 20), as `divIcon` 22 px circles, 2 px white border, 1 px hairline ring, letter inside (see table). DOM markers are fine at this count; keep polylines and the later heatmap on canvas.
- Origin pin: ringed dot with the city label; destination: square pin with the label and ETA.
- Popup: custom styled (remove Leaflet's default bubble). Layout: level badge and word at top, ETA in Condensed 28 with the timezone abbreviation, then rows for wind, gust, rain, snow with units, then the driver reason as one sentence. Opens with a 150 ms fade and 4 px rise.
- Label on the map corner: "Weather at your ETA".

---

## 6. Motion

Principle: one orchestrated moment, plus motion that answers a person's action. No decorative loops, no scroll-triggered entrances.

**The one moment: results reveal (after Analyze succeeds), about 1.6 s total.**
1. Camera eases to the bounds of all routes (`flyToBounds`, 1.0 s, `--ease-inout`).
2. Alternate routes draw in first and fast (400 ms, staggered 80 ms).
3. The selected route draws in last, stretch by stretch along its length (about 900 ms).
4. Checkpoint markers pop in along the route in order (28 ms apart, 160 ms each, scale from 0.4).
5. In the panel, rows enter with a short stagger (70 ms), figures count up (700 ms, ease-out), and the featured ribbon fills left to right (`scaleX` from the left, 600 ms).

**Motion that answers an action:**
- Selecting a route: the row's ink bar slides to it (layout animation), the map line weight and opacity tween (200 ms), the camera nudges to that route.
- Swap button: spine rotation and field cross-fade (240 ms).
- Popup open and close, button press, focus rings: 140 to 240 ms.
- Bottom sheet: drag with a soft snap.

**Loading and skeletons:**
- The panel shows skeletons shaped exactly like the real rows: one tall featured skeleton (title bar, two big figure blocks, ribbon bar, two text lines) and two compact ones. Shimmer is subtle and slow (1.4 s).
- On the map: origin and destination pins appear immediately and a dashed straight line marches between them (CSS `stroke-dashoffset` on one SVG overlay) until results arrive. Be honest: do not fake progress steps. Button label reads "Checking routes and forecasts".
- Skeleton to content swap is a 160 ms crossfade, no layout jump (reserve the same heights).

**Rules:**
- Animate only `transform` and `opacity` (plus Leaflet's own `setLatLngs` and camera calls). No layout-thrashing animations.
- `prefers-reduced-motion: reduce`: no draw-in, no pops, no count-up, no shimmer; use a 120 ms opacity change instead.
- Use `motion` (`npm i motion`, import from `motion/react`) for panel and sheet animation. Leaflet animation is hand-driven with `requestAnimationFrame`.
- Easing: `--ease-out` for entrances, `--ease-inout` for camera, no springs with visible overshoot.

---

## 7. Copy

Plain, direct, sentence case. Name things the way a driver would. A button says what happens. The same action keeps the same name through the flow. Errors say what happened and what to do, with no apology and no drama.

| Place | Text |
|---|---|
| Panel helper (idle) | Pick a start, a destination and when you leave. We check the forecast for the time you reach each checkpoint. |
| Main button | Find safest route |
| Button while loading | Checking routes and forecasts |
| Featured badge | Recommended |
| Delta on alternates | 26 min slower / Fastest |
| Blocked tag | No travel on this route |
| All blocked banner | No route is drivable at this departure time. Try leaving later. |
| Unknown weather | Forecast not available for 3 checkpoints. They are shown in grey and left out of the average. |
| Null avg risk | n/a |
| Network error | Can't reach the server. Check your connection and try again. |
| 422 no route | No drivable route found between these places. Try different locations. |
| 400 departure | Pick a departure between {start} and {end}. |
| Origin equals destination | Start and destination are the same place. |
| Load error | Enter a load above 0 lb. |
| Autocomplete empty | No matching US places. Try a city name. |
| Map corner label | Weather at your ETA |

Never show `r1`, `r2` ids or raw field names. Map `r1` to "Route 1" everywhere, including inside the server's `reason` text.

---

## 8. Code examples (starting points: adapt, test, do not paste blindly)

### Skeleton shimmer
```css
.skeleton { position: relative; overflow: hidden; background: #DDE2E4; border-radius: var(--r-sm); }
.skeleton::after {
  content: ''; position: absolute; inset: 0; transform: translateX(-100%);
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.55), transparent);
  animation: shimmer 1.4s var(--ease-inout) infinite;
}
@keyframes shimmer { to { transform: translateX(100%); } }
@media (prefers-reduced-motion: reduce) { .skeleton::after { animation: none; } }
```

### Count-up hook
```js
import { useEffect, useState } from 'react';

export function useCountUp(target, { duration = 700, decimals = 0 } = {}) {
  const reduce = typeof window !== 'undefined' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const [value, setValue] = useState(reduce ? target : 0);
  useEffect(() => {
    if (reduce) { setValue(target); return; }
    let raf; const start = performance.now();
    const tick = (now) => {
      const t = Math.min((now - start) / duration, 1);
      setValue(target * (1 - Math.pow(1 - t, 3)));
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, duration, reduce]);
  return value.toFixed(decimals);
}
```

### Progressive route draw (Leaflet)
```js
// coords: [[lat, lng], ...]. Call once per polyline; returns a cancel function.
export function revealPolyline(polyline, coords, duration = 900, onDone) {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    polyline.setLatLngs(coords); onDone?.(); return () => {};
  }
  let raf; const start = performance.now();
  const step = (now) => {
    const t = Math.min((now - start) / duration, 1);
    const eased = 1 - Math.pow(1 - t, 3);
    polyline.setLatLngs(coords.slice(0, Math.max(2, Math.floor(coords.length * eased))));
    if (t < 1) raf = requestAnimationFrame(step); else onDone?.();
  };
  raf = requestAnimationFrame(step);
  return () => cancelAnimationFrame(raf);
}
// For the risk-coloured selected route, reveal stretch polylines one after another
// by giving each its own start offset (stretch index * duration / stretchCount).
```

### Ribbon
```jsx
// ownedMiles: same midpoint rule as backend RULES.md A4. Returns [{ level, miles }] in route order.
export function RouteRibbon({ stretches, label, tall = false }) {
  return (
    <div className={`ribbon${tall ? ' ribbon--tall' : ''}`} role="img" aria-label={label}>
      {stretches.map((s, i) => (
        <span key={i} className={`ribbon__seg level-${s.level}`} style={{ flexGrow: s.miles }} />
      ))}
    </div>
  );
}
```
```css
.ribbon { display: flex; gap: 1px; height: 12px; border-radius: var(--r-sm); overflow: hidden; transform-origin: left; }
.ribbon--tall { height: 16px; }
.ribbon__seg { flex-basis: 0; min-width: 2px; }
.level-low { background: var(--risk-low); }
.level-moderate { background: var(--risk-moderate); }
.level-high { background: var(--risk-high); }
.level-severe { background: var(--risk-severe); }
.level-no_travel { background: repeating-linear-gradient(135deg, var(--risk-no-travel) 0 5px, var(--panel) 5px 9px); }
.level-unknown { background: radial-gradient(circle, #6f7a80 1px, transparent 1.4px) 0 0 / 5px 5px, var(--risk-unknown); }
```

### Checkpoint marker
```js
const icon = (level, letter, i) => L.divIcon({
  className: 'cp',
  html: `<span class="cp__dot level-${level}" style="--i:${i}">${letter}</span>`,
  iconSize: [22, 22], iconAnchor: [11, 11],
});
```
```css
.cp__dot {
  display: grid; place-items: center; width: 22px; height: 22px; border-radius: 50%;
  border: 2px solid #fff; box-shadow: 0 0 0 1px rgba(20, 24, 27, 0.35);
  font: 700 12px/1 var(--font-display); color: var(--ink);
  animation: cp-in 160ms var(--ease-out) both; animation-delay: calc(var(--i) * 28ms);
}
.cp__dot.level-severe, .cp__dot.level-no_travel { color: #fff; }
@keyframes cp-in { from { transform: scale(0.4); opacity: 0; } }
@media (prefers-reduced-motion: reduce) { .cp__dot { animation: none; } }
```
Note: `.level-no_travel` and `.level-unknown` in the ribbon use patterns; inside markers override to flat fills (`.cp__dot.level-no_travel { background: var(--risk-no-travel); }` etc.).

### Basemap with labels above routes
```jsx
<MapContainer preferCanvas center={[39, -97]} zoom={4} zoomControl={false} style={{ background: 'var(--ground)' }}>
  <TileLayer
    url="https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png"
    attribution="&copy; OpenStreetMap contributors &copy; CARTO"
  />
  {/* route and heat layers render here, above the base tiles */}
  <Pane name="labels" style={{ zIndex: 450, pointerEvents: 'none' }}>
    <TileLayer url="https://{s}.basemaps.cartocdn.com/light_only_labels/{z}/{x}/{y}{r}.png" />
  </Pane>
</MapContainer>
```

### MUI theme (so nothing looks like stock MUI)
```js
import { createTheme } from '@mui/material/styles';

export const theme = createTheme({
  palette: {
    mode: 'light',
    primary: { main: '#1456A0', dark: '#0F4682' },
    text: { primary: '#14181B', secondary: '#3A4247' },
    background: { default: '#E6E9EA', paper: '#F8F9F9' },
  },
  shape: { borderRadius: 8 },
  typography: {
    fontFamily: "'Barlow', system-ui, sans-serif",
    button: { textTransform: 'none', fontWeight: 600 },
  },
  components: {
    MuiButtonBase: { defaultProps: { disableRipple: true } },
    MuiPaper: { defaultProps: { elevation: 0 } },
    MuiOutlinedInput: { styleOverrides: { root: { borderRadius: 4, background: '#fff' } } },
  },
});
```
Use MUI for primitives that are hard to build well (Autocomplete, Slider in Phase 6, Popover, Tooltip). Build the route rows, ribbon, badges, spine and sheet by hand with the tokens.

### Staggered panel entrance (used once per analysis)
```js
export const list = { show: { transition: { staggerChildren: 0.07, delayChildren: 0.15 } } };
export const item = {
  hidden: { opacity: 0, y: 8 },
  show: { opacity: 1, y: 0, transition: { duration: 0.32, ease: [0.22, 1, 0.36, 1] } },
};
```

---

## 9. References to study

Open these in the browser tool, spend a few minutes each, and write one line on what you borrow. Do not copy any of them.

| Reference | Borrow |
|---|---|
| Windy.com | Timeline scrubber behaviour and how a colour layer sits on a map without hiding it (for Phase 6) |
| Google Maps directions | Alternate routes: selected strong, others muted, time-delta label on the line |
| Flightradar24 | Map-first layout with a docked side panel; legible data on a busy map |
| Apple Weather | Calm numeric hierarchy: big figures, small units, almost no chrome |
| Linear | Restraint: hairlines, tight type scale, motion only when it explains something |
| MUTCD sign colours (US highway signs) | Colour logic and the barricade stripe for "closed" |
| Old motor-club strip maps | The ribbon idea: a route read as a line, left to right |

---

## 10. Quality floor and self-critique

Build to this without announcing it:
- Responsive down to 360 px wide, no horizontal scroll.
- Visible keyboard focus on every control; route rows reachable with arrow keys.
- Contrast: text at least 4.5:1, UI shapes at least 3:1. Colour never the only signal.
- Reduced motion respected.
- No layout shift between skeleton and content.

Before reporting, run this critique and list three things you removed or simplified:
1. Does any screen use one of the "Do not use" items in section 1?
2. Is the ribbon clearly the most memorable element, with everything else quieter?
3. Do all radii, shadows and borders come from tokens, with at most one shadow in the whole UI?
4. Are all strings from section 7, with no `r1`, `null`, or raw field names visible?
5. Take a screenshot at 1440 px and at 390 px. Squint at it: can you tell which route is recommended and why in two seconds?

---

## 11. Hooks for Phase 6 (do not build yet)

- Heat ramp (transparent to opaque): `--risk-low` at 0.25 alpha, then `--risk-moderate`, `--risk-high`, `--risk-severe`, ending at `--risk-no-travel`. It must stay readable on the light basemap and under the labels pane.
- Slider: a thin 4 px track in `--line` with the elapsed part in `--ink`; a 20 px thumb with white fill, 2 px `--ink` border and `--primary` focus ring; time label in Condensed above the thumb; play button in the same family as the primary button but outlined.
- The slider and heat controls live in a single bar anchored to the bottom of the map (desktop) or inside the sheet (mobile).