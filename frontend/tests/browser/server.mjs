import { readFile } from "node:fs/promises";
import { createServer } from "node:http";
import { build } from "esbuild";

const harness = await build({
  entryPoints: ["tests/browser/harness.ts"],
  bundle: true,
  format: "esm",
  write: false,
  target: "es2022",
});
createServer(async (req, res) => {
  try {
    if (req.url?.split("?")[0] === "/cards.js") {
      res.setHeader("Content-Type", "text/javascript");
      res.end(
        await readFile("../custom_components/globird/www/globird-cards.js"),
      );
    } else if (req.url === "/harness.js") {
      res.setHeader("Content-Type", "text/javascript");
      res.end(harness.outputFiles[0].contents);
    } else {
      res.setHeader("Content-Type", "text/html");
      res.end(
        '<!doctype html><html lang="en"><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>GloBird synthetic dashboard</title></head><body><main id="cards"></main><script type="module" src="/harness.js"></script></body></html>',
      );
    }
  } catch {
    res.statusCode = 500;
    res.end("Test harness error");
  }
}).listen(4178, "127.0.0.1");
