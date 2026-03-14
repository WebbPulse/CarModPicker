/**
 * Invisible spacer that reserves the same space as the ad column.
 * Used when ads are hidden (e.g. premium users) so layout stays consistent.
 * Dimensions must match AdBanner (width, margin, minHeight).
 */
const AD_WIDTH = 160;
const OUTER_EDGE_MARGIN = 20;
const FOOTER_SAFE_PX = 280;
const AD_HEIGHT = 600;
const MARGIN = 8;
const AD_BOTTOM_MARGIN = 32;

const paddingTop = `calc((100vh - ${FOOTER_SAFE_PX}px) / 2 - ${AD_HEIGHT / 2 + MARGIN}px)`;
const minHeight = `calc((100vh - ${FOOTER_SAFE_PX}px) / 2 + ${AD_HEIGHT / 2 + MARGIN + AD_BOTTOM_MARGIN}px)`;

type Side = 'left' | 'right';

interface AdColumnSpacerProps {
  side: Side;
}

export default function AdColumnSpacer({ side }: AdColumnSpacerProps) {
  return (
    <aside
      className="hidden lg:flex flex-shrink-0 flex-col"
      style={{
        width: AD_WIDTH,
        paddingTop,
        paddingBottom: AD_BOTTOM_MARGIN,
        minHeight,
        ...(side === 'left'
          ? { marginLeft: OUTER_EDGE_MARGIN }
          : { marginRight: OUTER_EDGE_MARGIN }),
      }}
      aria-hidden
    />
  );
}
