# AI Chatbot Framework

A self-hosted AI agent for people who don't write code. The interface is a precise, quiet workspace
borrowing the discipline of tools like Linear (not their look): dark first, hairline structure, lists you can scan, and every
action one keystroke away. It is set larger than most productivity tools (16px text, 40px controls)
because the people using it are not power users, and comfort beats density.

## Principles

1. **Quiet chrome, loud content.** Surfaces step by lightness only (`bg` → `bg-raised` →
   `bg-elevated`). Structure comes from 1px `border` hairlines, not shadows or colour. Shadows are
   reserved for things that float: `shadow-pop` (command menu, menus) and `shadow-composer`.
2. **One accent, from the logo.** The logo's green ring (`brand-signal`, #4a946a) sets the palette;
   `accent` is that green stepped lighter for dark and deeper for light so it passes contrast. It marks the single primary action on a screen, focus, the
   selected indicator and the agent's live wave. Everything else is neutral. Success uses
   `accent-text`; errors `danger`; attention `warning`.
3. **Keyboard first, mouse friendly.** Every primary action has a shortcut shown as a `Kbd`
   (`⌘K` command menu, `C` new chat, `G then F` files…). Targets are still ≥ 40px.
4. **Show the work.** Agent tool calls are rows (`ToolStep`) with a state, a plain verb, a mono
   detail and a duration, never hidden behind spinners.
5. **Big enough to read.** `body` is 16px, agent messages `body-lg` 17px; `caption` 13px is the floor.

## Content

Plain words, sentence case, verbs on buttons ("New chat", "Upload skill", "Run now"). Name things by
what people recognise: *Files*, *Skills*, *Tasks*, *Connections*. Errors say what happened and what to
do: "Could not reach the model. Check the server address in Settings." No exclamation marks, no emoji.

## Visual foundations

- **Colour** — dark is the primary theme; light mirrors it. Text: `text` (primary), `text-muted`
  (secondary), `text-faint` (meta only). Selected rows use `bg-selected` plus `text`.
- **Type** — Geist for UI, Geist Mono for commands, paths and tool output. Titles are 600 weight with
  tight tracking (`title-1`, `title-2`); the empty-chat greeting is the only `display`.
- **Space** — 4px grid: rows pad `space-3`, cards `space-6`, pages `space-8` at the sides and
  `space-12` on top. Content never exceeds `content-width` (880px).
- **Radius** — `radius-md` for controls and rows, `radius-lg` for cards, composer and command menu,
  `radius-full` for dots and the send button.
- **Motion** — 120–160ms ease-out for hover and selection; the command menu scales from 98%. The
  brand wave "speaks" (vertical breathing) only while the agent works. Respect reduced motion.

## Iconography

1.75px stroke, 20px default size, round caps and joins, drawn inline as SVG in `currentColor`.
The logo is a green ring holding a zigzag wave (three peaks, four valleys, ends at mid-height), drawn
with round caps in `brand-signal`, beside the wordmark "AI Chatbot Framework" in `brand-ink`. It sits on
the surface directly: no tile, no outline, no other colour. Mark SVG (24-unit box):
`<circle cx="12" cy="12" r="10.25"/>` + `<polyline points="4.4,12 6.3,15.8 8.2,8.4 10.1,15.8 12,8.4 13.9,15.8 15.8,8.4 17.7,15.8 19.6,12"/>`.
While the agent works, only the wave breathes (`acf-wave-live`).

## Layout

Three columns at most: sidebar (`sidebar-width`, `bg-raised`, right `border`), main panel (`bg`),
optional inspector (file preview). Page header: `title-1` on the left, actions right, then content.
Under 760px the sidebar becomes a drawer over `scrim` and the composer stays pinned to the bottom.

## Components

Button, Input, Kbd, Badge, NavItem, ListRow, ToolStep, Composer, CommandMenu. Their styles live in
`components/bundle.css` as `.acf-*` classes built only from these tokens; copy them, don't restyle.
