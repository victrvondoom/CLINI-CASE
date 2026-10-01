/**
 * Reveal — scroll-triggered fade/rise.
 *
 * Stands in for framer-motion's `whileInView` (not a dependency of this app).
 * One IntersectionObserver per element, disconnected after the first reveal so
 * the effect is once-only, matching the original `viewport={{ once: true }}`.
 */
import { useEffect, useRef, useState } from "react";
import type { CSSProperties, ElementType, ReactNode } from "react";

interface Props {
  children: ReactNode;
  /** Stagger, in ms. */
  delay?: number;
  className?: string;
  style?: CSSProperties;
  as?: ElementType;
  id?: string;
  /** Forwarded so sections can drive the 3D scene on hover/focus. */
  onMouseEnter?: () => void;
  onFocus?: () => void;
}

export default function Reveal({
  children,
  delay = 0,
  className,
  style,
  as: Tag = "div",
  id,
  onMouseEnter,
  onFocus,
}: Props) {
  const ref = useRef<HTMLElement | null>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    // No IntersectionObserver (very old browser / jsdom) → show immediately
    // rather than leaving the content invisible.
    if (typeof IntersectionObserver === "undefined") {
      setVisible(true);
      return;
    }
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { rootMargin: "-10% 0px", threshold: 0.05 },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return (
    <Tag
      ref={ref}
      id={id}
      onMouseEnter={onMouseEnter}
      onFocus={onFocus}
      className={[
        "aperture-reveal",
        visible ? "is-visible" : "",
        className ?? "",
      ]
        .filter(Boolean)
        .join(" ")}
      style={{ ...style, ["--reveal-delay" as string]: `${delay}ms` }}
    >
      {children}
    </Tag>
  );
}
