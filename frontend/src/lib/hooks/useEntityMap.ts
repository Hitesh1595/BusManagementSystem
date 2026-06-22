import { useQueries } from "@tanstack/react-query";

/**
 * Resolve a set of foreign-key ids to their full entities via per-id GETs,
 * deduped and cached by react-query.
 *
 * Use this instead of fetching a whole (100-row capped) list just to build an
 * id→name map: that map silently loses entries once a school has more than one
 * page of students/users/etc., so cards fall back to "Student" / "A user". With
 * a paginated parent list this only fetches the ≤pageSize ids actually on screen,
 * and the single-resource caches are shared with detail views.
 */
export function useEntityMap<T extends { id: string }>(
  ids: Array<string | null | undefined>,
  fetchById: (id: string) => Promise<T>,
  queryKeyPrefix: string,
  staleTime = 60_000,
): Map<string, T> {
  const uniqueIds = [...new Set(ids.filter((x): x is string => !!x))];

  const results = useQueries({
    queries: uniqueIds.map((id) => ({
      queryKey: [queryKeyPrefix, id],
      queryFn: () => fetchById(id),
      staleTime,
    })),
  });

  const map = new Map<string, T>();
  results.forEach((r, i) => {
    if (r.data) map.set(uniqueIds[i], r.data);
  });
  return map;
}
