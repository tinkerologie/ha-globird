import { execFileSync } from "node:child_process";

execFileSync(process.execPath, ["scripts/build.mjs"], { stdio: "inherit" });
const status = execFileSync(
  "git",
  [
    "status",
    "--porcelain",
    "--untracked-files=all",
    "--",
    "custom_components/globird/www",
  ],
  { cwd: "..", encoding: "utf8" },
);
if (status.trim())
  throw new Error(`Bundle differs from committed build:\n${status}`);
