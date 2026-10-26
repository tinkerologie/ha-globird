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
    } else if (req.url === "/scoped-registry.js") {
      res.setHeader("Content-Type", "text/javascript");
      res.end(
        await readFile(
          "node_modules/@webcomponents/scoped-custom-element-registry/scoped-custom-element-registry.min.js",
        ),
      );
    } else if (req.url === "/early-registry") {
      res.setHeader("Content-Type", "text/html");
      res.end(`<!doctype html><html lang="en"><head><title>Early module reproduction</title></head><body><script type="module">
        await import("/cards.js");
        const tags=["globird-card-editor","globird-usage-cost-card","globird-electricity-usage-card","globird-latest-day-card","globird-account-card"];
        document.documentElement.dataset.beforePolyfill=String(tags.every(tag=>customElements.get(tag)));
        await new Promise((resolve,reject)=>{const script=document.createElement("script");script.src="/scoped-registry.js";script.onload=resolve;script.onerror=reject;document.head.append(script);});
        document.documentElement.dataset.afterPolyfill=String(tags.some(tag=>customElements.get(tag)));
      </script></body></html>`);
    } else if (req.url === "/harness.js") {
      res.setHeader("Content-Type", "text/javascript");
      res.end(harness.outputFiles[0].contents);
    } else {
      res.setHeader("Content-Type", "text/html");
      res.end(
        '<!doctype html><html lang="en"><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>GloBird synthetic dashboard</title></head><body><main id="cards"></main><script src="/scoped-registry.js"></script><script type="module" src="/harness.js"></script></body></html>',
      );
    }
  } catch {
    res.statusCode = 500;
    res.end("Test harness error");
  }
}).listen(4178, "127.0.0.1");
