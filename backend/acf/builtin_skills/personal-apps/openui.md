<!-- Generated from frontend/src/openui/library.tsx by frontend/scripts/build-app-prompt.mjs. Do not edit. -->

Personal apps are written in OpenUI Lang. The file apps/<id>/app.oui holds one program whose root is Screen(...). This is the complete reference for the language and the components available.

## Syntax Rules

1. Each statement is on its own line: `identifier = Expression`
2. `root` is the entry point — every program must define `root = Screen(...)`
3. Expressions are: strings ("..."), numbers, booleans (true/false), null, arrays ([...]), objects ({...}), or component calls TypeName(arg1, arg2, ...)
4. Use references for readability: define `name = ...` on one line, then use `name` later
5. EVERY variable (except root) MUST be referenced by at least one other variable. Unreferenced variables are silently dropped and will NOT render. Always include defined variables in their parent's children/items array.
6. Arguments are POSITIONAL (order matters, not names). Write `SomeComp([children], "row", "l")` NOT `SomeComp([children], direction: "row", gap: "l")` — colon syntax is NOT supported and silently breaks
7. Optional arguments can be omitted from the end
8. Declare mutable state with `$varName = defaultValue`. Components marked with `$binding` can read/write these. Undeclared $variables are auto-created with null default.
9. String concatenation: `"text" + $var + "more"`
10. Dot member access: `query.field` reads a field; on arrays it extracts that field from every element
11. Index access: `arr[0]`, `data[index]`
12. Arithmetic operators: +, -, *, /, % (work on numbers; + is string concat when either side is a string)
13. Comparison: ==, !=, >, <, >=, <=
14. Logical: &&, ||, ! (prefix)
15. Ternary: `condition ? valueIfTrue : valueIfFalse`
16. Parentheses for grouping: `(a + b) * c`
- Strings use double quotes with backslash escaping

## Component Signatures

Arguments marked with ? are optional. Sub-components can be inline or referenced; prefer references for better streaming.
Props typed `ActionExpression` accept one @step, or Action([@steps...]) for several. See the Action section for available steps (@Run, @ToAssistant, @OpenUrl, @Set, @Reset).
Props marked `$binding<type>` accept a `$variable` reference for two-way binding.

Screen(children: any[]) — The whole app screen: its sections from top to bottom.
Row(children: any[]) — Puts components side by side; they stack on phones.
Grid(children: any[], columns?: number) — Equal columns (2-4) of cards or stats; one column on phones.
Card(title: string, children?: any[], description?: string) — A titled section.
Heading(text: string) — A section heading outside a Card.
Text(markdown: string) — Markdown text (bold, lists, links, tables). Use for briefs and notes, e.g. Text(brief.text).
Stat(label: string, value: string | number, note?: string) — One number or short value with a label, e.g. Stat("Due today", @Count(due)).
Badge(text: string, tone?: "neutral" | "success" | "warning" | "danger") — A short status label.
Notice(text: string, tone?: "neutral" | "success" | "warning" | "danger") — A one-line message that stands out: a warning, a problem, or good news.
Table(columns: string[], rows: (string | number | any)[][]) — Rows of values under column headings. rows is a list of rows, each a list of cells.
Button(label: string, action?: ActionExpression, variant?: "primary" | "secondary" | "ghost" | "danger", confirm?: string) — A button. Without an action it sends its label to the agent. Use the primary variant for at most one main action. confirm is a question shown before it runs (use it for anything the user can't undo).
TextField(label: string, value?: $binding<string>, placeholder?: string) — A one-line text box bound to a $variable, e.g. TextField("New task", $title).
SelectField(label: string, options: {value: string, label: string}[], value?: $binding<string>) — A dropdown bound to a $variable. options are {value, label} objects.
Board(title: string, file: string, columns: {id: string, title: string, hint?: string}[], agentNote?: string) — Columns of items the user drags between, ticks done and adds to; it reads and saves a JSON file {"items": [{"id", "title", "column", "note"?, "due"?, "done"?}]} by itself (column is a column id). Four columns show as a 2x2 matrix. agentNote, if set, is sent to the agent with each change - only set it when the agent must react, since each change then costs a run.

## Built-in Functions

Data functions prefixed with `@` to distinguish from components. These are the ONLY functions available — do NOT invent new ones.
Use @-prefixed built-in functions (@Count, @Sum, @Avg, @Min, @Max, @Round) on Query results. Do NOT hardcode computed values.

@Count(array: any[]) → number — Returns array length
@First(array: any[]) → any — Returns first element of array
@Last(array: any[]) → any — Returns last element of array
@Sum(numbers: number[]) → number — Sum of numeric array
@Avg(numbers: number[]) → number — Average of numeric array
@Min(numbers: number[]) → number — Minimum value in array
@Max(numbers: number[]) → number — Maximum value in array
@Sort(array: any[], field: string, direction?: "asc" | "desc") → any[] — Sort array by field. Direction: "asc" (default) or "desc"
@Filter(array: any[], field: string, operator: "==" | "!=" | ">" | "<" | ">=" | "<=" | "contains", value: any) → any[] — Filter array by field value
@Round(number: number, decimals?: number) → number — Round to N decimal places (default 0)
@Abs(number: number) → number — Absolute value
@Floor(number: number) → number — Round down to nearest integer
@Ceil(number: number) → number — Round up to nearest integer
@Each(array: any[], varName: string, template: any) — Evaluate template for each element. varName is the loop variable — use it ONLY inside the template expression (inline). Do NOT create a separate statement for the template.

Builtins compose — output of one is input to the next:
`@Count(@Filter(data.rows, "field", "==", "val"))` for KPIs/chart values, `@Round(@Avg(data.rows.score), 1)`, `@Each(data.rows, "item", Comp(item.field))` for per-item rendering.
Array pluck: `data.rows.field` extracts a field from every row → use with @Sum, @Avg, charts, tables.

IMPORTANT @Each rule: The loop variable (e.g. "item") is ONLY available inside the @Each template expression. Always inline the template — do NOT extract it to a separate statement.
CORRECT: `list = @Each(rows, "t", Comp(t.name))`
WRONG: `item = Comp(t.name)` then `list = @Each(rows, "t", item)`, because t is undefined in item.

## Query — Live Data Fetching

Fetch data from available tools. Returns defaults instantly, swaps in real data when it arrives.

```
metrics = Query("tool_name", {arg1: value, arg2: $binding}, {defaultField: 0, defaultData: []}, refreshInterval?)
```

- First arg: tool name (string)
- Second arg: arguments object (may reference $bindings — re-fetches automatically on change)
- Third arg: default data (rendered immediately before fetch resolves)
- Fourth arg (optional): refresh interval in seconds (e.g. 30 for auto-refresh every 30s)
- Use dot access on results: metrics.totalEvents, metrics.data.day (array pluck)
- Query results must use regular identifiers: `metrics = Query(...)`, NOT `$metrics = Query(...)`
- Manual refresh: `Button("Refresh", Action([@Run(query1), @Run(query2)]), "secondary")` — re-fetches the listed queries
- Refresh all queries: create Action with @Run for each query

## Mutation — Write Operations

Execute state-changing tool calls (create, update, delete). Unlike Query (auto-fetches on render), Mutation fires only on button click via Action.

```
result = Mutation("tool_name", {arg1: $binding, arg2: "value"})
```

- First arg: tool name (string)
- Second arg: arguments object (evaluated with current $binding values at click time)
- result.status: "idle" | "loading" | "success" | "error"
- result.data: tool response on success
- result.error: error message on failure
- Mutation results use regular identifiers: `result = Mutation(...)`, NOT `$result`
- Show loading state: `result.status == "loading" ? TextContent("Saving...") : null`

## Action — Button Behavior

An action wires a button click to operations. Pass one @-prefixed step bare, e.g. Button("Ask", @ToAssistant("Tell me more")). Put several steps in Action([...]), e.g. Button("Read", Action([@OpenUrl("https://example.com"), @ToAssistant("Summarize this page")])). Steps execute in order.
Buttons without an action automatically send their label to the assistant (equivalent to @ToAssistant(label)).

Available steps:
- @Run(ref: Query | Mutation) — Execute a Mutation or re-fetch a Query (ref must be a declared Query/Mutation)
- @ToAssistant(message: string, context?: any) — Send a message to the assistant (for conversational buttons like "Tell me more", "Explain this"). The optional context is any value (object, array, string, number) passed to the assistant as hidden data, e.g. @ToAssistant("Show details", {orderId: 42})
- @OpenUrl(url: string) — Navigate to a URL
- @Set(variable: $variable, value: any) — Set a $variable to a specific value
- @Reset(variable: $variable) — Reset $variables to their declared defaults; pass several to reset each (e.g. @Reset($title, $priority) restores $title="" and $priority="medium")

Example — mutation + refresh + reset (PREFERRED pattern):
```
$binding = "default"
result = Mutation("tool_name", {field: $binding})
data = Query("tool_name", {}, {rows: []})
onSubmit = Action([@Run(result), @Run(data), @Reset($binding)])
```

Example — simple nav:
```
viewBtn = Button("View", @OpenUrl("https://example.com"))
```

- An action can be assigned to a variable or inlined: Button("Go", onSubmit) and Button("Go", Action([...])) both work
- If a @Run(mutation) step fails, remaining steps are skipped (halt on failure)
- @Run(queryRef) re-fetches the query (fire-and-forget, cannot fail)

## Interactive Filters

To let the user filter data with a dropdown:
1. Declare a $variable with a default: `$dateRange = "14"`
2. Create a Select with name, items, and binding: `Select("dateRange", [SelectItem("7", "Last 7 days"), ...], null, null, $dateRange)`
3. Wrap in FormControl for a label: `FormControl("Date Range", Select(...))`
4. Pass $dateRange in Query args: `Query("tool", {dateRange: $dateRange}, {defaults})`
5. When the user changes the Select, $dateRange updates and the Query automatically re-fetches

FILTER WIRING RULE: If a $binding filter is visible in the UI, EVERY relevant Query MUST reference that $binding in its args. Never show a filter dropdown while hardcoding the query args.

Rules for $variables:
- $variables hold simple values (strings or numbers), NOT arrays or objects
- $variables must be bound to a Select/Input component via the value argument (last positional arg) to be interactive
- Queries must use regular identifiers (NOT $variables): `metrics = Query(...)` not `$metrics = Query(...)`
- **Auto-declare**: You do NOT need to explicitly declare $variables. If you use `$foo` without declaring it, the parser auto-creates `$foo = null`. You can still declare explicitly to set a default: `$days = "14"`

## Forms

Simple form — no $bindings needed. Field values are managed internally by the Form via the name prop:
```
contactForm = Form("contact", submitBtn, [nameField, emailField])
nameField = FormControl("Name", Input("name", "Your name", "text", {required: true}))
emailField = FormControl("Email", Input("email", "your@email.com", "email", {required: true, email: true}))
submitBtn = Button("Submit")
```

Use $bindings when you need to read field values elsewhere (in Action context, Query args, or conditionals). They are auto-declared:
```
$role = "engineer"
contactForm = Form("contact", submitBtn, [nameField, emailField, roleField])
nameField = FormControl("Name", Input("name", "Enter your name", "text", {required: true}, $name))
emailField = FormControl("Email", Input("email", "Enter your email", "email", {required: true, email: true}, $email))
roleField = FormControl("Role", Select("role", [SelectItem("engineer", "Engineer"), SelectItem("designer", "Designer"), SelectItem("pm", "PM")], null, {required: true}, $role))
submitBtn = Button("Submit")
```

For form + mutation patterns (create, refresh, reset), see the Action section example above.

IMPORTANT: Always add validation rules to form fields used with Mutations. Use OBJECT syntax: {required: true, email: true, minLength: 8}. The renderer shows error messages automatically and blocks submit when validation fails.

## Data Workflow

When tools are available, follow this workflow:
1. FIRST: Call the most relevant tool to inspect the real data shape before generating code
2. Use Query() for READ operations (data that should stay live) — NEVER hardcode tool results as literal arrays or objects
3. Use Mutation() for WRITE operations (create, update, delete) — triggered by button clicks via @Run(mutationRef)
4. Use the real data from step 1 as condensed Query defaults (3-5 rows) so the UI renders immediately
5. Use @-prefixed builtins (@Count, @Filter, @Sort, @Sum) on Query results for KPIs and aggregations — the runtime evaluates these live on every refresh
6. Hardcoded arrays are ONLY for static display data (labels, options) where no tool exists

WRONG — you called a tool and got data back, but you inlined the results:
```
openCount = 2
item1 = SomeComp("first item title")
item2 = SomeComp("second item title")
list = SomeList([item1, item2])
chart = SomeChart(["A", "B"], [12, 8])
```
This is static — it shows stale data and won't update. Creating item1, item2, item3... manually is ALWAYS wrong when a tool exists.

RIGHT — use Query() for live data, Mutation() for writes, @builtins to derive values:
```
data = Query("tool_name", {}, {rows: []})
openCount = @Count(@Filter(data.rows, "field", "==", "value"))
list = @Each(data.rows, "item", SomeComp(item.title, item.field))
createResult = Mutation("create_tool", {title: $title})
submitBtn = Button("Create", Action([@Run(createResult), @Run(data), @Reset($title)]))
```
Everything derives from the Query — when data refreshes, the entire dashboard updates automatically.

## Available Tools

Use these with Query() for read operations or Mutation() for write operations. The LLM decides which is appropriate based on the tool's purpose.

- read_file(path: string) → {text?: string, data?: any}
  Read a file of the app (its folder, or a file listed in app.json). Returns {text}, plus {data} when the file is JSON.
- update_file(path: string, content: any) → {path?: string}
  Write a file of the app. content is text, or any value, which is saved as JSON.
- ask_agent(prompt: string) → {chat_id?: number}
  Send the agent a message in the app's own chat; it works in the background. Prefer @ToAssistant in buttons.
- run(script: string, input?: any) → {output?: string}
  Run the script apps/<id>/actions/<script>.sh in the sandbox with input as JSON in $1. Returns {output}.
- mcp(server: string, tool: string, arguments?: object) → {text?: string, data?: any}
  Call a read-only tool of a connected app (e.g. a calendar search). Returns {text}, plus {data} when it is JSON. Tools that change things are refused: send those to the agent instead.

### Default values for Query results

Use these shapes as minimal Query defaults:
- read_file: `{"text":"","data":null}`
- update_file: `{"path":""}`
- ask_agent: `{"chat_id":0}`
- run: `{"output":""}`
- mcp: `{"text":"","data":null}`

CRITICAL: Use ONLY the tools listed above in Query() and Mutation() calls. Do NOT invent or guess tool names. If the user asks for functionality that doesn't match any available tool, use realistic mock data instead of fabricating a tool call.

## Hoisting & Streaming (CRITICAL)

openui-lang supports hoisting: a reference can be used BEFORE it is defined. The parser resolves all references after the full input is parsed.

During streaming, the output is re-parsed on every chunk. Undefined references are temporarily unresolved and appear once their definitions stream in. This creates a progressive top-down reveal — structure first, then data fills in.

**Recommended statement order for optimal streaming:**
1. `root = Screen(...)` — UI shell appears immediately
2. $variable declarations — state ready for bindings
3. Query statements — defaults resolve immediately so components render with data
4. Component definitions — fill in with data already available
5. Data values — leaf content last

Always write the root = Screen(...) statement first so the UI shell appears immediately, even before child data has streamed in.

## Examples

root = Screen([summary, needs, todo, actions])
brief = Query("read_file", {path: "apps/cockpit/brief.md"}, {text: ""}, 10)
tasks = Query("read_file", {path: "apps/cockpit/tasks.json"}, {data: {items: []}}, 10)
summary = Grid([Stat("Open to-dos", @Count(@Filter(tasks.data.items, "done", "==", false))), Stat("Do first", @Count(@Filter(tasks.data.items, "column", "==", "do")))], 2)
needs = Card("Needs you", [Text(brief.text)])
todo = Board("To-do", "apps/cockpit/tasks.json", [{id: "do", title: "Do first", hint: "Urgent and important"}, {id: "schedule", title: "Schedule", hint: "Important, not urgent"}, {id: "delegate", title: "Delegate", hint: "Urgent, not important"}, {id: "drop", title: "Drop", hint: "Neither"}])
actions = Row([Button("Refresh", @ToAssistant("Use the personal-assistant skill to refresh the cockpit."), "primary"), Button("Plan my day", @ToAssistant("Plan my day from the cockpit's Do first and Schedule columns."))])

## Important Rules
- Choose components that best represent the content (tables for comparisons, charts for trends, forms for input, etc.)

## Final Verification
Before finishing, walk your output and verify:
1. root = Screen(...) is the FIRST line (for optimal streaming).
2. Every referenced name is defined. Every defined name (other than root) is reachable from root.
3. Every Query result is referenced by at least one component.
4. Every $binding appears in at least one component or expression.
5. Every visible filter $binding appears in at least one Query args object.

- The tools above are called by the app screen, not by you: to see a file's shape, read it with your own read tool.
- Write only these components; never HTML, CSS or colours - the app's look comes from the design system.
- Read data with Query("read_file", ...) and a refresh interval (e.g. 10) so the screen follows the files you update.
- Buttons that need judgment, writing or another app's write tools send the work to you with @ToAssistant("...").
- Keep one screen focused on what the user acts on; at most one primary Button.
