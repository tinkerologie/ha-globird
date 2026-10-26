import { writeFile } from "node:fs/promises";
import { build } from "esbuild";

const result = await build({
  entryPoints: ["src/index.ts"],
  bundle: true,
  format: "esm",
  target: "es2022",
  minify: true,
  legalComments: "eof",
  write: false,
  outfile: "../custom_components/globird/www/globird-cards.js",
});
// Esbuild preserves literal tabs in Lit's whitespace regex strings. Escaping
// those tabs keeps the same regex while avoiding trailing whitespace in Git.
await writeFile(
  result.outputFiles[0].path,
  result.outputFiles[0].text.replaceAll("\t", "\\t"),
);
