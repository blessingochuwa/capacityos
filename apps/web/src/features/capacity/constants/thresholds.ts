/**
 * The single, documented threshold used anywhere in the frontend to turn a
 * capacity result into a status label. Over-allocation and null utilization
 * are hard facts already computed by the backend (never guessed here) — see
 * ../utils/presentation.ts::getCapacityStatus. AT_CAPACITY_MIN is the one
 * number this app invents, so it lives here, named once, and is easy to
 * change without hunting through components.
 *
 * utilization at or above this (and not over-allocated) is labeled
 * "At capacity" rather than "Under capacity" — 90% leaves roughly a 10%
 * buffer for the meetings/admin/context-switching overhead CLAUDE.md §13
 * expects sustainable capacity to reserve. Below this is "Under capacity".
 */
export const AT_CAPACITY_MIN = 0.9
