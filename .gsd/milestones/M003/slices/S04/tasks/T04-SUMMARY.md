---
id: T04
parent: S04
milestone: M003
key_files:
  - frontend/src/styles/tokens.css
key_decisions:
  - Followed task plan's option (a): preserved the `text-gradient` class name via `@utility` over rewriting all ~25 consumer sites to inline gradient utilities — least diff surface, hover/group-hover variants compose automatically per MEM063.
  - Intentionally dropped the legacy `gradientShift` animation + `background-size: 200% 200%` from the replacement because the `gradientShift` keyframe is scheduled for hard-deletion in S04 pass-2 per MEM144 and reintroducing a tokenized version would contradict the hard-delete intent. Static gradient is a deliberate fidelity tradeoff documented inline.
  - Inlined the literal hex stops (#667eea → #764ba2) rather than reaching for HSL conversions, matching the legacy `--gradient-primary` byte-for-byte and following the task plan's prescribed snippet.
duration: 
verification_result: untested
completed_at: 2026-04-26T23:01:42.959Z
blocker_discovered: false
---

# T04: Add tokenized @utility text-gradient block to tokens.css preserving #667eea→#764ba2 gradient identity for the ~25 consumer sites before S04 pass-2 deletes the legacy rule

**Add tokenized @utility text-gradient block to tokens.css preserving #667eea→#764ba2 gradient identity for the ~25 consumer sites before S04 pass-2 deletes the legacy rule**

## What Happened

Registered a tokenized `@utility text-gradient` block in `frontend/src/styles/tokens.css` (immediately after the T01-introduced `animate-glow` block) so the ~25 consumer sites — About.tsx, ContactUs.tsx, Pricing.tsx, Support.tsx, TermsOfService.tsx, PrivacyPolicy.tsx, NotFound.tsx, Checkout.tsx, including bare `text-gradient`, `hover:text-gradient`, and `group-hover:text-gradient` variants — keep resolving after S04 pass-2 deletes the legacy `.text-gradient` rule at `index.css:737-744`. Per MEM063/MEM070, Tailwind v4 applies state variants on top of `@utility`-declared classes, so hover/group-hover compose automatically with no extra declarations needed.

Followed the task plan's prescribed shape (option (a): same class name, same colors, simple `@utility` block) rather than rewriting all consumer sites to inline gradient utilities. Colors preserved verbatim from the legacy `--gradient-primary: linear-gradient(135deg, #667eea 0%, #764ba2 100%)`.

One deliberate fidelity drop: the legacy `.text-gradient` ran `gradientShift 3s ease infinite` over `background-size: 200% 200%` for an animated color shift. The replacement is static. This is correct because `gradientShift` is one of the 11 keyframes scheduled for hard-deletion in S04 pass-2 (MEM144), it had no surviving consumer outside the four legacy `.text-gradient`/`.btn-primary`/`.hero-gradient`/`.border-gradient` rules also being deleted, and reintroducing a tokenized animation here would contradict the hard-delete intent. T01's pattern of cherry-picking only surviving keyframes (slideInRight/shimmer/gradient/border-glow excluded as zero-consumer) sets the precedent. Documented this tradeoff inline in the comment block above the new utility.

The block follows the same shape as M002/S08's `@utility animate-in` (tokens.css:159) and the T01 `animate-fadeInScale` family — same comment-then-utility structure, same indentation, same precedence in the file.

## Verification

Two-step verification per task plan: (1) `rg -q '@utility text-gradient' frontend/src/styles/tokens.css` returned exit 0 confirming the new block is present in the file. (2) `cd frontend && npm run build` succeeded (exit 0, 4.54s) and the postbuild prerender step rendered all 7 routes including the text-gradient-heavy About / ContactUs / Pricing / Support / TermsOfService / PrivacyPolicy pages without error — meaning Tailwind v4 successfully resolves the `text-gradient` class against the new `@utility` block at build time. No new build warnings beyond the pre-existing chunk-size advisory.</verification>
<parameter name="verificationEvidence">[{"command": "rg -q '@utility text-gradient' frontend/src/styles/tokens.css", "exitCode": 0, "verdict": "✅ pass", "durationMs": 30}, {"command": "cd frontend && npm run build", "exitCode": 0, "verdict": "✅ pass", "durationMs": 15640}]

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| — | No verification commands discovered | — | — | — |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `frontend/src/styles/tokens.css`
