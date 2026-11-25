import { execFileSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const rootDir = path.resolve(__dirname, '..');
const distDir = path.join(rootDir, 'dist');

const WHEEL_URL =
  'https://files.pythonhosted.org/packages/ab/e4/7aa5601ecc4a424f75a24f9b74afae195bf4e106ab4ad597a551a246912a/openconstructionerp-19.9.0-py3-none-any.whl';

const pyScript = `
import lzma, os, shutil, sys, tempfile, urllib.request, zipfile
from pathlib import Path

dist = Path(sys.argv[1])
url = sys.argv[2]
if dist.exists():
    shutil.rmtree(dist)
dist.mkdir(parents=True, exist_ok=True)

with tempfile.NamedTemporaryFile(suffix=".whl", delete=True) as tmp:
    print(f"Downloading prebuilt v19.9.0 bundle from PyPI...", flush=True)
    urllib.request.urlretrieve(url, tmp.name)
    prefix = "app/_frontend_dist/"
    count = 0
    with zipfile.ZipFile(tmp.name) as z:
        for info in z.infolist():
            if not info.filename.startswith(prefix) or info.is_dir():
                continue
            rel = info.filename[len(prefix):]
            if not rel:
                continue
            data = z.read(info.filename)
            if rel.endswith(".xz"):
                rel = rel[:-3]
                data = lzma.decompress(data)
            out_path = dist / rel
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(data)
            count += 1
    print(f"Extracted and expanded {count} frontend files into {dist}", flush=True)
`;

if (process.env.FORCE_VITE_BUILD !== '1') {
  try {
    execFileSync('python3', ['-c', pyScript, distDir, WHEEL_URL], {
      cwd: rootDir,
      stdio: 'inherit',
    });
    if (existsSync(path.join(distDir, 'index.html'))) {
      console.log('Prebuilt v19.9.0 dist ready.');
      process.exit(0);
    }
  } catch (err) {
    console.warn('Prebuilt unpack failed, falling back to Vite build:', err);
  }
}

execFileSync('npm', ['install', '--no-audit', '--no-fund', '--legacy-peer-deps'], {
  cwd: rootDir,
  stdio: 'inherit',
});
execFileSync(
  'node',
  ['--max-old-space-size=4096', './node_modules/vite/bin/vite.js', 'build'],
  {
    cwd: rootDir,
    stdio: 'inherit',
    // Low-memory Rollup settings for the 8 GB test runner (see vite.config.ts).
    env: { ...process.env, OE_BUILD_LOW_MEMORY: '1' },
  },
);
