import type { PortfolioRankingEntry } from '../types/prioritization'

/**
 * Phase 25 — pure reshaping of already-computed WSJF portfolio entries
 * (GET /api/v1/prioritization/portfolio, unchanged since Phase 17) into
 * the PRD's §15 "WSJF breakdown (stacked bar of the four inputs)"
 * visualization. Never recomputes anything: `business_value`/
 * `time_criticality`/`risk_reduction_opportunity_enablement`/`job_size`
 * are copied verbatim from each project's already-returned `breakdown`
 * (app/domain/prioritization.py::calculate_wsjf_score's own fixed
 * criterion keys — WSJF_CRITERION_KEYS). Only fully-scored projects
 * (`score !== null`, which calculate_wsjf_score guarantees means every
 * one of the four criteria is present) are included — a partially-scored
 * project has an incomplete breakdown that would render as a misleading
 * partial bar, so it's left out rather than plotted with a fabricated
 * zero.
 */

export interface WsjfBreakdownRow {
  project_id: string
  project_name: string
  business_value: number
  time_criticality: number
  risk_reduction_opportunity_enablement: number
  job_size: number
}

const WSJF_KEYS = [
  'business_value',
  'time_criticality',
  'risk_reduction_opportunity_enablement',
  'job_size',
] as const

export function buildWsjfBreakdown(items: PortfolioRankingEntry[]): WsjfBreakdownRow[] {
  return items
    .filter((item) => item.score !== null && WSJF_KEYS.every((key) => key in item.breakdown))
    .map((item) => ({
      project_id: item.project_id,
      project_name: item.project_name,
      business_value: Number(item.breakdown.business_value),
      time_criticality: Number(item.breakdown.time_criticality),
      risk_reduction_opportunity_enablement: Number(
        item.breakdown.risk_reduction_opportunity_enablement,
      ),
      job_size: Number(item.breakdown.job_size),
    }))
}
