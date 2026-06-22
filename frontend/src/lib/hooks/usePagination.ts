import { useEffect, useState } from "react";

/**
 * Offset/limit pagination state for list views.
 *
 * Pass a `resetKey` built from the active filters/search (e.g. `${tab}` or
 * `${role}:${q}`) so changing a filter snaps back to the first page — otherwise
 * you can be left on an out-of-range offset staring at an empty page.
 */
export function usePagination(pageSize = 25, resetKey?: unknown) {
  const [offset, setOffset] = useState(0);

  useEffect(() => {
    setOffset(0);
  }, [resetKey]);

  return { limit: pageSize, offset, setOffset };
}
