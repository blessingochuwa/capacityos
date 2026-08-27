import { apiGet, apiPost } from '@/api/client'
import type {
  AIAskRequest,
  AIExplainPriorityRequest,
  AIExplainScenarioPriorityComparisonRequest,
  AIExplainScenarioRequest,
  AIExplainSignalRequest,
  AIExplainSnapshotComparisonRequest,
  AIResponseEnvelope,
  AIStatusRead,
  AISummaryRequest,
} from '../types/ai'

/** Thin typed wrappers over apps/api's AI endpoints
 * (apps/api/app/api/v1/ai.py). Every call here is explicitly user-triggered
 * (a button click) — never fired automatically on page load or on every
 * keystroke (CLAUDE.md §18 cost control). AIResponseEnvelope's `status`
 * field carries the "unavailable"/"error" soft-fail states; these never
 * throw for those cases, only for a genuine transport/HTTP failure. */
export const aiApi = {
  getStatus: () => apiGet<AIStatusRead>('/api/v1/ai/status'),

  summarize: (data: AISummaryRequest) =>
    apiPost<AIResponseEnvelope>('/api/v1/ai/summary', data),

  explainSignal: (data: AIExplainSignalRequest) =>
    apiPost<AIResponseEnvelope>('/api/v1/ai/explain-signal', data),

  explainScenario: (data: AIExplainScenarioRequest) =>
    apiPost<AIResponseEnvelope>('/api/v1/ai/explain-scenario', data),

  explainPriority: (data: AIExplainPriorityRequest) =>
    apiPost<AIResponseEnvelope>('/api/v1/ai/explain-priority', data),

  explainSnapshotComparison: (data: AIExplainSnapshotComparisonRequest) =>
    apiPost<AIResponseEnvelope>('/api/v1/ai/explain-snapshot-comparison', data),

  explainScenarioPriorityComparison: (data: AIExplainScenarioPriorityComparisonRequest) =>
    apiPost<AIResponseEnvelope>('/api/v1/ai/explain-scenario-priority-comparison', data),

  ask: (data: AIAskRequest) =>
    apiPost<AIResponseEnvelope>('/api/v1/ai/ask', data),
}
