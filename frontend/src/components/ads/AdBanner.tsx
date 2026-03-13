import { useEffect, useRef } from 'react';

/** Width of the sidebar ad in pixels. Standard skyscraper / banner sizes. */
const AD_WIDTH = 160;
const AD_HEIGHT = 600;

/** Reserve space at bottom so the ad never overlaps the footer. Match footer height (main block + bottom bar). */
const FOOTER_SAFE_PX = 280;

/** Minimum gap between the bottom of the ad and the footer on short pages. */
const AD_BOTTOM_MARGIN = 32;

type AdBannerSide = 'left' | 'right';

interface AdBannerProps {
  /** Which side this banner is on (for styling/layout). */
  side: AdBannerSide;
  /**
   * Optional AdSense slot ID (e.g. "1234567890").
   * Set VITE_ADSENSE_CLIENT_ID in .env to enable real ads; otherwise a placeholder is shown.
   */
  slotId?: string | undefined;
}

declare global {
  interface Window {
    adsbygoogle: unknown[];
  }
}

/**
 * Global sidebar ad banner. Renders in left/right margins.
 * When the route changes, the parent should remount this component (e.g. key={location.pathname})
 * so a new ad is requested for another ad view.
 */
export default function AdBanner({ side, slotId }: AdBannerProps) {
  const insRef = useRef<HTMLModElement>(null);
  const clientId = import.meta.env['VITE_ADSENSE_CLIENT_ID'] as
    | string
    | undefined;
  const hasAdConfig = Boolean(clientId);

  useEffect(() => {
    if (!hasAdConfig || !slotId || !insRef.current) return;
    try {
      (window.adsbygoogle = window.adsbygoogle || []).push({});
    } catch {
      // AdSense may not be loaded yet or blocked
    }
  }, [hasAdConfig, slotId]);

  const MARGIN = 8;
  /** Extra space between the ad and the browser's left/right edge. */
  const OUTER_EDGE_MARGIN = 20;
  // On initial load, place ad so its center is at viewport center (above footer). In-flow so it scrolls with the page.
  const paddingTop = `calc((100vh - ${FOOTER_SAFE_PX}px) / 2 - ${AD_HEIGHT / 2 + MARGIN}px)`;
  // Min height so on short pages the aside fits ad + bottom margin and never collides with the footer.
  const minHeight = `calc((100vh - ${FOOTER_SAFE_PX}px) / 2 + ${AD_HEIGHT / 2 + MARGIN + AD_BOTTOM_MARGIN}px)`;

  return (
    <aside
      className="hidden lg:flex flex-shrink-0 flex-col items-center"
      style={{
        width: AD_WIDTH,
        paddingTop,
        paddingBottom: AD_BOTTOM_MARGIN,
        minHeight,
        ...(side === 'left'
          ? { marginLeft: OUTER_EDGE_MARGIN }
          : { marginRight: OUTER_EDGE_MARGIN }),
      }}
      aria-label={`Advertisement ${side}`}
    >
      <div
        className="rounded-lg overflow-hidden border border-white/10 bg-black/20 flex items-center justify-center"
        style={{
          width: AD_WIDTH,
          minHeight: AD_HEIGHT,
          marginLeft: MARGIN,
          marginRight: MARGIN,
        }}
      >
        {hasAdConfig && slotId ? (
          <ins
            ref={insRef as React.RefObject<HTMLModElement>}
            className="adsbygoogle"
            style={{
              display: 'block',
              minHeight: AD_HEIGHT,
              minWidth: AD_WIDTH,
            }}
            data-ad-client={clientId}
            data-ad-slot={slotId}
            data-ad-format="auto"
            data-full-width-responsive="false"
          />
        ) : (
          <div
            className="text-neutral-500 text-xs text-center p-4"
            style={{ minHeight: AD_HEIGHT, minWidth: AD_WIDTH }}
          >
            <span className="block mt-20">Ad placeholder</span>
            <span className="block mt-2">
              {clientId ? 'Set slot id' : 'Set VITE_ADSENSE_CLIENT_ID'}
            </span>
          </div>
        )}
      </div>
    </aside>
  );
}
