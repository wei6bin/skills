# Forms and optimistic UI

## Check the repo's form pattern before choosing one

Common patterns in this style, roughly newest to oldest: React 19's
`useActionState` bound to a `<form action={...}>`, a form library
(`react-hook-form`, Formik), or manual `onSubmit` + `useState`. Match whichever
the repo's existing forms already use - don't introduce a new one for a single
feature.

**If the repo has no form pattern established yet**, use the form primitive that
belongs to its component library rather than bolting a third-party one on top.
In an Ant Design app that means antd's own `Form` + `Form.Item` - see
`references/antd-component-patterns.md` for the field wiring, since `Form.Item`
already owns the label, validation rules, error text, and the accessible wiring
between them, and every antd control is a controlled component that a
third-party form library would need a `<Controller>` wrapper for. The rest of
this file still applies: the error-mapping, reset, and optimistic-update
guidance below is independent of which form library you land on.

The example below assumes `useActionState`, since it needs no extra dependency
and is the current React-native pattern - read it for the shape of the error
handling even if you're using react-hook-form.

```tsx
interface WidgetFormState {
  fieldErrors: Record<string, string>;
}
const INITIAL_STATE: WidgetFormState = { fieldErrors: {} };

const [state, submitAction, isPending] = useActionState(
  async (_prev: WidgetFormState, formData: FormData): Promise<WidgetFormState> => {
    const name = String(formData.get("name") ?? "").trim();
    try {
      await createWidget.mutateAsync({ name });
      return INITIAL_STATE;
    } catch (error) {
      if (isApiError(error) && error.errors) {
        return { fieldErrors: mapFieldErrors(error.errors) };
      }
      return { fieldErrors: {} };
    }
  },
  INITIAL_STATE,
);
```

- Read fields with `formData.get(name)`, coerce explicitly
  (`String(... ?? "")`). Decide deliberately whether an empty optional field
  becomes `""` or `null` in the request body - match whatever the backend
  contract and the repo's existing forms already do.
- If the repo has a field-error-mapping helper (converting a validation-error
  payload into a `{ field: message }` shape, possibly also re-casing field
  names), reuse it rather than inlining the mapping in a new form.
- Distinguish field-level errors from form-level errors (a conflict, a generic
  failure) in state, and render form-level errors through whatever banner/alert
  component the repo's other forms already use.
- Match the repo's reset behavior on success - clearing via a form ref,
  resetting individual controlled inputs, or navigating away, whichever its
  existing forms already do.

## Optimistic add

If the repo's list-add flows use React's `useOptimistic`, follow that pattern: a
placeholder item (often with an id prefixed something like `optimistic-`) is
added to the optimistic list synchronously before the mutation is awaited, and
any interactive controls on that placeholder row are disabled until the real
item replaces it. If the repo instead does optimistic updates via direct
query-cache manipulation (`queryClient.setQueryData` in `onMutate`/`onError`),
match that instead - the two are not interchangeable, and mixing them in one
codebase creates inconsistent rollback behavior.

## Optimistic toggle - local state, not always `useOptimistic`

For a toggle/checkbox bound to a controlled value (not a list append), a
`useOptimistic` list-transform often isn't the right tool - some repos instead
track a local "pending" value set **synchronously in the same click handler**,
cleared once the mutation settles, so the control visually flips the instant
it's clicked rather than after a round trip. This matters beyond visual polish:
some E2E frameworks' checkbox-check assertions verify the state changed
immediately and don't retry, so a round-trip-dependent toggle can fail tests a
human wouldn't perceive as broken. Check whether the repo's existing toggles
already do this before choosing an approach for a new one.

## Full vs. partial updates

Check whether the backend's update endpoint expects the complete resource body
or a partial patch. Some frontends always send the full object on every update
(including single-field toggles) because the backend does a full replace;
sending a partial body against such a backend silently clobbers the other
fields. Match the repo's existing update calls' body shape exactly - don't
assume PATCH semantics without checking.
