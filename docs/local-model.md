# A local model for background jobs

Scheduled tasks that run every hour don't need a frontier model, and they don't need to be fast: a run that
takes ten minutes is fine. `docker-compose.withllm.yml` runs one on your own hardware next to the stack,
sized for a **Raspberry Pi 5 with 8 GB**, and each task can be set to run on it (the **Model** field on the
Tasks page, or `model` in the `system` server's `create_task` / `update_task`). Chats stay on your default
model.

## The model: Qwen3.5 4B

| | Qwen3.5 4B (chosen) | Gemma 4 E2B |
|---|---|---|
| File | `unsloth/Qwen3.5-4B-MTP-GGUF`, `UD-Q4_K_XL`, 2.8 GB | `unsloth/gemma-4-E2B-it-qat-GGUF`, 2.4 GB |
| Generation on a Pi 5 | ~3 tokens/s, ~4.8 with MTP | ~9, ~13 with MTP |
| A 40-token tool call | ~8 s | ~3 s |
| Agent work | Picks tools reliably, holds a short chain of steps | Fine for one narrow step; "confident and wrong" on chains |

For unattended jobs accuracy matters more than speed, so it is Qwen3.5 4B. 7–8B models run at ~2.5
tokens/s and Gemma 4 E4B doesn't fit in 8 GB. Numbers from
[Marcelo Rovai's Pi 5 MTP benchmarks](https://mjrovai.com/articles/slm-on-raspberry-pi-mtp/) and
[pi5-llm-arena](https://github.com/leemailto2008/pi5-llm-arena); measure your own jobs before you rely on them.

Use the `-MTP-` repo: the multi-token-prediction head is in that file, and the plain repo has none.

## What to expect

The agent sends a large system prompt (instructions, `context.md`, skills, apps, memory and the tool
definitions). A Pi processes a prompt at roughly 20–45 tokens/s, so the **first step of a run takes a few
minutes**; later steps reuse the cached prompt and take ~30–60 s each. A typical task is 5–15 minutes. Keep
skills, memory and connected MCP servers small: every tool definition is prompt to process.

## Set it up

On the Pi (64-bit Raspberry Pi OS, an active cooler, ideally an NVMe drive):

```sh
cp .env.example .env    # as in the README, plus:
echo "ACF_LOCAL_LLM_KEY=$(openssl rand -hex 32)" >> .env
docker compose -f docker-compose.yml -f docker-compose.withllm.yml up -d --build
```

`--build` matters on a Pi: the published app images are amd64, and `llama-server` is built from source for
the CPU it runs on (`deploy/llm/Dockerfile`, llama.cpp `b10075`). The first start builds it (10–20 minutes on
a Pi) and downloads the model once into the `llm-models` volume (`llm-download`). The model server sits on
its own internal network: the app reaches it at `http://llm:8080`, while sandboxes and the internet can't.

Then, in ACF:

1. **Settings → Models → OpenAI**: address `http://llm:8080/v1`, API key = the `ACF_LOCAL_LLM_KEY` value.
   This takes the OpenAI slot for your account; if you also use OpenAI itself, use a second account for
   background jobs.
2. **Add a model** under OpenAI: `qwen3.5-4b`. Open its options and set the **token window to 32768**
   (`ACF_LOCAL_LLM_CTX`), so the agent compacts before the server runs out of context.
3. **Tasks → New task**: pick **qwen3.5-4b** under **Model**.

A sub-agent asked for the "fast" model gets `gpt-4.1-mini` on this address, which `llama-server` serves with
the same local model. It handles one request at a time, so sub-agents take turns.

## Prompt caching

`llama-server` keeps the processed prompt of its one slot (`--parallel 1`) and reuses the longest matching
prefix on the next request. ACF builds the system prompt once per turn and puts the date last, so the prompt
stays the same from step to step and nearly the same from run to run (memory changes near the end). Qwen3.5
is a hybrid model with recurrent layers, so it can only go back to a shared prefix from a saved checkpoint:
`--ctx-checkpoints 16` keeps them, and `--cache-ram 1024` keeps an idle slot's state in RAM (the default of
8 GB would not fit). To check that it works, look at `docker compose logs llm` while a task runs: from the
second step on, most prompt tokens should come from the cache, not be processed again.

## Tuning (`.env`)

| Setting | Default | |
|---|---|---|
| `ACF_LOCAL_LLM_REASONING` | `off` | `on` lets the model think before it answers: better tool choice, but at ~5 tokens/s each step takes minutes longer. Set a budget with it. |
| `ACF_LOCAL_LLM_REASONING_BUDGET` | `0` | Thinking tokens per answer when reasoning is on, e.g. `512`. |
| `ACF_LOCAL_LLM_CTX` | `32768` | Context size. Set the model's token window in Settings to the same number. |
| `ACF_LOCAL_LLM_THREADS` | `4` | CPU threads; the Pi 5 has four cores. |
| `ACF_LOCAL_LLM_CACHE_RAM` | `1024` | MiB of RAM for cached prompts. |
| `ACF_LOCAL_LLM_MEMORY` | `5g` | Memory limit of the model server (weights ~2.8 GB, context ~1 GB, prompt cache). |
| `ACF_LOCAL_LLM_REPO`, `ACF_LOCAL_LLM_FILE`, `ACF_LOCAL_LLM_ALIAS` | Qwen3.5 4B | Another GGUF model. The alias is the model id you add in Settings. |
| `ACF_LOCAL_LLM_LLAMA_CPP` | `b10075` | The llama.cpp release to build. |

Memory on an 8 GB Pi: the model server ~4.6 GB, a sandbox up to 1 GB, the app, PostgreSQL, Redis and Caddy
about 1 GB. It fits; don't run other heavy services next to it.
