import { spawn } from "node:child_process";
import { once } from "node:events";
import fs from "node:fs";
import http from "node:http";
import os from "node:os";
import path from "node:path";

const [siteArgument, chromeExecutable, startupBudgetArgument] = process.argv.slice(2);
// The caller decides how long a browser start may take, because the caller is
// the one holding the outer timeout. A budget hardcoded here once matched that
// outer timeout exactly, so this script was killed mid-report every time and
// the failure below never reached anyone.
const startupBudgetMs = Number(startupBudgetArgument ?? 30_000);
if (!Number.isFinite(startupBudgetMs) || startupBudgetMs <= 0) {
  throw new Error(`startup budget must be a positive number of milliseconds, got ${startupBudgetArgument}`);
}
if (!siteArgument || !chromeExecutable) {
  throw new Error("usage: margin_sidebar_transition.mjs SITE_DIR CHROME_EXECUTABLE");
}
if (typeof WebSocket === "undefined") {
  throw new Error("this probe requires Node.js 22 or newer");
}

const siteDirectory = path.resolve(siteArgument);
const contentTypes = new Map([
  [".css", "text/css"],
  [".html", "text/html; charset=utf-8"],
  [".js", "text/javascript"],
  [".json", "application/json"],
  [".png", "image/png"],
  [".svg", "image/svg+xml"],
  [".woff", "font/woff"],
  [".woff2", "font/woff2"],
]);
const delay = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));

function serveSite(request, response) {
  const requestUrl = new URL(request.url ?? "/", "http://127.0.0.1");
  const relativePath = decodeURIComponent(requestUrl.pathname).replace(/^\/+/, "");
  const requestedPath = path.resolve(siteDirectory, relativePath || "index.html");
  const insideSite =
    requestedPath === siteDirectory || requestedPath.startsWith(`${siteDirectory}${path.sep}`);
  if (!insideSite || !fs.existsSync(requestedPath) || !fs.statSync(requestedPath).isFile()) {
    response.writeHead(404);
    response.end("Not found");
    return;
  }

  response.writeHead(200, {
    "Content-Type": contentTypes.get(path.extname(requestedPath)) ?? "application/octet-stream",
  });
  fs.createReadStream(requestedPath).pipe(response);
}

async function waitForFile(file, chrome, diagnostics) {
  // Chrome's own stderr is the only thing that explains a failed start, and a
  // CI runner is exactly where that happens. Report it, and stop as soon as
  // the process is gone instead of polling out the full budget.
  const pollMs = 50;
  const attempts = Math.max(1, Math.ceil(startupBudgetMs / pollMs));
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    if (fs.existsSync(file)) return;
    if (chrome.exitCode !== null || chrome.signalCode !== null) {
      throw new Error(
        `Chrome exited (code=${chrome.exitCode}, signal=${chrome.signalCode}) ` +
          `before creating ${file}.\nChrome output:\n${diagnostics() || "(none)"}`,
      );
    }
    await delay(pollMs);
  }
  throw new Error(
    `Chrome did not create ${file} within ${startupBudgetMs}ms. It was still ` +
      `running, so it started but never opened its debugging port.\n` +
      `Chrome output:\n${diagnostics() || "(none)"}`,
  );
}

function connect(socket) {
  return new Promise((resolve, reject) => {
    socket.addEventListener("open", resolve, { once: true });
    socket.addEventListener("error", reject, { once: true });
  });
}

function protocol(socket) {
  let nextId = 1;
  const pending = new Map();

  socket.addEventListener("message", (event) => {
    const message = JSON.parse(event.data);
    if (!message.id || !pending.has(message.id)) return;
    const handlers = pending.get(message.id);
    pending.delete(message.id);
    if (message.error) handlers.reject(new Error(JSON.stringify(message.error)));
    else handlers.resolve(message.result);
  });

  return (method, params = {}) =>
    new Promise((resolve, reject) => {
      const id = nextId;
      nextId += 1;
      pending.set(id, { resolve, reject });
      socket.send(JSON.stringify({ id, method, params }));
    });
}

async function runProbe() {
  const server = http.createServer(serveSite);
  server.listen(0, "127.0.0.1");
  await once(server, "listening");
  const address = server.address();
  if (!address || typeof address === "string") throw new Error("HTTP server has no TCP address");

  const profile = fs.mkdtempSync(path.join(os.tmpdir(), "qn-margin-sidebar-chrome-"));
  const chrome = spawn(
    chromeExecutable,
    [
      "--headless",
      "--no-sandbox",
      // Containerised CI mounts a small /dev/shm; without this Chrome can die
      // during startup before it ever writes DevToolsActivePort.
      "--disable-dev-shm-usage",
      "--disable-extensions",
      "--disable-gpu",
      "--no-default-browser-check",
      "--no-first-run",
      "--remote-allow-origins=*",
      "--remote-debugging-port=0",
      `--user-data-dir=${profile}`,
      "about:blank",
    ],
    { stdio: ["ignore", "pipe", "pipe"] },
  );

  const chromeOutput = [];
  const captureOutput = (chunk) => {
    chromeOutput.push(chunk.toString());
    if (chromeOutput.length > 200) chromeOutput.shift();
  };
  chrome.stdout.on("data", captureOutput);
  chrome.stderr.on("data", captureOutput);
  const diagnostics = () => chromeOutput.join("").trim();

  let socket;
  let send;
  try {
    const activePort = path.join(profile, "DevToolsActivePort");
    await waitForFile(activePort, chrome, diagnostics);
    const [debuggingPort] = fs.readFileSync(activePort, "utf8").trim().split("\n");
    const targets = await fetch(`http://127.0.0.1:${debuggingPort}/json/list`).then((response) =>
      response.json(),
    );
    const page = targets.find((target) => target.type === "page");
    if (!page) throw new Error("Chrome exposed no page target");

    socket = new WebSocket(page.webSocketDebuggerUrl);
    await connect(socket);
    send = protocol(socket);
    await send("Runtime.enable");
    await send("Page.enable");

    const evaluate = async (expression) => {
      const result = await send("Runtime.evaluate", {
        expression,
        awaitPromise: true,
        returnByValue: true,
      });
      if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
      return result.result.value;
    };

    const waitUntil = async (expression) => {
      for (let attempt = 0; attempt < 200; attempt += 1) {
        if (await evaluate(expression)) return;
        await delay(50);
      }
      throw new Error(`Timed out waiting for ${expression}`);
    };

    const settleLayout = () =>
      evaluate("new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)))");

    const measure = () =>
      evaluate(`(() => {
        const left = document.getElementById("quarto-sidebar");
        const margin = document.getElementById("quarto-margin-sidebar");
        const toggle = document.querySelector(".qn-margin-sidebar-toggle");
        return {
          innerWidth: window.innerWidth,
          leftDisplay: getComputedStyle(left).display,
          marginDisplay: getComputedStyle(margin).display,
          marginWidth: margin.getBoundingClientRect().width,
          toggleDisplay: getComputedStyle(toggle).display,
          bodyCollapsed: document.body.classList.contains("qn-margin-sidebar-collapsed"),
          storedCollapsed: localStorage.getItem("quarto-needs:margin-sidebar-collapsed"),
        };
      })()`);

    await send("Emulation.setDeviceMetricsOverride", {
      width: 1200,
      height: 800,
      deviceScaleFactor: 1,
      mobile: false,
    });
    const pageUrl = `http://127.0.0.1:${address.port}/index.html`;
    await send("Page.navigate", { url: pageUrl });
    await waitUntil(`document.readyState === "complete" && location.href === ${JSON.stringify(pageUrl)}`);
    await settleLayout();
    const expanded = await measure();

    await evaluate('document.querySelector(".qn-margin-sidebar-toggle").click()');
    await settleLayout();
    const collapsed = await measure();

    await send("Emulation.setDeviceMetricsOverride", {
      width: 991,
      height: 800,
      deviceScaleFactor: 1,
      mobile: false,
    });
    await waitUntil("window.innerWidth === 991");
    await settleLayout();
    const responsive = await measure();

    return { expanded, collapsed, responsive };
  } finally {
    if (chrome.exitCode === null && chrome.signalCode === null) {
      const exited = once(chrome, "exit");
      const shutdownTimeout = setTimeout(() => chrome.kill("SIGKILL"), 5000);
      try {
        if (send && socket.readyState === WebSocket.OPEN) {
          // Let Chrome flush its profile before deleting it. Wait for process
          // exit: the DevTools socket may close before Browser.close replies.
          void send("Browser.close").catch(() => chrome.kill("SIGTERM"));
        } else {
          chrome.kill("SIGTERM");
        }
        await exited;
      } finally {
        clearTimeout(shutdownTimeout);
      }
    }
    if (socket) socket.close();
    await new Promise((resolve) => server.close(resolve));
    // Chrome's child processes can finish writing the profile after the main
    // process exits. Retry transient cleanup races without hiding failures.
    fs.rmSync(profile, { force: true, recursive: true, maxRetries: 5, retryDelay: 100 });
  }
}

process.stdout.write(`${JSON.stringify(await runProbe())}\n`);
