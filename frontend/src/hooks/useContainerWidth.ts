import { useLayoutEffect, useRef, useState, type RefObject } from 'react';

/**
 * Observes the attached element's inline width via ResizeObserver,
 * debounced with requestAnimationFrame. Returns 0 until the first measurement.
 */
export function useContainerWidth<T extends HTMLElement>(): [
  RefObject<T | null>,
  number,
] {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(0);

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    let raf = 0;
    const observer = new ResizeObserver((entries) => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        const w = entries[0]?.contentRect.width;
        if (typeof w === 'number') setWidth(w);
      });
    });
    observer.observe(el);
    setWidth(el.getBoundingClientRect().width);
    return () => {
      observer.disconnect();
      cancelAnimationFrame(raf);
    };
  }, []);

  return [ref, width];
}
