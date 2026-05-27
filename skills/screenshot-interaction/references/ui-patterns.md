# UI Pattern State Defaults

Use this reference when a screenshot includes common interactive UI patterns. These defaults are adapted from mature accessibility and design-system conventions, especially WAI-ARIA Authoring Practices for disclosure, accordion, menu button, tree view, tabs, and dialog patterns, plus common app-shell guidance from Apple, Material, and Carbon-style navigation systems.

## General Heuristic

A screenshot is a single state. For any visible interactive pattern, infer:

- **Role**: what kind of component this is.
- **Current state**: what the screenshot shows now.
- **Inverse state**: what must also exist.
- **Trigger**: click, keyboard, route, hover, input, resize, outside click.
- **Semantics**: accessible element, label, focus, ARIA when needed.
- **Persistence**: local, route-derived, saved preference, server data.

## Sidebar / Navigation Drawer

Common states:

- Expanded sidebar, collapsed sidebar, mobile drawer open, mobile drawer closed.
- Active item, inactive item, hover/focus item.
- Group expanded, group collapsed.
- Item with children, item without children.
- Overflow menu visible, overflow menu hidden.
- Long labels clipped, wrapped, or tooltiped depending on product style.

Implementation defaults:

- Sidebar collapse toggle is a real button with an accessible label.
- Active route is route-derived when the app has routing.
- Group disclosure uses a button, not a div.
- Chevron direction reflects expansion.
- On mobile, prefer drawer overlay with backdrop, Escape close, outside-click close, and focus return.
- Preserve the screenshot's fully expanded state as a reachable state, but also implement collapsed groups if any chevron or hierarchy is visible.

Do not:

- Hard-code all groups open because the screenshot is open.
- Make chevrons decorative when they sit next to grouped nav labels.
- Collapse the sidebar without considering icons-only, tooltip labels, or mobile drawer behavior.

## Disclosure / Accordion

Common states:

- Expanded, collapsed.
- Single-open accordion, multi-open accordion.
- Focused trigger, disabled trigger.
- Content loaded, loading, empty, error if content is data-backed.

Implementation defaults:

- Trigger is a button.
- Use `aria-expanded` and `aria-controls` when the content panel is controlled by the trigger.
- Chevron/caret rotates or changes direction.
- Space/Enter toggles.
- Preserve content in DOM only if that matches the repo/accessibility pattern; otherwise unmounting is acceptable for simple UI.

Question only when single-open vs multi-open materially changes the requested behavior. Otherwise choose the common product default: nav groups can be multi-open; FAQ accordions are often single-open or multi-open depending on existing repo pattern.

## Tree / Tree Navigation

Common states:

- Node expanded, collapsed, leaf.
- Node selected, focused, disabled.
- Parent partially loaded, loading children, empty children.

Implementation defaults:

- Indentation plus chevrons implies a tree or nested nav.
- Arrow keys should work when building a real tree widget. If the repo uses normal nav links, at minimum Tab, Enter, Space, focus, and click must work.
- Selected node is distinct from focused node.
- Expanding a parent should not automatically select it unless the product already does that.

## Tabs / Segmented Controls

Common states:

- Selected tab, unselected tab, focused tab, disabled tab.
- Empty panel, loading panel, error panel, populated panel.
- Overflow tabs on narrow width.

Implementation defaults:

- Only one tab selected in a normal tablist.
- Selected tab controls panel content.
- Keyboard arrow navigation is expected for a full tab pattern; click and Tab focus are minimum for simple segmented controls.
- Do not make tab-like labels static if panels are implied.

## Menu Button / Dropdown / Kebab

Common states:

- Closed, open.
- Item hover/focus, disabled item, destructive item.
- Submenu open/closed if nested.
- Empty or permission-filtered menu.

Implementation defaults:

- Trigger is a button.
- Trigger exposes open state with `aria-expanded` where appropriate.
- Escape closes.
- Outside click closes.
- Focus returns to trigger after close.
- Menu position handles viewport edges.

Do not:

- Render ellipsis/kebab as a static icon.
- Put menu items in the DOM without keyboard/focus handling if they are visually a menu.

## Modal / Dialog / Drawer / Popover

Common states:

- Closed, opening, open, closing.
- Focus inside, focus restored to opener.
- Dismiss by close button, Escape, and sometimes backdrop depending on risk.
- Loading, empty, error, success inside the overlay.

Implementation defaults:

- Overlay has a visible close affordance unless it is an intentionally blocking flow.
- Dialog title is programmatically associated.
- Modal traps focus; non-modal popover does not.
- Destructive confirmations require clear primary/secondary actions and do not rely on color alone.

## Forms / Inputs

Common states:

- Empty, filled, focused, disabled, readonly.
- Valid, invalid, submitting, submitted, server error.
- Placeholder visible, helper text, error text.

Implementation defaults:

- Label above or clearly associated with input.
- Placeholder is not the only label.
- Error text is near the field and linked when possible.
- Submit button has loading/disabled states.

## Tables / Lists / Cards

Common states:

- Loading skeleton, empty, populated, filtered-empty, error.
- Row hover/focus, selected row, expanded row.
- Sorting, pagination, bulk selection, overflow actions.

Implementation defaults:

- If checkboxes are visible, implement selected and unselected states.
- If row chevrons are visible, implement expanded row/detail state.
- If column headers show sort indicators, implement sort state or remove the indicator.
- Preserve stable dimensions for badges, buttons, and counts so data changes do not shift layout.

## Toolbar / Icon Button

Common states:

- Default, hover, active/pressed, focused, disabled.
- Toggle on/off for formatting, filters, view modes.
- Tooltip visible on hover/focus when icon meaning is not obvious.

Implementation defaults:

- Use a button with accessible label for every icon control.
- If the icon represents a mode, expose pressed/selected state.
- Tooltips do not replace labels for assistive technology.

## Split Pane / Resizable Panels

Common states:

- Default size, collapsed pane, expanded pane, resizing, minimum width, maximum width.

Implementation defaults:

- Visible drag handle implies resize.
- If resizing is too much for scope, either implement a collapse toggle or remove the visual handle.
- Preserve content readability at min width and narrow viewport.

## Verification Prompts

Before handoff, test the most important inverse states:

- Can the expanded thing collapse?
- Can the open thing close?
- Can the selected thing become unselected or another item selected?
- Does keyboard focus reveal where the user is?
- Does Escape close overlays and menus?
- Does the mobile layout still expose the same actions?
- Do long labels and localized strings fit?

## Source Anchors

Use these only when deeper pattern confirmation is needed:

- WAI-ARIA APG disclosure, menu button, tree view, tabs, and dialog patterns: https://www.w3.org/WAI/ARIA/apg/patterns/
- Apple Human Interface Guidelines sidebars and disclosure controls: https://developer.apple.com/design/human-interface-guidelines/sidebars/ and https://developer.apple.com/design/human-interface-guidelines/disclosure-controls/
- Material Design navigation drawer: https://m2.material.io/components/navigation-drawer
- Carbon UI shell left panel and header: https://carbondesignsystem.com/components/UI-shell-left-panel/accessibility/ and https://carbondesignsystem.com/components/UI-shell-header/style/
