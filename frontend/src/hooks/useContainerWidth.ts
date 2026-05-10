import { useCallback, useRef, useState, type RefCallback } from 'react';

/**
 * Returns a callback ref and the observed element's content width.
 * Uses a callback ref (not useRef) so the ResizeObserver is wired up
 * whenever the element mounts — even if the first render showed a
 * loading state and the element wasn't in the DOM yet.
 * Returns 0 until the first measurement.
 */
export function useContainerWidth<T extends HTMLElement>(): [
  RefCallback<T>,
  number,
] {
  const observerRef = useRef<ResizeObserver | null>(null);
  const rafRef = useRef(0);
  const [width, setWidth] = useState(0);

  const ref = useCallback((el: T | null) => {
    if (observerRef.current) {
      observerRef.current.disconnect();
      observerRef.current = null;
      cancelAnimationFrame(rafRef.current);
    }

    if (!el) return;

    const observer = new ResizeObserver((entries) => {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = requestAnimationFrame(() => {
        const w = entries[0]?.contentRect.width;
        if (typeof w === 'number') setWidth(w);
      });
    });
    observer.observe(el);
    observerRef.current = observer;
    setWidth(el.getBoundingClientRect().width);
  }, []);

  return [ref, width];
}
