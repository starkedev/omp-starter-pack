# Setting someone up with the omp starter pack

You are helping a Glitch member install this pack. They may be new to omp and to the terminal.
Use plain words, ask one question at a time, and give your recommendation with each question.

`README.md` says what the pack does and why. `install.py` does all the work: you collect the
answers, build one command, run it, and read its output back.

## Rules

- Change settings only through `install.py`. Never edit `~/.omp/agent/config.yml` or the auto
  mode config by hand, and never offer to.
- Find out what you can before asking. Ask only what the member has to decide.
- If the member does not mind either way, take the recommendation.
- Run the installer once, with every answer in it.

## 1. Find out first

- **omp**: `omp --version`. If it is missing, point them to
  <https://github.com/can1357/oh-my-pi#install> and stop until it is installed and signed in
  to Claude.
- **Glitch folder**: the folder holding `.claude/hooks/write-guard.py`. Look in the current
  folder and its parents; otherwise ask where their Glitch folder is. No Glitch folder is fine:
  the installer then skips the Glitch parts.
- **GitHub names**: `gh api user -q .login`, and the owners in `git remote -v` of their
  projects. Confirm the list with them: these are the accounts auto mode will treat as theirs.
- **Existing setup**: if `~/.omp/agent/config.yml` exists, read it. For any setting below that
  they have already set, tell them its value and ask whether to keep it.

## 2. Ask

**When should an idle conversation be shrunk?**

omp resends the whole conversation on every turn, so a long one left open is costly to come
back to. With this on, a conversation over the limit is shrunk to a summary plus its most
recent messages after sitting idle for five minutes. Glitch saves the chat to memory first.

- 200K tokens: the default, and the recommendation.
- 150K: tighter, for a smaller Claude plan.
- 300K: looser, when long sessions matter more than usage.
- Off: never shrink an idle conversation.

→ `--set compaction.idleThresholdTokens=N`, or `--set compaction.idleEnabled=false`.

That is the only question. Do not ask about the main model: they pick it in omp with `/model`.
Do not ask about auto mode's own rules: the pack's are the starting point, and they can be
changed later.

## 3. Install

Run from this folder, with one `--github` for each name:

```sh
uv run install.py --glitch <Glitch folder> --github <name> --set <key>=<value>
```

Read the output back in plain words: what was added, what was left as they had it, and what
was set because they chose it. If any line under `Check` says `FAIL`, say which and stop.

## 4. Finish

- Tell them to restart omp. Open omp sessions resend their whole conversation once after a
  settings change, so close the ones they do not need first.
- Tell them to run `uv run install.py --check` after every omp or plugin update.
- Tell them the three things from "Things to know" in `README.md` that matter day to day:
  approve risky actions in plain words in chat, a block is a block, and do not pin auto mode's
  checking model.
