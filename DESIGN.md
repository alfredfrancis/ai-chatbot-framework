---
name: "AI Chatbot Framework"
description: "A self-hosted AI agent for people who don't write code. Dark first; light mirrors it."
colors:
  bg: "#0b0c0f"
  bg-raised: "#111317"
  bg-elevated: "#16181d"
  bg-hover: "#1d1f25"
  bg-selected: "#24272e"
  border: "#22252b"
  border-strong: "#696c77"
  text: "#edeef0"
  text-muted: "#a0a3ab"
  text-faint: "#8b8e97"
  accent: "#5fb383"
  accent-fg: "#08200f"
  accent-text: "#74c597"
  accent-subtle: "#15271c"
  accent-2: "#7fd0d0"
  accent-2-subtle: "#132326"
  danger: "#ff7a70"
  danger-subtle: "#3a1716"
  warning: "#f5b04b"
  warning-subtle: "#3a2a10"
  brand-ink: "#edeef0"
  brand-signal: "#4a946a"
  scrim: "rgba(0,0,0,0.6)"
  bg-light: "#f7f7f8"
  bg-raised-light: "#ffffff"
  bg-elevated-light: "#ffffff"
  bg-hover-light: "#efeff2"
  bg-selected-light: "#e6e7ec"
  border-light: "#e3e3e8"
  border-strong-light: "#8c8e98"
  text-light: "#16171b"
  text-muted-light: "#5c5e68"
  text-faint-light: "#6a6c75"
  accent-light: "#2e7a50"
  accent-fg-light: "#ffffff"
  accent-text-light: "#2a7049"
  accent-subtle-light: "#e7f2eb"
  accent-2-light: "#1f6662"
  accent-2-subtle-light: "#dcf0f0"
  danger-light: "#c4161c"
  danger-subtle-light: "#fdecec"
  warning-light: "#995800"
  warning-subtle-light: "#fdf3e3"
  brand-ink-light: "#111114"
  scrim-light: "rgba(17,17,20,0.35)"
typography:
  display:
    fontFamily: "\"Geist Variable\", Geist, \"SF Pro Text\", system-ui, -apple-system, \"Segoe UI\", sans-serif"
    fontSize: "40px"
    fontWeight: 600
    lineHeight: "44px"
    letterSpacing: "-0.03em"
  title-1:
    fontFamily: "\"Geist Variable\", Geist, \"SF Pro Text\", system-ui, -apple-system, \"Segoe UI\", sans-serif"
    fontSize: "28px"
    fontWeight: 600
    lineHeight: "34px"
    letterSpacing: "-0.02em"
  title-2:
    fontFamily: "\"Geist Variable\", Geist, \"SF Pro Text\", system-ui, -apple-system, \"Segoe UI\", sans-serif"
    fontSize: "20px"
    fontWeight: 600
    lineHeight: "28px"
    letterSpacing: "-0.01em"
  body-lg:
    fontFamily: "\"Geist Variable\", Geist, \"SF Pro Text\", system-ui, -apple-system, \"Segoe UI\", sans-serif"
    fontSize: "17px"
    fontWeight: 400
    lineHeight: "27px"
  body:
    fontFamily: "\"Geist Variable\", Geist, \"SF Pro Text\", system-ui, -apple-system, \"Segoe UI\", sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: "24px"
  body-strong:
    fontFamily: "\"Geist Variable\", Geist, \"SF Pro Text\", system-ui, -apple-system, \"Segoe UI\", sans-serif"
    fontSize: "16px"
    fontWeight: 550
    lineHeight: "24px"
  small:
    fontFamily: "\"Geist Variable\", Geist, \"SF Pro Text\", system-ui, -apple-system, \"Segoe UI\", sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: "20px"
  caption:
    fontFamily: "\"Geist Variable\", Geist, \"SF Pro Text\", system-ui, -apple-system, \"Segoe UI\", sans-serif"
    fontSize: "13px"
    fontWeight: 500
    lineHeight: "18px"
    letterSpacing: "0.01em"
  code:
    fontFamily: "\"Geist Mono Variable\", \"Geist Mono\", ui-monospace, \"SF Mono\", Menlo, monospace"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: "22px"
rounded:
  sm: "6px"
  md: "10px"
  lg: "14px"
  full: "999px"
spacing:
  space-1: "4px"
  space-2: "8px"
  space-3: "12px"
  space-4: "16px"
  space-6: "24px"
  space-8: "32px"
  space-12: "48px"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.accent-fg}"
    typography: "{typography.body-strong}"
    rounded: "{rounded.md}"
    height: "40px"
    padding: "0 16px"
  button-secondary:
    backgroundColor: "{colors.bg-elevated}"
    textColor: "{colors.text}"
    typography: "{typography.body-strong}"
    rounded: "{rounded.md}"
    height: "40px"
    padding: "0 16px"
  button-ghost:
    textColor: "{colors.text-muted}"
    typography: "{typography.body-strong}"
    rounded: "{rounded.md}"
    height: "40px"
    padding: "0 16px"
  button-ghost-hover:
    backgroundColor: "{colors.bg-hover}"
    textColor: "{colors.text}"
  input:
    backgroundColor: "{colors.bg-elevated}"
    textColor: "{colors.text}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    height: "40px"
    padding: "0 12px"
  card:
    backgroundColor: "{colors.bg-elevated}"
    rounded: "{rounded.lg}"
    padding: "24px"
  badge:
    backgroundColor: "{colors.accent-subtle}"
    textColor: "{colors.accent-text}"
    typography: "{typography.caption}"
    rounded: "{rounded.sm}"
    height: "24px"
    padding: "0 8px"
  side-panel:
    backgroundColor: "{colors.bg-raised}"
    width: "400px"
---
# Design System: AI Chatbot Framework

<!-- Generated from design/tokens.json and design/README.md by frontend/scripts/build-tokens.mjs. Do not edit. -->

## Overview

A self-hosted AI agent for people who don't write code. The look is called **Signal**: a precise
workspace borrowing the discipline of tools like Linear (not their look). Dark first, hairline
structure, lists you can scan, and every action one keystroke away. It is set larger than most
productivity tools (16px text, 40px controls) because the people using it are not power users, and
comfort beats density. The one signature move: the logo's wave is alive only while the agent works.

Principles:

1. **Quiet chrome, loud content.** Surfaces step by lightness (`bg` → `bg-raised` → `bg-elevated`) and
   structure comes from 1px `border` hairlines.
2. **One accent, from the logo.** Everything is neutral except the green that marks the one primary
   action, focus, selection and live state.
3. **Keyboard first, mouse friendly.** Every primary action has a shortcut shown as a `Kbd` (`⌘K` command
   menu, `C` new chat, `G` then a letter to go to a page). Targets are still ≥ 40px.
4. **Show the work.** Agent tool calls are rows (`ToolStep`) with a state, a plain verb, a mono detail and
   a duration, never hidden behind spinners.
5. **Big enough to read.** `body` is 16px, chat messages `body-lg` 17px; `caption` 13px is the floor.
6. **Alive, not busy.** Only live things move.
7. **Lists before cards.** Equivalent items (templates, suggestions, apps, skills) are rows in a list,
   led by their text.

## Colors

Dark is the primary theme; light mirrors it and applies when the OS prefers light.

- **Surfaces**: `bg` (canvas), `bg-raised` (sidebar, header bars, side panels), `bg-elevated` (cards,
  popovers, the composer, the command menu), `bg-hover`, `bg-selected`.
- **Lines**: `border` for hairlines between regions; `border-strong` for outlines of inputs, checkboxes
  and secondary buttons (3:1 against `bg-elevated`).
- **Text**: `text` (primary), `text-muted` (secondary), `text-faint` (meta only: timestamps, counts,
  hints; never body copy). Selected rows use `bg-selected` plus `text`.
- **Accent**: the logo's green ring (`brand-signal`, #4a946a) sets the palette; `accent` is that green
  stepped lighter for dark and deeper for light so it passes contrast. It marks the single primary action
  on a screen, focus, the selected indicator (the selected row fills with `bg-selected` and its icon turns
  `accent-text`; no side stripes), live dots and the agent's wave. `accent-text` is for links and success.
- **Data**: `accent-2` (teal) is a second data colour for chart bars and file-type tags, never an action.
- **State**: errors `danger`, attention `warning`, each with a `-subtle` fill for banners and badges.
- **Brand**: `brand-signal` is for the mark only, never text on light; `brand-ink` is the wordmark.

## Typography

Geist for the UI, Geist Mono for commands, file paths, tool output and numbers in data. Titles are 600
weight with tight tracking (`title-1` for page titles, `title-2` for sections and dialogs); the
empty-chat greeting is the only `display`. Labels and section headings are sentence case in the UI sans
(`caption`, `text-muted`); no uppercase eyebrows. Counts and sizes use tabular figures.

## Layout

- **Grid**: 4px. Rows pad `space-3`, cards `space-6`, pages `space-8` at the sides and `space-12` on top.
  Content never exceeds `content-width` (880px; app screens may go wider).
- **Columns**: three at most: sidebar (`sidebar-width`, `bg-raised`, right `border`), main panel (`bg`),
  and an optional right panel (`bg-raised`, left `border`): chat artifacts, file details, or an app's own
  chat (`panel-width`). Under 1100px a right panel overlays the main one; under 800px the sidebar becomes
  a drawer over `scrim`. The composer stays pinned to the bottom of a chat.
- **Pages**: a header with `title-1` on the left and actions on the right, then content. Files is a
  drive: a mono path bar, folder tiles, file cards with a thumbnail, and a details pane.
- **Responsive**: everything works from 390px wide; app screens lay out by their own width (container
  queries), so they adapt when a panel opens beside them.

## Elevation & Depth

Depth comes from lightness steps and hairlines first. Shadows appear only where they mean something:
`shadow-pop` (command menu, menus, the mobile drawer, overlaid right panels), `shadow-composer` (the chat
composer only) and `shadow-card` (cards and file tiles on hover; in light it replaces the lightness
steps). Every shadow has an offset and a soft blur; nothing glows.

## Shapes

`radius-md` for controls, rows and nav items; `radius-lg` for cards, the composer and the command menu;
`radius-sm` for badges, keyboard hints and checkboxes; `radius-full` for avatars, status dots and the send
button.

Icons: 1.75px stroke, 20px default size, round caps and joins, drawn inline as SVG in `currentColor`
(`frontend/src/components/icons.tsx`). An icon appears only when it tells the kind of thing (a folder, a
file type) or labels an icon-only button. The logo is a green ring holding a zigzag wave (three peaks,
four valleys, ends at mid-height), drawn with round caps in `brand-signal`, beside the wordmark "AI
Chatbot Framework" in `brand-ink`. It sits on the surface directly: no tile, no outline, no other colour.
Mark SVG (24-unit box): `<circle cx="12" cy="12" r="10.25"/>` +
`<polyline points="4.4,12 6.3,15.8 8.2,8.4 10.1,15.8 12,8.4 13.9,15.8 15.8,8.4 17.7,15.8 19.6,12"/>`.

## Components

Button, Input, Kbd, Badge, NavItem, ListRow, ToolStep, Composer, CommandMenu. Reference styles are in
`design/components.css` as `.acf-*` classes built only from the tokens; the app's own styles are in
`frontend/src/styles.css`. Copy them, don't restyle.

- **Buttons**: default (`bg-elevated`, `border-strong` outline), `primary` (`accent` fill, `accent-fg`
  text; one per screen), `ghost` (no fill, `text-muted`, `bg-hover` on hover), `danger`. Heights
  `control-sm` / `control-md` / `control-lg`; compact buttons grow to `control-md` on phones.
- **Inputs**: `control-md` high, `radius-md`, `border-strong` outline; the caret is `accent`.
- **Focus**: a 2px `accent` outline with a 2px offset on every focusable element.
- **ToolStep**: a row with a state (check, cross, or the live wave), a verb, a mono detail that truncates,
  and a duration. While running, the verb shimmers.
- **Motion**: 120–160ms ease-out for hover and selection; the command menu scales in from 98%. Live
  things only: the wave speaks (scaleY to 0.55, 1.3s) while the agent works, a running step's verb
  shimmers (2.4s), live dots send a ring every 3s. All of it stops under `prefers-reduced-motion`.

## Do's and Don'ts

Do:

- Use plain words, sentence case and verbs on buttons ("New chat", "Upload skill", "Run now").
- Name things by what people recognise: *Files*, *Skills*, *Tasks*, *Connections*.
- Write errors that say what happened and what to do: "Could not reach the model. Check the server
  address in Settings."
- Check light, dark and 390px wide for every change.

Don't:

- Use exclamation marks or emoji.
- Add a colour, size or radius that isn't a token; add the token to `tokens.json` instead.
- Use `brand-signal` for anything but the mark, or `accent-2` for an action.
- Decorate: no glows, gradients, decorative tiles, icons above headings, coloured side stripes or
  uppercase eyebrows.
- Animate anything that isn't live.
