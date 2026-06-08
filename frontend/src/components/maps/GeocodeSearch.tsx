import { useEffect, useRef, useState } from "react";
import { Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { geocodeAddress, type GeocodeResult } from "@/lib/geocode";

interface GeocodeSearchProps {
  placeholder?: string;
  onSelect: (result: GeocodeResult) => void;
}

/** Debounced address search (Nominatim) with a results dropdown. */
export function GeocodeSearch({ placeholder, onSelect }: GeocodeSearchProps) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<GeocodeResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (timer.current) clearTimeout(timer.current);
    if (query.trim().length < 3) {
      setResults([]);
      return;
    }
    timer.current = setTimeout(async () => {
      setLoading(true);
      const r = await geocodeAddress(query);
      setResults(r);
      setOpen(true);
      setLoading(false);
    }, 600);
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, [query]);

  return (
    <div className="relative">
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={query}
          placeholder={placeholder ?? "Search an address…"}
          className="pl-9"
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => results.length && setOpen(true)}
        />
        {loading ? (
          <span className="absolute right-3 top-1/2 -translate-y-1/2">
            <Spinner />
          </span>
        ) : null}
      </div>
      {open && results.length > 0 ? (
        <ul className="absolute z-[1000] mt-1 max-h-60 w-full overflow-y-auto rounded-lg border border-border bg-popover p-1 shadow-md">
          {results.map((r, i) => (
            <li key={`${r.lat}-${r.lng}-${i}`}>
              <button
                type="button"
                className="w-full rounded-md px-3 py-2 text-left text-sm hover:bg-accent hover:text-accent-foreground"
                onClick={() => {
                  onSelect(r);
                  setQuery(r.label.split(",").slice(0, 2).join(", "));
                  setOpen(false);
                }}
              >
                {r.label}
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
