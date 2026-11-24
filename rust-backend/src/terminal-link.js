import { appHome, exec, focused, openOverlay, readTextFile } from "herdr";

function stillAtSource(source) {
  const current = focused();
  return !!source?.terminal && !!source.tab && !!source.space &&
    current?.tab === source.tab && current.space === source.space &&
    (current.shown || current.terminal) === source.terminal;
}

export async function handleLink(click) {
  try {
    const { link, source } = click ?? {};
    if (link?.kind !== "url" || typeof link.url !== "string" || !stillAtSource(source)) return "pass";
    const url = new URL(link.url);
    const key = /^\/browse\/([A-Z][A-Z0-9_]*-[0-9]+)$/.exec(url.pathname)?.[1];
    if (url.protocol !== "https:" || url.username || url.password || !key || key.length > 256) return "pass";

    const home = appHome();
    const bindingPath = `${home}/mods/jira-peek-terminal-links/binding.json`;
    const text = await readTextFile(bindingPath);
    const binding = JSON.parse(text);
    if (binding?.origin !== url.origin || typeof binding.configDir !== "string" || !binding.configDir.startsWith("/")) return "pass";
    // This bridge operation only reads the local binding's config. The original
    // URL and its query and fragment never enter the process arguments.
    const result = await exec(`${home}/mods/jira-peek/runtime/jira-peek-bridge`,
      ["terminal-link", binding.configDir, url.origin, key], { timeout: 2500, on: null });
    if (result.code !== 0 || result.truncated) return "pass";
    const route = JSON.parse(result.stdout);
    if (route?.ok !== true || typeof route.stamp !== "string" || !/^[a-f0-9]{64}$/.test(route.stamp)) return "pass";
    // Recheck after the bridge returns in case the opt-in was removed or the
    // user moved to another terminal while the click was being resolved.
    if (await readTextFile(bindingPath) !== text || !stillAtSource(source)) return "pass";
    return openOverlay({
      mod: "jira-peek", kind: "dialog", width: 440, height: 540,
      props: { configDir: binding.configDir, linkPreview: { key, origin: url.origin, stamp: route.stamp } },
    }) ? "handled" : "pass";
  } catch {
    return "pass";
  }
}
