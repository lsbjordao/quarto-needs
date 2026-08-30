const assert = require("node:assert/strict");
const vscode = require("vscode");

async function eventually(operation, predicate, timeoutMs = 15000) {
  const deadline = Date.now() + timeoutMs;
  let last;
  while (Date.now() < deadline) {
    last = await operation();
    if (predicate(last)) {
      return last;
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  return last;
}

function hoverText(hovers) {
  return hovers
    .flatMap((hover) => hover.contents ?? [])
    .map((content) => {
      if (typeof content === "string") {
        return content;
      }
      if (content && typeof content.value === "string") {
        return content.value;
      }
      return String(content ?? "");
    })
    .join("\n");
}

async function run() {
  const extension = vscode.extensions.getExtension("lsbjordao.quarto-needs-vscode");
  assert.ok(extension, "Quarto-Needs extension is available in the Extension Host");
  await extension.activate();
  assert.equal(extension.isActive, true);

  const commands = await vscode.commands.getCommands(true);
  assert.ok(commands.includes("quartoNeeds.restartLanguageServer"));
  assert.ok(commands.includes("quartoNeeds.showLanguageServerOutput"));

  const folders = vscode.workspace.workspaceFolders ?? [];
  assert.equal(folders.length, 1, "smoke fixture opens as a single workspace folder");
  const uri = vscode.Uri.joinPath(folders[0].uri, "model.qmd");
  const document = await vscode.workspace.openTextDocument(uri);
  await vscode.window.showTextDocument(document);
  assert.equal(document.languageId, "markdown");

  const line = document.lineAt(0).text;
  const start = line.indexOf("FUN-001");
  assert.ok(start >= 0);
  const position = new vscode.Position(0, start + 2);
  const hovers = await eventually(
    () => vscode.commands.executeCommand("vscode.executeHoverProvider", uri, position),
    (value) => Array.isArray(value) && value.length > 0,
  );

  assert.ok(Array.isArray(hovers) && hovers.length > 0, "Python LSP supplies hover through vscode-languageclient");
  const text = hoverText(hovers);
  assert.match(text, /FUN-001/);
  assert.match(text, /Smoke requirement/);
}

module.exports = { run };
