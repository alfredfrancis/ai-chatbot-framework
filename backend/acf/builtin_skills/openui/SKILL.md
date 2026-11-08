---
name: openui
description: Show a chart, a table, a plan or a small interactive view (sliders, choices, buttons that reply) right in a chat answer, written in OpenUI Lang. Also the language personal apps are written in. Use when numbers read better as a chart, when the user should pick or adjust something, or before writing an app's app.oui.
pinned: true
---

# OpenUI views

OpenUI Lang describes a screen made of the web app's own components (cards, stats, charts, lists, tabs,
inputs, buttons). You write components and data, never HTML or styles; the look comes from the design
system and works in light, dark and on phones. `reference.md` in this skill's folder is the complete
reference for the language and the only components that exist: read it before writing a view.

## In a chat answer

Put one program in a fenced code block with the language `openui`; text before and after it shows as
usual:

````
Here is where the money went:

```openui
root = Screen([spend])
spend = BarChart("Spending by month", ["Aug", "Sep", "Oct"], [{name: "Food", values: [320, 280, 345]}], "EUR")
```

October was the highest month.
````

- The data goes in the program: work the numbers out first (read the files, run a script), then write
  them in. `Query`, `Mutation`, `@Run` and `Board` need a personal app and don't work in chat.
- Inputs (`Slider`, `RadioGroup`, `Checkbox`, `TextField`, ...) keep a `$variable`; a `Button` with
  `@ToAssistant("..." + $variable)` sends that text to you in the same chat, as if the user typed it.
  Use this to let the user choose instead of asking them to type (pick a slot, set a budget).
- Use a view when it says more than text: a trend, a comparison, shares of a whole, a plan with steps,
  a choice to make. Answer short questions in words. One view per answer, usually.
- Still say the key finding in a sentence: the view can't be searched or read in past chats as easily.
- `@OpenUrl` opens only http(s) links.

## In a personal app

The screen `apps/<id>/app.oui` is the same language, plus `Query` and `Mutation` over the app's tools
(read and write its files, run its scripts, read connected apps) and `Board`. Follow the personal-apps
skill for the files around it.

## Checking a view

Walk the reference's "Final Verification" list. Every name you define must be reachable from `root`.
If a view has problems, the chat shows them under it; fix the program in your next answer.
