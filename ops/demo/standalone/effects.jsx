// effects.jsx — jaw-dropper UI primitives.
// Tasteful motion: tilt, spotlight, particles, number rolls, bursts, reveals.

const { useState: useSE, useEffect: useEE, useRef: useRE, useLayoutEffect: useLE, useCallback: useCE } = React;

// ---------------------------------------------------------------
// useReveal — IntersectionObserver hook. Returns ref + className flag.
// ---------------------------------------------------------------
function useReveal(opts = {}) {
  const ref = useRE(null);
  const [shown, setShown] = useSE(false);
  useEE(() => {
    const el = ref.current; if (!el || shown) return;
    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => { if (e.isIntersecting) { setShown(true); io.disconnect(); } });
    }, { threshold: opts.threshold ?? 0.15, rootMargin: opts.rootMargin ?? "0px" });
    io.observe(el);
    return () => io.disconnect();
  }, [shown]);
  return [ref, shown];
}

// ---------------------------------------------------------------
// Reveal — wrap children, animate them in once visible.
// ---------------------------------------------------------------
function Reveal({ children, delay = 0, as: Tag = "div", className = "", style = {}, ...rest }) {
  const [ref, shown] = useReveal();
  return (
    <Tag
      ref={ref}
      className={`${shown ? "reveal-go" : "reveal-init"} ${className}`}
      style={{ ...style, animationDelay: shown ? `${delay}ms` : undefined }}
      {...rest}
    >
      {children}
    </Tag>
  );
}

// ---------------------------------------------------------------
// TiltCard — 3D tilt on hover with spotlight glow + sheen sweep.
// Pass `intensity` (default 8 deg) to scale the tilt.
// ---------------------------------------------------------------
function TiltCard({ children, intensity = 7, glow = true, sheen = true, className = "", style = {}, ...rest }) {
  const ref = useRE(null);

  const onMove = (e) => {
    const el = ref.current; if (!el) return;
    const r = el.getBoundingClientRect();
    const x = e.clientX - r.left, y = e.clientY - r.top;
    const px = x / r.width, py = y / r.height;
    el.style.setProperty("--mx", `${x}px`);
    el.style.setProperty("--my", `${y}px`);
    el.style.setProperty("--mx-pct", `${(px * 100).toFixed(1)}`);
    el.style.setProperty("--ry", `${((px - 0.5) * intensity).toFixed(2)}deg`);
    el.style.setProperty("--rx", `${((0.5 - py) * intensity).toFixed(2)}deg`);
    el.style.setProperty("--glow-opacity", "1");
    el.style.setProperty("--sheen-opacity", "1");
  };
  const onLeave = () => {
    const el = ref.current; if (!el) return;
    el.style.setProperty("--rx", "0deg");
    el.style.setProperty("--ry", "0deg");
    el.style.setProperty("--glow-opacity", "0");
    el.style.setProperty("--sheen-opacity", "0");
  };

  return (
    <div
      ref={ref}
      onMouseMove={onMove}
      onMouseLeave={onLeave}
      className={`tilt-card relative ${className}`}
      style={style}
      {...rest}
    >
      {children}
      {glow && <div className="tilt-glow" />}
      {sheen && <div className="tilt-sheen" />}
    </div>
  );
}

// ---------------------------------------------------------------
// Spotlight — cursor-tracked radial highlight on a container.
// Drop inside a `position: relative` parent.
// ---------------------------------------------------------------
function Spotlight({ className = "" }) {
  const ref = useRE(null);
  useEE(() => {
    const el = ref.current; if (!el) return;
    const parent = el.parentElement; if (!parent) return;
    let raf = 0;
    const onMove = (e) => {
      const r = parent.getBoundingClientRect();
      const x = e.clientX - r.left, y = e.clientY - r.top;
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        el.style.setProperty("--mx", `${x}px`);
        el.style.setProperty("--my", `${y}px`);
      });
    };
    const onEnter = () => el.classList.add("is-active");
    const onLeave = () => el.classList.remove("is-active");
    parent.addEventListener("mousemove", onMove);
    parent.addEventListener("mouseenter", onEnter);
    parent.addEventListener("mouseleave", onLeave);
    return () => {
      parent.removeEventListener("mousemove", onMove);
      parent.removeEventListener("mouseenter", onEnter);
      parent.removeEventListener("mouseleave", onLeave);
      cancelAnimationFrame(raf);
    };
  }, []);
  return <div ref={ref} className={`cursor-spotlight ${className}`} />;
}

// ---------------------------------------------------------------
// Particles — drifting glowing dots inside a relative container.
// ---------------------------------------------------------------
function Particles({ count = 14, className = "", colors = ["", "cyan", "violet"] }) {
  const items = useRE(null);
  if (!items.current) {
    items.current = Array.from({ length: count }).map((_, i) => ({
      top: `${Math.random() * 100}%`,
      left: `${Math.random() * 100}%`,
      dx: `${(Math.random() - 0.5) * 80}px`,
      dy: `${(Math.random() - 0.5) * 60}px`,
      dur: `${4 + Math.random() * 5}s`,
      delay: `${Math.random() * 4}s`,
      size: 3 + Math.random() * 3,
      color: colors[i % colors.length],
    }));
  }
  return (
    <div className={`absolute inset-0 overflow-hidden pointer-events-none ${className}`} aria-hidden>
      {items.current.map((p, i) => (
        <span
          key={i}
          className={`particle ${p.color}`}
          style={{
            top: p.top, left: p.left,
            width: `${p.size}px`, height: `${p.size}px`,
            "--dx": p.dx, "--dy": p.dy,
            "--dur": p.dur, "--delay": p.delay,
          }}
        />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------
// NumberRoll — animate from 0 → target on first paint or on `value` change.
// Format with `format` fn. Duration ms; easing cubic-out.
// ---------------------------------------------------------------
function NumberRoll({ value, duration = 1100, format = (v) => Math.round(v).toString(), className = "", start = 0 }) {
  const [v, setV] = useSE(start);
  const fromRef = useRE(start);
  const startedAt = useRE(0);
  const rafRef = useRE(0);

  useEE(() => {
    cancelAnimationFrame(rafRef.current);
    fromRef.current = v;
    startedAt.current = performance.now();
    const target = Number(value);
    const from = fromRef.current;
    const ease = (t) => 1 - Math.pow(1 - t, 3);
    const tick = (now) => {
      const t = Math.min(1, (now - startedAt.current) / duration);
      const cur = from + (target - from) * ease(t);
      setV(cur);
      if (t < 1) rafRef.current = requestAnimationFrame(tick);
      else setV(target);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current);
  // eslint-disable-next-line
  }, [value, duration]);

  return <span className={`tabular-nums ${className}`}>{format(v)}</span>;
}

// ---------------------------------------------------------------
// RippleBurst — three staggered rings expanding from center.
// Renders only when `active` is true; remount via key to retrigger.
// ---------------------------------------------------------------
function RippleBurst({ tone = "brand", active = true }) {
  if (!active) return null;
  const cls = tone === "green" ? "green" : tone === "red" ? "red" : tone === "amber" ? "amber" : "";
  return (
    <>
      <span className={`burst-ring ${cls}`} />
      <span className={`burst-ring ${cls} delay-1`} />
      <span className={`burst-ring ${cls} delay-2`} />
    </>
  );
}

// ---------------------------------------------------------------
// FlowingDot — animated dot riding an SVG path. Pass `pathId`.
// Use INSIDE an <svg>. Wraps SVG <circle> + <animateMotion>.
// ---------------------------------------------------------------
function FlowingDot({ pathId, dur = "2.4s", begin = "0s", color = "currentColor", r = 2.4, opacity = 0.95 }) {
  return (
    <circle r={r} fill={color} opacity={opacity}>
      <animateMotion dur={dur} repeatCount="indefinite" begin={begin}>
        <mpath href={`#${pathId}`} />
      </animateMotion>
    </circle>
  );
}

// ---------------------------------------------------------------
// Shimmer — text element shimmer (for skeletons / "thinking" copy)
// ---------------------------------------------------------------
function Shimmer({ children, className = "" }) {
  return (
    <span
      className={`bg-clip-text text-transparent ${className}`}
      style={{
        backgroundImage: "linear-gradient(90deg, var(--ink-muted) 0%, var(--ink-primary) 50%, var(--ink-muted) 100%)",
        backgroundSize: "220% 100%",
        animation: "sweep 2.4s linear infinite",
      }}
    >
      {children}
    </span>
  );
}

// ---------------------------------------------------------------
// MagneticButton — slight cursor pull on hover.
// ---------------------------------------------------------------
function MagneticButton({ children, strength = 0.18, className = "", as: Tag = "button", ...rest }) {
  const ref = useRE(null);
  const onMove = (e) => {
    const el = ref.current; if (!el) return;
    const r = el.getBoundingClientRect();
    const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
    const dx = (e.clientX - cx) * strength;
    const dy = (e.clientY - cy) * strength;
    el.style.transform = `translate(${dx}px, ${dy}px)`;
  };
  const onLeave = () => { const el = ref.current; if (el) el.style.transform = ""; };
  return (
    <Tag ref={ref} onMouseMove={onMove} onMouseLeave={onLeave}
         className={`transition-transform duration-200 ease-out ${className}`} {...rest}>
      {children}
    </Tag>
  );
}

// ---------------------------------------------------------------
// AnimatedCounterUp — counts when scrolled into view.
// ---------------------------------------------------------------
function CounterOnVisible({ value, duration, format, className }) {
  const [ref, shown] = useReveal({ threshold: 0.4 });
  return (
    <span ref={ref} className={className}>
      {shown
        ? <NumberRoll value={value} duration={duration} format={format} />
        : <span className="tabular-nums opacity-30">{format ? format(0) : 0}</span>}
    </span>
  );
}

Object.assign(window, {
  useReveal, Reveal, TiltCard, Spotlight, Particles,
  NumberRoll, RippleBurst, FlowingDot, Shimmer, MagneticButton, CounterOnVisible,
});
