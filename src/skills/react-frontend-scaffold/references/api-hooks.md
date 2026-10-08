# Query/mutation hook conventions

Confirm the repo's actual data-fetching stack before writing a new hook - common
combinations in this style are TanStack Query (or SWR, or RTK Query) over a
typed `fetch` wrapper, a generated SDK's own hooks, or a hand-rolled
`useEffect`-based hook in older codebases. The example below assumes TanStack
Query over a typed client, since that's the most common modern combination -
adapt the shape to whatever the repo's reference feature actually uses.

```ts
// use{Feature}.ts
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "../../lib/api/client"; // match the repo's actual client import path

export interface Widget {
  id: string;
  name: string;
}

async function fetchWidgets(): Promise<Widget[]> {
  const { data } = await apiClient.GET("/widgets");
  return data as Widget[];
}

export function useWidgets() {
  return useQuery({ queryKey: ["widgets"], queryFn: fetchWidgets });
}
```

```ts
// widgetMutations.ts
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../../lib/api/client";
import type { Widget } from "./useWidgets";

async function createWidget(name: string): Promise<Widget> {
  const { data } = await apiClient.POST("/widgets", { body: { name } });
  return data as Widget;
}

export function useCreateWidgetMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createWidget,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["widgets"] }),
  });
}
```

## Error handling

Check how the repo's API client surfaces failures - a common pattern is a typed
error class (status code, optional field-level validation errors, optional
correlation/trace id) thrown by a fetch-level interceptor, caught by
`instanceof` checks in forms/components. If the repo already has a global
query/mutation error handler (e.g. toasting unexpected 5xx errors), don't
duplicate that handling in every new hook - only handle the error shapes the new
feature displays differently from the default.

## Auth/CSRF headers

If the repo's client attaches auth or CSRF headers via a middleware/interceptor,
don't reimplement that in feature code - just call the client normally. Confirm
this by reading the client module directly rather than assuming; some repos
handle it per-request instead.

## Query keys

Match the repo's existing convention exactly - plain array literals scoped by
feature (`["widgets"]`) are common in simpler codebases; a query-key-factory
function/object is common in larger ones. Export a key as a named const only
when another feature or route genuinely needs to reference the same key. Don't
introduce a query-key-factory abstraction if the rest of the repo uses flat
literals, or vice versa.

## Pagination

Offset pagination (`page`/`pageSize`/`totalCount`) via the query library's
infinite-query primitive is common; so is cursor pagination. Check which the
backend's endpoint actually returns before assuming - the shape of
`getNextPageParam` (or equivalent) depends entirely on it. Match whether the
repo's existing paginated lists use an explicit "Load more" button or an
infinite-scroll observer; don't switch UX patterns for one new feature.

## Cross-feature reads

Don't call another feature's fetch function or endpoint directly. Import its
public hook through its barrel export instead, matching however the repo's
existing features already consume each other (if they do at all).
