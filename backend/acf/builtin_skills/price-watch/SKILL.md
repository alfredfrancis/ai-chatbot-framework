---
name: price-watch
description: Watch a product, flight, hotel or ticket and alert when the full price drops below a limit or it comes back in stock. Use when asked to track a price or availability over time, and for each scheduled check of a watch.
---

# Price watch

A watch is a small JSON file in `watches/<name>.json` plus a scheduled task that checks it.

## Set up (once, in the chat)

1. Pin down the exact item: link, variant (size, colour, dates, class, room type), quantity, seller,
   and what counts as a match. Two variants must not be confusable.
2. Pin down the alert: currency, full price including shipping, fees and taxes (or say it excludes
   them), the limit, and whether stock or refundability matters.
3. Fetch the page once now (`curl -sL` with a browser user agent, or `agent-browser` for pages that need
   JavaScript) and read the current price and stock. If this does not work, stop and tell the user;
   never schedule a watch that has not worked once.
4. Write `watches/<name>.json`: the item, the alert rule, and `last_good` (price, stock, time).
5. Ask the user to add a task on the Tasks page with a schedule (e.g. every 6 hours: `0 */6 * * *`) and
   this prompt: `Use the price-watch skill to check watches/<name>.json.`

## Each check (scheduled)

1. Fetch the page and read the full price and stock the same way as in set-up.
2. A failed fetch, a captcha or an error page means "unknown": say so briefly, and never overwrite
   `last_good` with it.
3. Alert only when the rule is newly met (not again for the same offer): the item, the full price, the
   limit, stock, the time you checked and the link. Record the alert in the file.
4. Nothing new: one short line, e.g. "Still €1,149, above your €1,000 limit."

## Pitfalls

- Compare like with like: a price before tax against a limit with tax gives false alerts.
- Check the variant on the page every time; shops change the default selection.
- Don't check more often than every hour; sites block frequent visitors.
