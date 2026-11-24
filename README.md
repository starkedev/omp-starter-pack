# omp starter pack for Glitch

The least you need to run Glitch under [omp](https://github.com/can1357/oh-my-pi) without the
problems I ran into in my first three weeks with it. One command sets it up; a second checks it.

It is for Glitch members who already use Claude Code and want to try omp, with a Claude sign-in
or another provider's. It changes nothing in Glitch's engine.

## Start here

1. **Get the pack.** On this repo's GitHub page, click **Code**, then **Download ZIP**, and unzip
   it. Or, in a terminal: `git clone https://github.com/starkedev/omp-starter-pack`
2. **Open `start.html`** from the pack's folder in your browser: double-click it. Nothing to
   install, and it works offline. From a terminal in the pack's folder, run `open start.html`
   on a Mac, `xdg-open start.html` on Linux, or `start start.html` on Windows.
3. **Answer its five questions.** At the end it gives you a prompt to copy.
4. **Open Claude Code in the pack's folder**: in a terminal, `cd` into it (from a ZIP it is
   called `omp-starter-pack-main`), then run `claude`. Paste the prompt and answer anything it
   asks. When it's done, restart omp.

## What it sets up

| Problem | What the pack does |
|---|---|
| Glitch's guards, secret scan and memory do not run under omp. They are Claude Code hooks, and omp does not read them. | Installs a bridge, `glitch-hooks.ts`, that runs every Glitch hook on the matching omp event, and loads `CLAUDE.md` and your persona the way Claude Code does. |
| omp either asks before every action or checks nothing. | Installs auto mode (the `pi-automode` plugin): a second model call judges each risky action, and routine work goes through without a prompt. |
| Auto mode can fail to load after an update, and omp gives no sign. Nothing is then checked. | Installs a warning that appears on your first prompt when auto mode is missing. |
| Auto mode ignores a config in the wrong place and runs on its defaults. | Writes the config where the plugin reads it under omp: `~/.omp/agent/extensions/pi-automode/config.json`. |
| Auto mode blocks ordinary actions with "response was not 0 or 1" or a timeout. | Sets a 45 second timeout and tells the checking model to answer with one character. This reduces the blocks; a full fix is waiting upstream ([pi-automode#86](https://github.com/czottmann/pi-automode/pull/86)). |
| A session left open keeps growing, and every turn resends all of it. | Turns on idle compaction: a session over 200K tokens is shrunk once it sits idle. The guided setup also offers a limit for sessions you keep working in. |
| Background helpers (titles, commit messages, memory, image reads) run on your most expensive model. | Gives those helpers small models from your first sign-in (`--sign-in claude`, `codex`, `cursor`, `grok` or `mistral`). Your main model is yours to pick with `/model`. |
| A rate or usage limit on one sign-in stops your work. | With more than one sign-in, sets omp to move to the next one in your order when a model hits a limit (helpers to the next sign-in's helpers, your main model to its main model), and back once the limit resets. |
| omp can spend a saved Claude weekly reset by itself. | Turns that off. |
| Secrets in your environment can end up in what the model reads. | Turns on omp's redaction of environment secrets and token-shaped strings. |
| If auto mode is down, nothing stops a disastrous command. | Adds fixed rules that need no model: the plainest forms of a disk or home wipe are refused, and omp's file tools ask before touching `~/.ssh` and `~/.aws`. These are a last line, not a net: a differently spelled command gets past them. |

`files/settings.yml` holds the settings with the reason beside each one; `files/automode.json`
holds auto mode's rules.

## Install

**The easy way:** the steps under [Start here](#start-here). Claude follows `AGENTS.md`; saying
"set me up" in Claude Code in this folder, without the prompt, works too, and it asks the same
questions in chat.

**By hand:**

1. Install omp ([instructions](https://github.com/can1357/oh-my-pi#install)) and sign in to it.
2. From your Glitch folder, run:

   ```sh
   uv run /path/to/omp-starter-pack/install.py --github YOUR-GITHUB-NAME --sign-in claude
   ```

   `--github` names an account or organisation that is yours, so auto mode knows a push there is
   not a push to a stranger. Repeat it for each one. Leave it out if you do not use GitHub.

   `--sign-in` names a sign-in you use in omp. Repeat it in the order to fall back through them,
   for example `--sign-in claude --sign-in codex`. `files/sign-ins.yml` lists the models each one
   uses.

3. Restart omp.

The installer never overwrites a setting you already have. It adds what is missing (for the
fixed rules, it adds the pack's beside yours), says what it left alone, and saves a copy of a
file before changing it. In an auto mode config that already exists it touches only two lines:
your GitHub names and your Glitch folder. To choose a value yourself, add `--set`, for example
`--set compaction.idleThresholdTokens=150000`.

## After every omp or plugin update

```sh
uv run /path/to/omp-starter-pack/install.py --check --glitch /path/to/your/glitch
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

## Known gaps

- **omp's `eval` tool is not covered by Glitch's guards.** It runs Python or JavaScript
  directly, and Glitch's hooks only know shell commands and file edits. Auto mode still
  checks it.
- **Auto mode's working-folder shortcut looks loose.** From reading its code, a read or write
  whose path is a web or `ssh://` address counts as inside the working folder and skips the
  check. Not yet confirmed in a live session.
- **Chat transcripts are kept outside your Glitch folder**, in
  `~/.omp/agent/glitch/transcripts/`, so Glitch's memory can read them. Nothing prunes them.

## Remove it

1. Run `omp plugin uninstall @czottmann/pi-automode`.
2. Delete `~/.omp/agent/extensions/glitch-hooks.ts`, `~/.omp/agent/extensions/automode-check.ts`
   and the folder `~/.omp/agent/extensions/pi-automode`.
3. Delete the `.omp` folder in your Glitch folder, and the `.omp/` line in its
   `.git/info/exclude`.
4. Delete `~/.omp/agent/glitch/transcripts/` if you do not want the transcripts.
5. Put back the settings copy the installer saved beside `~/.omp/agent/config.yml`, or delete
   the settings you no longer want from that file.
