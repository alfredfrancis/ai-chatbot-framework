# Web search and page fetching

Intents can use [Parallel Search MCP](https://docs.parallel.ai/integrations/mcp/search-mcp)
to search the web or retrieve excerpts from a page. Search uses Fast mode and
needs no account or API key. This is a fulfilment step after intent recognition
and parameter collection; it does not ask the NLU model to choose tools or write
an answer.

Start with a working bot and a configured NLU pipeline from the
[getting started guide](02-getting-started.md). Traditional NLU requires trained
models even when you use explicit `/intent_id` commands.

## Create a search intent

1. In the intent editor, create an intent with ID `web_search`.
2. Add a required parameter named `query`, with type `free_text` and prompt
   `What would you like to search for?`.
3. Enable **Web search / page fetch**, select **Search the web**, and set
   **Query or URL template** to `{{ parameters.query }}`.
4. Set **Speech Response** to this Jinja template and save:

   ```jinja
   {% for page in result.results %}
   {{ page.title or page.url }}
   {{ page.url }}
   {{ page.excerpts | join('\n') }}
   {% else %}
   No pages found.
   {% endfor %}
   ```

5. Reload the bot to activate the saved intent: restart the backend, or use
   **Train Models** on the Intents page and wait for successful training and
   reload. Saving an intent alone does not update the running dialogue manager.

In the chat interface, send `/web_search`, then answer the bot's prompt with a
query such as `Python release schedule`. The bot renders page titles, source
URLs and relevant excerpts in its reply. You can also add training phrases to
recognize this intent through your configured NLU pipeline.

Leave the query template empty to search for the triggering user message itself.
Templates can access the existing `parameters` and `context` dictionaries. Only
the rendered query is sent to the search service, together with an opaque
conversation identifier. Do not include credentials or private information in
queries. API keys configured for other services are not sent to Parallel.

## Fetch a page

Create another intent with ID `web_fetch` and the same parameter and response
configuration. Select **Fetch a page URL** and use
`{{ parameters.query }}` as the URL template. Save and reload the bot as above.
Send `/web_fetch`, then provide a
complete HTTP or HTTPS page URL. The reply uses the same `result.results` list.
Each entry includes its `url`, optional `title` and `excerpts`.

Fetch retrieves one page per fulfilment. Use search excerpts directly when they
already answer the question; fetching every search result is unnecessary.

## Controls and existing intents

Existing intents keep their current behavior. Web access is off for each intent
until enabled. When enabled, Parallel is the built-in provider and requires no
provider selection or credential configuration. Turn the checkbox off, save, and reload the bot to stop
web requests for that intent. Set `WEB_SEARCH_ENABLED=false` in the backend
environment and restart the backend to disable all built-in web fulfilments.

When **REST API Calling** is also enabled with API details, the existing REST
fulfilment takes precedence, including its URL, headers and credentials. A failed
REST request does not fall back to web search. Web replies escape interpolated
content and include only HTTP(S) source URLs; existing REST response templates
keep their rendering behavior.

The `thread_id` identifies a conversation. Related searches and page fetches
reuse a random UUID stored with that conversation's state, separate from the
thread ID. Start a new conversation with a new thread ID, or send the existing
`/init_conversation` command to start a fresh web session on the same thread
(the command follows `DEFAULT_WELCOME_INTENT_NAME` if customized).

Calls time out after 30 seconds, and cancellation stops the pending request.
Service errors and free-tier quota limits use the existing “Service is not
available” reply. Retries on the same conversation retain its identifier. The
anonymous service is rate limited; free access is not unlimited.
