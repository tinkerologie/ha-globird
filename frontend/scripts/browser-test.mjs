import { spawnSync } from "node:child_process";

const env = { ...process.env };
delete env.NO_COLOR;
const result = spawnSync(
  process.execPath,
  ["node_modules/@playwright/test/cli.js", "test", ...process.argv.slice(2)],
  { stdio: "inherit", env },
);
process.exitCode = result.status ?? 1;
