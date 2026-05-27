---
name: screenshot-interaction
description: Use when a user provides, references, or asks to implement from a UI screenshot, mockup, reference image, screen recording frame, Figma screenshot, app screenshot, sidebar/menu/navigation screenshot, dashboard screenshot, or visual bug screenshot, especially when Codex must infer interactive behavior rather than copy the visible static state. Trigger for screenshot-to-code, image-to-code, screenshot analysis, UI reverse engineering, visual implementation, sidebar/nav/menu/tabs/accordion/tree/drawer/modal/dropdown screenshots, and complaints that Codex made a static expanded/selected/success state instead of implementing collapsible, closeable, selectable, hover, active, keyboard, loading, empty, error, disabled, responsive, or compact states.
---

# Screenshot Interaction

Treat every screenshot as one captured state of an interactive system, not the whole UI contract. The job is to infer the component roles, controls, state transitions, and missing states before writing or changing code.

Use this skill with design/frontend skills. This skill owns the interaction inference; the design skill owns visual taste.

## Core Rule

Do not implement only the state visible in the screenshot when the surface is an app UI, component, dashboard, settings page, navigation system, form, sidebar, drawer, menu, tree, tabs, accordion, modal, popover, or toolbar.

Before implementation, write a short **Interaction Read**:

```text
Interaction Read:
- Components: ...
- Current visible state: ...
- Likely controls: ...
- Missing states to implement: ...
- Ambiguities: ...
```

Keep it concise. If ambiguity changes product behavior or data shape, ask one question. If ambiguity is normal UI convention, make the conventional choice and continue.

## Workflow

1. **Identify component roles**
   - Name the likely pattern: sidebar, navigation drawer, tree nav, accordion, tabs, menu button, modal, popover, table, form, command palette, split pane, toolbar, card list, empty state.
   - Separate structure from state: "all nav groups expanded" is state; "sidebar with collapsible groups" is structure.

2. **Find affordance clues**
   - Look for icons: chevrons, carets, disclosure triangles, X/close, hamburger, kebab, plus/minus, handles, resizers, selected markers, badges, switches, segmented controls.
   - Look for layout hints: nested indentation, grouped labels, active rows, count badges, hover-like backgrounds, scrims, handles, sticky regions, clipped text, overflow menus.
   - If an item looks like a control, assume it has at least default, hover, active/focus, and disabled states unless impossible.

3. **Build the state matrix**
   - For each interactive component, list current state plus required alternate states.
   - Include only states that matter for the task, but never omit obvious inverse states such as expanded/collapsed, open/closed, selected/unselected, checked/unchecked, enabled/disabled, loading/loaded, empty/populated, error/success.

4. **Map triggers and persistence**
   - Define what changes state: click, keyboard, route change, search input, resize, outside click, escape, drag, hover, focus.
   - Decide whether state is local, URL/route-derived, persisted, or server-derived. Prefer local state for visual-only controls unless the repo already has a state convention.

5. **Implement behavior before polish**
   - Preserve the screenshot's visual state as one reachable state, not the only state.
   - Implement accessible semantics: buttons for controls, labels, focus states, keyboard support, and ARIA attributes when appropriate.
   - Do not replace real controls with static divs to match pixels.

6. **Verify reachable states**
   - Use the in-app browser/browser automation when testing a web UI.
   - Capture or inspect at least the screenshot state and one inverse state for each central interaction.
   - For sidebars/nav, verify expanded and collapsed groups, active item, hover/focus, compact/mobile behavior, and overflow if relevant.

## Screenshot-to-State Checklist

Use this compact checklist before code:

- **Visible state**: what exact state is captured?
- **Inverse state**: what would the closed/collapsed/unselected/empty/error version look like?
- **Control entry point**: which visible element toggles or opens it?
- **Feedback**: what changes on hover, focus, active, selected, disabled?
- **Keyboard**: Tab order, Enter/Space, Escape, arrow keys where pattern requires them.
- **Responsive**: desktop, narrow/mobile, overflow, long localized labels.
- **Data states**: loading, empty, error, partial data, permission-disabled.

If a screenshot shows every group expanded, implement expand/collapse unless the prompt explicitly says "static mockup only".

## Pattern Defaults

Load [references/ui-patterns.md](references/ui-patterns.md) when the screenshot includes navigation, disclosure, accordion, tree, tabs, menu button, drawer, sidebar, modal, popover, form, table, toolbar, split pane, or when you are unsure which states are conventional.

High-confidence defaults:

- Chevron/caret beside a label means expandable/collapsible.
- X means close/dismiss.
- Hamburger means open navigation or collapse/expand navigation.
- Kebab/ellipsis means overflow menu.
- Indentation means hierarchy; hierarchy usually has expanded/collapsed states.
- Active row highlight means there are selected and unselected states.
- Badge/count means item data can vary and must not resize layout unpredictably.
- Scrim/backdrop means overlay open state plus closed state and outside-click/Escape behavior.
- Resize handle or split boundary means draggable or at least resizable panes.

## Implementation Guardrails

- Prefer existing component libraries and patterns in the repo.
- Use structured state, not CSS-only hacks, when state affects DOM, labels, routes, ARIA, or keyboard behavior.
- Do not add fake controls that look clickable but do nothing.
- Do not hide missing state behavior behind comments or TODOs unless the user explicitly asked for a static prototype.
- When creating test IDs or semantic hooks, name the state: `sidebar-group-expanded`, `sidebar-toggle`, `nav-item-active`, `menu-open`.
- If time is limited, implement fewer components with complete state rather than many static replicas.

## Handoff

In the final response, say which screenshot states were implemented and how they were verified. If any visible affordance remains static, name it plainly.
