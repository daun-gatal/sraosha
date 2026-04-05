/**
 * Shared heading styles using the app display font (--font-display).
 * Use these for page titles, section titles, and card/list titles.
 */

/** Primary page heading (h1), e.g. Contracts, Data Quality */
export const PAGE_TITLE =
  'font-[family-name:var(--font-display)] text-3xl font-semibold tracking-tight'

/** Section heading in forms/cards (h2), e.g. New connection */
export const SECTION_TITLE = 'font-[family-name:var(--font-display)] text-lg font-semibold'

/** Muted panel subsection (h2), e.g. Guided builder, Details, Basics */
export const SUBSECTION_TITLE =
  'font-[family-name:var(--font-display)] text-sm font-semibold text-[var(--color-ink-muted)]'

/** List or card primary name (h3) */
export const CARD_TITLE = 'font-[family-name:var(--font-display)] text-base font-semibold'

/** Inline field group label that should read as a title (e.g. Contract YAML) */
export const FIELD_GROUP_LABEL =
  'font-[family-name:var(--font-display)] text-sm font-semibold text-[var(--color-ink)]'
