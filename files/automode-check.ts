/**
 * automode-check — warns when a session starts without the pi-automode plugin.
 *
 * omp's default approval mode asks about nothing: the starter pack relies on auto mode to
 * check risky actions. If the plugin fails to load (an update, a broken install), nothing
 * checks anything and omp gives no sign of it. This says so on the first prompt.
 *
 * Plugin tools may not be registered yet at session_start, so the check runs at
 * before_agent_start.
 */
import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";

export default function automodeCheck(pi: ExtensionAPI) {
	let checked = false;
	pi.on("before_agent_start", (_event, ctx) => {
		if (checked || ctx.agent?.kind === "sub" || !ctx.hasUI) return;
		checked = true;
		if (!pi.getAllTools().some(tool => tool.name === "automode_inspect")) {
			ctx.ui.notify(
				"Auto mode is not loaded: nothing is checking risky actions in this session. Run `omp plugin list`, reinstall @czottmann/pi-automode if it is missing, then restart omp.",
				"warning",
			);
		}
	});
}
