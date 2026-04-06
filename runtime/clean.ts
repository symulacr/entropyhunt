import { existsSync, rmSync } from 'node:fs';
import { resolve } from 'node:path';
for (const path of [resolve('runtime', 'logs'), resolve('runtime', 'snapshots'), resolve('runtime', 'proofs.jsonl'), resolve('runtime', 'session.json')]) {
  if (existsSync(path)) rmSync(path, { recursive: true, force: true });
}
