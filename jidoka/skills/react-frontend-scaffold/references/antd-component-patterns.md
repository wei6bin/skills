# Ant Design component patterns (per feature)

Read this whenever you build a feature in an app that uses Ant Design - whether
the setup came from `references/antd-app-setup.md` or the repo already used antd
before you arrived. In an existing antd repo, its own theme and conventions
still outrank this file; use the mapping below only to fill gaps.

## Which component for which job

| UI job | Reach for | Notes |
| --- | --- | --- |
| Page scaffold | `Flex vertical` + a page-header block | See below - every page uses the same one |
| Tabular list | `Table` | Built into antd; no extra package, sorting/filtering/paging included |
| Non-tabular list | `List` + `List.Item` | Anything row-shaped but not columnar |
| Create/edit, short form | `Modal` holding a `Form` | Roughly ≤5 fields and no nested resources - mind the remount trap below |
| Create/edit, taller form | `Drawer` | More vertical room than a Modal without leaving the page |
| Create/edit, long form | Its own route | Deep-linkable, survives refresh |
| Text input | `Form.Item` wrapping `Input` | Label and error render themselves - never hand-wire `help`/`validateStatus` inside a Form |
| Submit button | `<Button type="primary" htmlType="submit" loading={isPending}>` | `htmlType`, not `type` - `type` is antd's visual variant |
| Transient feedback | `App.useApp().message` | Never the static `message` import - see below |
| Destructive confirm | `Popconfirm` on a row action, `modal.confirm()` for heavier ones | Never `window.confirm` |
| Loading | `Skeleton active`, or `Table`'s own `loading` prop | Not a bare centred `Spin` |
| Empty | `Empty` with real copy + a primary action | Never the default "No Data" |
| Error | `Alert type="error"` with a retry in `action` | Say what failed and what to do |
| Status / category | `Tag` | Colour alone must never carry the meaning |
| Icon-only button | `Button type="text" icon={...}` + `aria-label` | The icon carries no accessible name |

## Page composition

Every page opens the same way, so the app feels like one product:

```tsx
<Flex vertical gap="large">
  <Flex align="center" justify="space-between" gap="middle">
    <div>
      <Typography.Title level={3} style={{ marginBlock: 0 }}>Notes</Typography.Title>
      <Typography.Text type="secondary">Everything you've captured, newest first.</Typography.Text>
    </div>
    <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>New note</Button>
  </Flex>

  {/* content */}
</Flex>
```

`Flex` (antd 5.10+) is the layout primitive - `gap` takes the token sizes
(`"small" | "middle" | "large"`) or a number. `Space` is for inline runs of
controls (a row of buttons in a table cell), not page layout: it wraps every
child in its own `div`, which breaks flex/grid children and full-width inputs.
Reach for `Row`/`Col` only for genuinely two-dimensional layouts.

`Typography.Title` ships with heavy default margins that collapse page rhythm -
zero them when the surrounding `Flex` already owns the spacing.

## Lists: Table or List

`Table` is the default, and unlike most component libraries it costs nothing
extra - sorting, filtering, pagination, row selection, expandable rows, and
fixed columns are all in antd core.

```tsx
const columns: TableColumnsType<Note> = [
  { title: "Title", dataIndex: "title", key: "title", sorter: true },
  { title: "Status", dataIndex: "status", key: "status",
    render: (status: NoteStatus) => <Tag color={STATUS_COLOR[status]}>{STATUS_LABEL[status]}</Tag> },
];

<Table<Note>
  rowKey="id"
  columns={columns}
  dataSource={notes}
  loading={isLoading}
  scroll={{ x: "max-content" }}
  pagination={{ pageSize: 25, showSizeChanger: true }}
/>
```

- **`rowKey` is the trap that bites first.** It defaults to a `key` field on
  each row, which API data almost never has. Without it you get React key
  warnings, and row selection/expansion silently target the wrong rows.
- Define `columns` outside the component (or in `useMemo` with stable handler
  refs). A fresh array every render resets column widths and any uncontrolled
  sort state.
- `dataSource` is paginated **client-side** by default. For server-side paging,
  pass only the current page's rows plus a controlled
  `pagination={{ current, pageSize, total }}` and an `onChange` - supplying a
  page slice without `total` shows one page's worth of rows and a pager that
  thinks that's everything. See `references/api-hooks.md` for the hook side.
- `scroll={{ x: "max-content" }}` keeps a wide table scrolling inside itself
  instead of pushing the page sideways.
- For thousands of rows without paging, `virtual` plus a fixed `scroll.y` -
  check the installed version supports it before relying on it.
- Row actions go in a `render` column as real buttons
  (`<Space><Button type="link">Edit</Button><Popconfirm …/></Space>`), not click
  handlers on text.

Drop to `List` when the data isn't columnar - a feed, cards, anything where a
row is a paragraph rather than a set of fields.

## Forms: antd's own `Form`

For greenfield. In an existing repo, match whatever its forms already do - see
`references/forms-and-optimistic-ui.md`.

`Form.Item` is the reason to use antd's form rather than bolting a third-party
one on: it owns the label, the required mark, validation, error text, and the
accessible wiring between them. Adding `react-hook-form` on top means a
`<Controller>` around nearly every antd control, because they're all controlled
components rather than native inputs.

```tsx
interface NoteFormValues { title: string; body?: string }

export function AddNoteForm({ onDone }: { onDone: () => void }) {
  const [form] = Form.useForm<NoteFormValues>();
  const [formError, setFormError] = useState<string | null>(null);
  const createNote = useCreateNoteMutation();

  const onFinish = async (values: NoteFormValues) => {
    setFormError(null);
    try {
      await createNote.mutateAsync(values);
      form.resetFields();
      onDone();
    } catch (error) {
      if (isApiError(error) && error.errors) {
        form.setFields(
          Object.entries(mapFieldErrors(error.errors))
            .map(([name, message]) => ({ name, errors: [message] })),
        );
        return;
      }
      setFormError("Couldn't save the note. Try again.");
    }
  };

  return (
    <Form form={form} layout="vertical" onFinish={onFinish} requiredMark="optional">
      {formError && <Alert type="error" showIcon title={formError} style={{ marginBlockEnd: 16 }} />}

      <Form.Item<NoteFormValues>
        name="title"
        label="Title"
        rules={[
          { required: true, message: "Title is required" },
          { max: 120, message: "Keep the title under 120 characters" },
        ]}
      >
        <Input />
      </Form.Item>

      <Form.Item<NoteFormValues> name="body" label="Body"
        rules={[{ max: 2000, message: "Keep the body under 2000 characters" }]}>
        <Input.TextArea rows={3} />
      </Form.Item>

      <Button type="primary" htmlType="submit" loading={createNote.isPending}>Save note</Button>
    </Form>
  );
}
```

- **`Form.Item` with a `name` must wrap exactly one control**, and clones it
  with `value`/`onChange`. Wrapping the input in a `<div>`, or putting two
  inputs in one named item, silently unbinds the field - no error, just a value
  that never updates. Multiple related fields need `Form.Item` nesting or
  `Form.List`.
- **Server-side validation errors go through
  `form.setFields([{ name, errors: [msg] }])`**, so backend and client messages
  land in the same place under the same field. antd has no root-error slot, so
  form-level failures (a conflict, a generic 500) need local state rendered as
  an `Alert` above the fields.
- `onFinish` only fires once the rules pass; there's no need to check validity
  yourself. `onFinishFailed` is for scrolling to the first error on long forms
  (`scrollToFirstError`).
- **Inside a `Modal`, the form stays mounted after close**, so opening it on a
  second row shows the first row's values. Set the modal's destroy-on-close prop
  (named `destroyOnClose` in older 5.x, `destroyOnHidden` since - check the
  installed types), or reset explicitly in the close handler.
- `Form.useForm()`'s instance must reach a `<Form form={...}>` before you call
  `setFieldsValue` on it, or antd warns that the instance isn't connected to any
  Form element. Pushing values in for an edit form belongs in an effect after
  mount, or in `initialValues` on a freshly-mounted form.
- If the repo wants one schema shared with the backend contract, keep zod as the
  source of truth and bridge it with a single `rules: [{ validator }]` per field
  rather than replacing antd's form.
- Give every field a `label`. It is the accessible name, it's what
  `getByLabelText` finds in tests, and antd generates the `id`/`htmlFor` pair
  from `name` for you.

## `message`, `modal`, `notification` - always via `App.useApp()`

```tsx
const { message, modal } = App.useApp();

await deleteNote.mutateAsync(id);
message.success("Note deleted");
```

The statics you can import directly (`import { message } from "antd"`) render
through their own React root, outside `ConfigProvider`. They ignore your theme
and locale - wrong colours in dark mode - and React warns about the detached
render. Mount one `<App>` at the root (see `references/antd-app-setup.md`) and
take them from the hook everywhere else. `Modal.confirm`, `notification.open`,
and `message.*` all have this problem and all have the same fix.

Confirm on success only where the result isn't visible - a row appearing in a
list is its own confirmation, and a toast saying "Note created" on top of the
note you can already see is noise. Toast the things you can't see: deletes,
background saves, copy-to-clipboard.

## Loading, empty, and error states

All three are part of the feature, not polish to add later. A list page has four
renderable states and the feature isn't done until all four exist.

```tsx
if (isLoading) return <Skeleton active paragraph={{ rows: 6 }} />;

if (error) return (
  <Alert
    type="error"
    showIcon
    title="Couldn't load notes."
    description="The server didn't respond. Your notes are safe."
    action={<Button size="small" onClick={() => refetch()}>Retry</Button>}
  />
);

if (!notes.length) return (
  <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No notes yet.">
    <Button type="primary" onClick={openCreate}>Create your first note</Button>
  </Empty>
);
```

- For a tabular list, prefer `Table`'s own `loading` prop over swapping in a
  `Skeleton` - the header and column widths stay put instead of the layout
  jumping when data lands. `Table` also renders `Empty` itself when `dataSource`
  is empty; pass your own through `locale={{ emptyText }}` so it gets real copy
  and an action.
- `Skeleton active` gives the shimmer;
  `Skeleton.Input`/`Skeleton.Button`/`Skeleton.Image` build a placeholder shaped
  like the real result. A centred `Spin` tells the user nothing about what's
  coming.
- **`Alert` renders `title` and `description` props, not children** (`title`
  is `message` before antd 6). Passing the text as children renders an empty
  alert.
- Error and empty copy follows the same rule as the rest of the UI: say what
  happened and what to do next. "Error" and "No Data" do neither.

## Styling rules

- Read design values from `const { token } = theme.useToken()` -
  `token.colorTextSecondary`, `token.paddingLG`, `token.colorBorderSecondary`.
  Never a raw hex or `px` outside `theme.ts`.
- Layout spacing comes from `Flex gap` / `Space size` / `Row gutter`, not
  per-element margins.
- Inline `style` for genuine one-offs. The second time the same styling appears,
  move it into `themeConfig.components.<Component>` and delete both copies -
  component tokens are antd's equivalent of a per-component style override, and
  they apply everywhere including inside portals.
- Use the semantic `styles={{ body: {...} }}` / `classNames={{ header: "..." }}`
  props rather than the deprecated `bodyStyle`/`headStyle`-family props.
- Don't add emotion or styled-components to restyle antd - v5 already ships a
  CSS-in-JS runtime, and a second one doubles it for no gain. If a component
  genuinely needs custom CSS, CSS Modules referencing the CSS variables
  `cssVar: true` emits is enough.
- **Don't branch styling on `isDark`.** The algorithm already flipped every
  token; `token.colorBgContainer` is correct in both modes, while
  `isDark ? "#fff" : "#000"` is a second theme to maintain.
- A local `ConfigProvider` can scope a theme override to one subtree (a
  marketing banner, a print view). Reach for it before hand-styling a dozen
  components.

## Accessibility

Ant Design gets the hard parts right if you let it: `Form.Item` wires
label/error/`aria-describedby`, `Modal` traps focus and restores it on close,
`Menu` and `Table` are keyboard-navigable. Breaking that takes effort - usually
by dropping an `Input` outside a `Form.Item`, or by putting an `onClick` on a
`div` or a `Typography.Text`.

The three you still owe:

- Every icon-only `Button` needs an `aria-label`; antd icons are decorative and
  contribute no name.
- `Tag` colour needs a text or icon companion, since colour alone carries no
  meaning for a screen reader or a red-green colourblind user.
- A `Form.Item` without a `label` gives its control no accessible name - add
  one, and hide it visually if the design demands it, rather than shipping an
  unnamed input.
