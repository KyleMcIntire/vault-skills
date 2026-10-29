#!/usr/bin/env node
// Render a Mermaid diagram to a themed SVG with pele, then to a PNG with headless Chrome.
// Usage: node render.mjs <diagram.mmd | -> --out <dir> [--name diagram] [--theme warm-dark|warm-light|light|dark]
//                        [--theme-file theme.json] [--scale 2] [--padding 24] [--no-png]
// Environment: PELE_DIR (where pele is installed, default ~/.local/share/pele), CHROME (browser binary).
// Prints one JSON line: {"svg": ..., "png": ..., "width": ..., "height": ...}. Errors go to stderr, exit 1.
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";

const PELE_DIR = process.env.PELE_DIR || path.join(os.homedir(), ".local/share/pele");
const CHROME_CANDIDATES = [
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  "/Applications/Chromium.app/Contents/MacOS/Chromium",
  "/usr/bin/google-chrome", "/usr/bin/google-chrome-stable", "/usr/bin/chromium", "/usr/bin/chromium-browser",
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
];
const CHROME = process.env.CHROME || CHROME_CANDIDATES.find((p) => fs.existsSync(p)) || CHROME_CANDIDATES[0];

// Pele colours come from CSS variables (https://pele.run/theming); these are the two presets.
const THEMES = {
  light: { bg: "#fffcf0", fg: "#100f0f", muted: "#6f6e69", line: "#100f0f", surface: "#f2f0e5",
           "surface-alt": "#e6e4d9", border: "#cecdc3", accent: "#205ea6" },
  dark: { bg: "#1c1b1a", fg: "#cecdc3", muted: "#878580", line: "#9f9d96", surface: "#282726",
          "surface-alt": "#343331", border: "#403e3c", accent: "#4385be" },
};

// Default accent series for charts (the public Gruvbox Material accents); a theme file can override any key.
const ACCENTS = ["#ea6962", "#e78a4e", "#d8a657", "#a9b665", "#89b482", "#7daea3", "#d3869b", "#a89984"];
// Warm greys with an orange accent. muted and line are estimates from neighbouring greys.
THEMES["warm-dark"] = { bg: "#2e261f", fg: "#d7c0a3", muted: "#b59873", line: "#c7b194", surface: "#342c23",
  "surface-alt": "#3b3026", border: "#4b3c30", accent: "#e78a4e" };
THEMES["warm-light"] = { bg: "#f8f5f1", fg: "#593e22", muted: "#8b6c4b", line: "#593e22", surface: "#f2ece3",
  "surface-alt": "#eee7dd", border: "#e4d7c3", accent: "#e8760a" };
for (const t of ["warm-dark", "warm-light"]) ACCENTS.forEach((c, i) => { THEMES[t][`series-${i + 1}`] = c; });

function die(msg) { console.error(`mermaid-image: ${msg}`); process.exit(1); }

const args = process.argv.slice(2);
const opt = { theme: "warm-dark", scale: 2, padding: 24, name: "diagram", png: true };
let input = null;
for (let i = 0; i < args.length; i++) {
  const a = args[i];
  if (a === "--out") opt.out = args[++i];
  else if (a === "--name") opt.name = args[++i];
  else if (a === "--theme") opt.theme = args[++i];
  else if (a === "--theme-file") opt.themeFile = args[++i];
  else if (a === "--scale") opt.scale = Number(args[++i]);
  else if (a === "--padding") opt.padding = Number(args[++i]);
  else if (a === "--no-png") opt.png = false;
  else if (input === null) input = a;
  else die(`unexpected argument ${a}`);
}
if (input === null) die("usage: render.mjs <diagram.mmd | -> --out <dir> [--theme warm-dark|warm-light|light|dark] [--theme-file theme.json]");
if (!opt.out) die("--out <dir> is required");
if (opt.themeFile) {
  // A JSON object of pele variables (bg, fg, muted, line, surface, surface-alt, border, accent, series-1..8) that
  // overrides the chosen preset, so a vault can match its own colours without editing this script.
  let custom;
  try { custom = JSON.parse(fs.readFileSync(opt.themeFile, "utf8")); } catch (e) { die(`cannot read theme file: ${e.message}`); }
  THEMES[opt.theme] = { ...(THEMES[opt.theme] || THEMES.dark), ...custom };
}
if (!THEMES[opt.theme]) die(`unknown theme ${opt.theme} (light, dark, warm-dark or warm-light)`);
if (!/^[\w.-]+$/.test(opt.name)) die("--name may only contain letters, digits, dot, dash and underscore");

const text = input === "-" ? fs.readFileSync(0, "utf8") : fs.readFileSync(input, "utf8");
const entry = path.join(PELE_DIR, "node_modules/pele/dist/pele.js");
if (!fs.existsSync(entry)) die(`pele not installed at ${PELE_DIR}; run: mkdir -p "${PELE_DIR}" && cd "${PELE_DIR}" && npm init -y && npm install pele --ignore-scripts`);
const { render } = await import(pathToFileURL(entry).href);

let result;
try { result = render(text.replace(/^```mermaid\s*\n|\n```\s*$/g, "")); }
catch (e) { die(`pele could not render the diagram: ${e.message}`); }

const vars = Object.entries(THEMES[opt.theme]).map(([k, v]) => `--pele-${k}:${v}`).join(";");
fs.mkdirSync(opt.out, { recursive: true });
const svgPath = path.join(opt.out, `${opt.name}.svg`);
// Bake the theme into the SVG so it looks the same wherever it is opened.
const svg = result.svg.replace('class="pele ', `class="pele ${"pele-" + opt.theme} `)
  .replace('style="', `style="${vars};`);
fs.writeFileSync(svgPath, svg);

const out = { svg: svgPath, png: null, width: result.width, height: result.height };
if (opt.png) {
  if (!fs.existsSync(CHROME)) die(`Chrome or Chromium not found (tried ${CHROME}); set CHROME to a browser binary or use --no-png`);
  const w = Math.ceil(result.width + 2 * opt.padding), h = Math.ceil(result.height + 2 * opt.padding);
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "mermaid-image-"));
  const html = path.join(tmp, "page.html");
  fs.writeFileSync(html, `<!doctype html><meta charset="utf-8"><style>html,body{margin:0;background:${THEMES[opt.theme].bg}}` +
    `body{padding:${opt.padding}px;width:${result.width}px;height:${result.height}px}svg{display:block;max-width:none!important}</style>${svg}`);
  const png = path.join(opt.out, `${opt.name}.png`);
  // A throwaway profile keeps this from touching, or waiting on, a running Chrome.
  execFileSync(CHROME, ["--headless=new", "--disable-gpu", "--hide-scrollbars", `--user-data-dir=${path.join(tmp, "profile")}`,
    `--force-device-scale-factor=${opt.scale}`, `--window-size=${w},${h}`, `--screenshot=${png}`, pathToFileURL(html).href],
    { stdio: ["ignore", "ignore", "ignore"], timeout: 60000 });
  fs.rmSync(tmp, { recursive: true, force: true });
  if (!fs.existsSync(png)) die("Chrome did not write the PNG");
  out.png = png;
}
console.log(JSON.stringify(out));
