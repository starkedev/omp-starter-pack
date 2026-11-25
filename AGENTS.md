# Setting someone up with the omp starter pack

You are helping a Glitch member install this pack. They may be new to omp and to the terminal.
Use plain words, ask one thing at a time, and give your recommendation with each question.

You are running in the pack's own folder, not in their Glitch folder. `README.md` says what
the pack does and why. `install.py` does all the work: you collect the answers, build one
command, run it, and read its output back.

## Rules

- Change settings only through `install.py`. Never edit `~/.omp/agent/config.yml` or the auto
  mode config by hand, and never offer to.
- Find out what you can before asking. Ask only what the member has to decide.
- If the member does not mind either way, take the recommendation.
- Run the installer once, with every answer in it. It is safe to run again later: to change
  an answer, run it again with the new one.

## 1. Find out first

- **omp**: `omp --version`. If it is missing, point them to
  <https://github.com/can1357/oh-my-pi#install> and stop until it is installed. If it is older
  than 19.1.1, have them run `omp update` first; the installer refuses older versions.
- **omp works**: ask them to open omp, type "hello", and tell you whether it answered. If it did
  not, they have no provider yet: the installer doesn't need one, but omp is no use until it has
  one. After the install, the provider guide helps them choose (step 4).
- **Glitch folder**: ask where it is. It is the folder holding `.claude/hooks/write-guard.py`;
  check that file exists before going on. No Glitch folder is fine: the installer then skips
  the Glitch parts.
- **GitHub names**: the accounts and organisations that are the member's own. Start from
  `gh api user -q .login` if `gh` is signed in, and from the owners in `git remote -v` of each
  project under `<Glitch folder>/workspaces/`. Do not use the Glitch folder's own remote: that
  is Glitch's home, not theirs. Read the list back and let them correct it. Auto mode treats a
  push to these as a push to their own space, so leave out anything they are unsure of.
- **Existing setup**: if `~/.omp/agent/config.yml` exists, read it. If it already sets
  `compaction.idleEnabled` or `compaction.idleThresholdTokens`, say what it is set to when you
  ask the question below.

## 2. Ask

**1. When should an idle conversation be shrunk?**

omp resends the whole conversation on every turn, so a long one left open is costly to come
back to. With this on, a conversation over the limit that is left alone is shrunk to a summary
plus its most recent messages, once it has sat idle long enough that the provider's saved copy
of it is about to expire (up to an hour). A provider whose saved copy never expires, such as a
ChatGPT plan, never triggers it; the working limit below is what counts there. Glitch saves the
chat to memory first.

| Answer | Add to the command |
|---|---|
| 200K tokens: the recommendation | `--set compaction.idleEnabled=true --set compaction.idleThresholdTokens=200000` |
| 150K: tighter, for a smaller plan | `--set compaction.idleEnabled=true --set compaction.idleThresholdTokens=150000` |
| 300K: looser, when long sessions matter more than usage | `--set compaction.idleEnabled=true --set compaction.idleThresholdTokens=300000` |
| Off: never shrink an idle conversation | `--set compaction.idleEnabled=false` |

**2. At what size should a conversation be shrunk while you are working?**

The idle limit only helps a conversation left open. One you keep working in grows until omp
shrinks it, and by default that is close to the model's limit: up to a million tokens on the
large models, with every turn resending all of it. A working limit shrinks it earlier. On a
model whose own limit is smaller than this number, omp ignores it and uses its default.

| Answer | Add to the command |
|---|---|
| 325K tokens: the recommendation | `--set compaction.thresholdTokens=325000` |
| 200K: tighter, for a smaller plan | `--set compaction.thresholdTokens=200000` |
| No working limit: omp's default | `--set compaction.thresholdTokens=-1` |

Those are the only two settings to ask about. Do not ask about the main model or providers: the
provider guide covers those after the install. Do not ask about auto mode's own rules: the pack's
are the starting point.

## 3. Install

Run from this folder, with one `--github` for each name (none if they have no GitHub):

```sh
uv run install.py --glitch <Glitch folder> --github <name> <the --set parts from the tables>
```

Read the output back in plain words: what was added, what was left as they had it, and what
was set because they chose it. If any line under `Check` says `FAIL`, say which and stop.

## 4. Finish

- Tell them to restart omp. Open omp sessions resend their whole conversation once after a
  settings change, so close the ones they do not need first.
- Tell them about the provider guide: in omp, they say "set up my providers". It checks which
  of their plans the vendor allows in omp, signs them in, and gives the background helpers small
  models. Say plainly that Anthropic permits plan sign-ins only in Claude Code and apps it has
  approved, and omp isn't one; for Claude they use Claude Code in their Glitch folder, or an
  Anthropic API key in omp.
- Tell them to run `uv run install.py --check --glitch <Glitch folder>` after every omp or
  plugin update.
- Tell them the three things from "Things to know" in `README.md` that matter day to day:
  approve risky actions in plain words in chat, a block is a block, and keep a fallback for auto
  mode's checking model.
