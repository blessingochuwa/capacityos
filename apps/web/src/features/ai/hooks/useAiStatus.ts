import { useQuery } from '@tanstack/react-query'
import { aiApi } from '../api/aiApi'

/** Read-only capability check — gates whether AI buttons render at all,
 * without ever triggering a real generation call itself (prompt: no AI call
 * on page load). Safe to call unconditionally from any page. */
export function useAiStatus() {
  return useQuery({
    queryKey: ['ai', 'status'],
    queryFn: () => aiApi.getStatus(),
  })
}
