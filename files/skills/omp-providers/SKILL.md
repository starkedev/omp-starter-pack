---
name: omp-providers
description: Use when the member wants to add, change or choose a model provider in omp, sign in to one, set the small helper models, or set a fallback from one provider to another.
---

# Set up model providers in omp

You are helping a Glitch member choose and set up the providers omp runs on. They may be new to
omp. Use plain words, ask one thing at a time, and give your recommendation with each question.
The choice is theirs: you lay out what each vendor allows, they decide.

## 1. Ask what they have

Ask which plans or API keys they already pay for, and which they want omp to use. Then check
each one against the table below before they sign in.

## 2. Check the vendor allows it

Signing in with a plan (a monthly subscription) inside a tool the vendor didn't make is up to
the vendor, and several say no. An API key, paid per use, works in any tool. This is what the
vendors' own pages said on 25 November 2026; terms change, so open the source link and confirm
before you recommend anything.

| Provider and route | In omp | Allowed? | Source |
|---|---|---|---|
| Any API key: Anthropic, OpenAI, Mistral, z.ai standard key, OpenRouter and others | `/login <provider>` and paste the key, or its environment variable | Yes. Paid per use. | Each vendor's API terms |
| Mistral plan | `/login mistral` | Yes. It creates a normal Mistral API key that draws on the plan. | [Mistral API keys](https://docs.mistral.ai/admin/identity-access/api-keys) |
| ChatGPT plan (Codex) | `/login openai-codex` | Low risk. OpenAI welcomes open-source tools on ChatGPT plans through "Sign in with ChatGPT". omp signs in as the Codex CLI instead, so it is not OpenAI's approved route yet. | [Sign in with ChatGPT](https://developers.openai.com/siwc/token-sharing-open-source) |
| Claude plan (Pro, Max) | `/login anthropic` | No. Plan sign-ins are for Claude Code and Anthropic's own apps "unless previously approved", and omp is not approved; it presents itself as Claude Code. Use an Anthropic API key in omp, or open Claude Code beside omp for Claude work. | [Claude Code legal](https://code.claude.com/docs/en/legal-and-compliance), [Agent SDK](https://code.claude.com/docs/en/agent-sdk/overview), [Consumer Terms](https://www.anthropic.com/legal/consumer-terms) |
| Cursor plan | `/login cursor` | No. Cursor staff named omp's Cursor provider as against its terms, with account bans as the penalty. | [Cursor forum](https://forum.cursor.com/t/does-using-oh-my-pi-s-cursor-provider-or-an-openai-compatible-proxy-to-the-same-endpoints-violate-cursor-s-tos/167778) |
| Grok plan (SuperGrok, X Premium) | `/login xai-oauth` | No. xAI allows its plans in named partner tools; omp is not one, and it presents itself as the Grok CLI. An xAI API key is fine. | [Grok in OpenCode](https://x.ai/blog/grok-opencode) |
| z.ai GLM Coding Plan | `/login zai` | No. The plan is limited to the tools z.ai lists, and omp is not on the list. A z.ai standard API key (`ZAI_API_KEY`) is fine; it bills pay per use, not the plan. | [z.ai supported tools](https://docs.z.ai/devpack/tool/others), [z.ai key types](https://docs.z.ai/devpack/notice/api-key-management) |

For a provider not in the table, find the vendor's own terms on using its plan in other tools
before they sign in. If the terms don't say, tell them you don't know rather than guessing.

When a member picks a route marked "No", say plainly what the vendor's terms say and that the
risk falls on their account, then let them decide. If they go ahead with a Claude plan anyway,
also run `omp config set claudeResets.autoRedeemWeekly no`, so omp never spends a saved weekly
reset by itself.

## 3. Sign in and check

In omp, they type `/login <provider>` (from a terminal: `omp login <provider>`). Then they pick
one of its models with `/model` and send "hello". Only go on when it answers.

## 4. Small models for the helpers

omp runs background helpers on model roles. Without them set, helpers run on the session's main
model, which works but spends the most usage. Give these roles a small, fast model from the
provider they use most:

| Role | What runs on it |
|---|---|
| `smol` | Quick jobs, and auto mode's check of each risky action |
| `tiny` | Session titles and other light background work, and auto mode's fallback checker. Unset, it uses `smol`. |
| `memory` | Memory summaries. Unset, it uses `tiny`. |
| `commit` | Commit messages |
| `vision` | Reading images: pick a model that takes images |

The easy way is omp's own picker: `/models`, then assign a model to each role. Assigning a role
there saves it without switching the conversation's model. To do it from a terminal instead:
list a provider's models with `omp models <provider>`, read what is set with
`omp config get modelRoles --json`, merge their choices in, show them the result, and set it
once with `omp config set modelRoles '<json>'`. That command replaces the whole map, so never
set it with only the new roles.

## 5. Fallbacks between providers (optional)

With two or more providers, omp can move a turn to another model when one hits a rate or usage
limit, and come back once the limit resets. This is `retry.fallbackChains`: each key is a model
(`openai-codex/gpt-6-luna`) or a whole provider (`openai-codex/*`), and its value is the list of
models to try next, in order. An exact model key beats the provider's `/*` key; an empty list
means no fallback for that model.

- Fall back to the same kind of model: a main model to the other provider's main model, a
  helper to its helper.
- Add a `provider/*` key for each provider, so a model they pick later with `/model` is covered.
- Set `retry.rateLimitWalksChain` to `true`, so a rate limit walks the chain.

Read what is set with `omp config get retry.fallbackChains --json`, merge, show them, then set it
once with `omp config set retry.fallbackChains '<json>'`.

## 6. Finish

- A change to omp's settings makes every open omp session resend its whole conversation on its
  next turn. Close the sessions they don't need, then restart omp.
- If they set up auto mode with the starter pack, run its check: `uv run install.py --check`
  from the pack's folder.
- For Claude without an API key, they use Claude Code itself, opened in their Glitch folder. It
  runs Glitch fully on its own.
