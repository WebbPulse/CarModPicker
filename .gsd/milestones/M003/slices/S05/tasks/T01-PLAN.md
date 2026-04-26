---
estimated_steps: 1
estimated_files: 4
skills_used: []
---

# T01: Add Textarea, StatusBadge/PriorityBadge, LoadingOverlay primitives + retokenize card-info-item.tsx

Land the four atomic primitive additions/refactors that block the polish batches (T03/T04/T05). Each primitive is a copy-of-existing-pattern with semantic-token surfaces only — bias is consumption of the existing token system per MEM149 (additions need concrete justification: 5 textarea sites, 3 status-badge sites, 3 loading-overlay sites, ~4 InfoItem sites). The existing card-info-item.tsx is retokenized off text-gray-300 → text-muted-foreground for the label and text-foreground for the value (no API change). All four ship in this single task because they are atomic tokenized component additions/edits with no cross-dependencies and trivial surface area. NO consumer migration in this task — consumers swap in subsequent batch tasks (T03/T04/T05). Quality gate (Q3 Threat Surface): None — presentational primitives with no input handling, auth, or data-access semantics; the Textarea forwards onChange/value props to a native textarea; consumers retain their own change handlers and validation. Quality gate (Q4 Requirement Impact): Touches R060 (per-slice baseline refresh) — refreshed PNG baselines for any spec that screenshots a card with CardInfoItem will pick up the text-gray-300 → text-muted-foreground color delta; refreshed in T06's cascade pass. Decision rationale (autonomous mode): Research recommended a DangerActionPanel extraction conditional on user approval for SystemAdmin's 10 near-identical danger sections — auto-mode cannot surface that, so deferred to S06 UAT and SystemAdmin tokenized in-place during T05. Skill: make-interfaces-feel-better + lint/test for verification.

## Inputs

- ``frontend/src/components/ui/card-info-item.tsx``
- ``frontend/src/components/ui/alert.tsx``
- ``frontend/src/components/ui/badge.tsx``
- ``frontend/src/components/ui/card.tsx``
- ``frontend/src/styles/tokens.css``

## Expected Output

- ``frontend/src/components/ui/textarea.tsx``
- ``frontend/src/components/ui/status-badge.tsx``
- ``frontend/src/components/ui/loading-overlay.tsx``
- ``frontend/src/components/ui/card-info-item.tsx``

## Verification

1. cd frontend && npm run type-check exits 0. 2. cd frontend && npm run lint exits 0 (zero new errors over MEM062 baseline of 108). 3. rg 'text-gray-' frontend/src/components/ui/card-info-item.tsx returns 0. 4. rg '\bbg-(primary|neutral|emerald|indigo|amber|rose)-[0-9]|text-accent-' frontend/src/components/ui/{textarea,status-badge,loading-overlay,card-info-item}.tsx returns 0 (no raw palette utilities in new primitives — semantic tokens only). 5. Each new file has a sensible TypeScript surface: Textarea accepts all native textarea props plus error?: boolean; StatusBadge accepts variant: 'pending'|'active'|'resolved'|'dismissed' (or equivalent enum derived from current admin usage); PriorityBadge accepts priority: 'low'|'medium'|'high'|'critical'; LoadingOverlay accepts visible: boolean and renders absolute inset-0 bg-background/80 backdrop-blur-sm when visible. 6. cd frontend && npm test -- --run exits 0 (594 tests pass — no consumers swapped yet, so no test churn expected).
