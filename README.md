# omp starter pack for Glitch

The least you need to run Glitch under [omp](https://github.com/can1357/oh-my-pi) without the
problems I ran into in my first three weeks with it. One command sets it up; a second checks it.

It is for Glitch members who already use Claude Code and want to try omp. It changes nothing in
Glitch's engine.

## What it sets up

| Problem | What the pack does |
|---|---|
| Glitch's guards, secret scan and memory do not run under omp. They are Claude Code hooks, and omp does not read them. | Installs a bridge, `glitch-hooks.ts`, that runs every Glitch hook on the matching omp event, and loads `CLAUDE.md` and your persona the way Claude Code does. |
| omp either asks before every action or checks nothing. | Installs auto mode (the `pi-automode` plugin): a second model call judges each risky action, and routine work goes through without a prompt. |
| Auto mode can fail to load after an update, and omp gives no sign. Nothing is then checked. | Installs a warning that appears on your first prompt when auto mode is missing. |
| Auto mode ignores a config in the wrong place and runs on its defaults. | Writes the config where the plugin reads it under omp: `~/.omp/agent/extensions/pi-automode/config.json`. |
| Auto mode blocks ordinary actions with "response was not 0 or 1" or a timeout. | Sets a 45 second timeout and tells the checking model to answer with one character. This reduces the blocks; a full fix is waiting upstream ([pi-automode#86](https://github.com/czottmann/pi-automode/pull/86)). |
| A session left open keeps growing, and every turn resends all of it. | Turns on idle compaction: a session over 200K tokens is shrunk once it sits idle. |
| Background helpers (titles, commit messages, memory) run on your most expensive model. | Gives those helpers Haiku and Sonnet. Your main model is yours to pick with `/model`. |
| omp can spend a saved Claude weekly reset by itself. | Turns that off. |
| If auto mode is down, nothing stops a disastrous command. | Adds fixed rules that need no model: disk and home wipes are refused, force pushes and piping a download into a shell always ask, and `~/.ssh` and `~/.aws` are off limits. |

`files/settings.yml` and `files/automode.json` hold the settings themselves, with the reason
beside each one.

## Install

**The easy way:** open this folder in Claude Code (or omp) and say "set me up". It asks a few
questions, such as when an idle conversation should be shrunk, then runs the installer for you.
`AGENTS.md` is the script it follows.

**By hand:**

1. Install omp ([instructions](https://github.com/can1357/oh-my-pi#install)) and sign in to Claude in it.
2. From your Glitch folder, run:

   ```sh
   uv run /path/to/omp-starter-pack/install.py --github YOUR-GITHUB-NAME
   ```

   `--github` names an account or organisation that is yours, so auto mode knows a push there is
   not a push to a stranger. Repeat it for each one. Leave it out if you do not use GitHub.

3. Restart omp.

The installer never overwrites a setting you already have or an auto mode config that already
exists. It adds what is missing, says what it left alone, and saves a copy of your settings
first. To choose a value yourself, add `--set`, for example
`--set compaction.idleThresholdTokens=150000`.

## After every omp or plugin update

```sh
uv run /path/to/omp-starter-pack/install.py --check
```

It changes nothing. Every line should say `ok`. Updates are when things break quietly: a renamed
setting, a plugin that did not finish installing.

## Things to know

- **Change settings in a quiet moment.** Any change to `~/.omp/agent/config.yml` makes every
  open omp session resend its whole conversation on its next turn. Close the sessions you do
  not need first.
- **Do not pin auto mode's checking model.** The pack leaves it following your session's model.
  Pinned to one model, a rate limit on that model blocks every action.
- **Approve risky actions in chat.** Auto mode reads your own messages as permission. It does
  not read a tick in a form or a line in a file that way. If it blocks something you want, say
  so in plain words and ask again.
- **A block is a block.** If the agent tries another route to the same action, stop it.
- **Reads outside the folder you are working in are checked.** Glitch treats a read outside
  your Glitch folder as something to ask about, and the pack keeps to that everywhere: auto
  mode checks reads (`classifyReadOnlyTools`), but lets reads inside the working folder through
  without a model call (`allowInsideWorkingDirectory`), so ordinary work costs nothing extra.
- **Rate limits.** The pack sets up no fallback to another provider. If you add one
  (`retry.fallbackChains`), make sure any model standing in for your image model can read
  images: a text-only stand-in answers image questions blind instead of failing.

## Remove it

Delete `~/.omp/agent/extensions/glitch-hooks.ts`, `~/.omp/agent/extensions/automode-check.ts`
and the `.omp` folder in your Glitch folder. Run `omp plugin uninstall @czottmann/pi-automode`.
Put back the settings copy the installer saved beside `~/.omp/agent/config.yml`.
