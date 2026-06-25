#!/usr/bin/env node
'use strict';

const sharp = require('sharp');
const fs = require('fs');
const path = require('path');

const args = process.argv.slice(2);
function getArg(flag, def) {
  const i = args.indexOf(flag);
  return i !== -1 && args[i + 1] ? args[i + 1] : def;
}

const DPI = parseFloat(getArg('--dpi', '96'));
const SVG_PATH = getArg('--svg', path.resolve(__dirname, '../src/lx-floor-package.svg'));
const OUT_PATH = getArg('--output', path.resolve(__dirname, '../output/lx-floor-package.png'));

fs.mkdirSync(path.dirname(OUT_PATH), { recursive: true });

sharp(fs.readFileSync(SVG_PATH), { density: DPI })
  .png({ compressionLevel: 9 })
  .toFile(OUT_PATH)
  .then(info => console.log(`[OK] Rendered: ${OUT_PATH} (${info.width}x${info.height}px) @ ${DPI}dpi`))
  .catch(err => { console.error('[ERR]', err.message); process.exit(1); });
