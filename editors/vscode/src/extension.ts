import * as vscode from "vscode";
import {
  LanguageClient,
  LanguageClientOptions,
  ServerOptions,
} from "vscode-languageclient/node";

const clients = new Map<string, LanguageClient>();

function folderKey(folder: vscode.WorkspaceFolder): string {
  return folder.uri.toString();
}

function documentSelector(folder: vscode.WorkspaceFolder): vscode.DocumentSelector {
  const pattern = new vscode.RelativePattern(folder, "**/*.qmd");
  return [
    { scheme: "file", language: "quarto", pattern },
    { scheme: "file", language: "markdown", pattern },
  ];
}

function serverCommand(): { command: string; extraArgs: string[] } {
  const config = vscode.workspace.getConfiguration("quartoNeeds.server");
  const command = config.get<string>("command", "quarto-needs").trim();
  const extraArgs = config.get<string[]>("extraArgs", []);
  return {
    command: command || "quarto-needs",
    extraArgs: extraArgs.filter((value) => typeof value === "string"),
  };
}

async function projectMarkerExists(folder: vscode.WorkspaceFolder): Promise<boolean> {
  try {
    await vscode.workspace.fs.stat(vscode.Uri.joinPath(folder.uri, ".quarto-needs.toml"));
    return true;
  } catch {
    return false;
  }
}

async function startClient(folder: vscode.WorkspaceFolder): Promise<void> {
  const key = folderKey(folder);
  if (clients.has(key)) {
    return;
  }
  if (!(await projectMarkerExists(folder))) {
    return;
  }

  const configured = serverCommand();
  const args = ["--root", folder.uri.fsPath, ...configured.extraArgs, "lsp"];
  const serverOptions: ServerOptions = {
    command: configured.command,
    args,
    options: { cwd: folder.uri.fsPath },
  };
  const clientOptions: LanguageClientOptions = {
    documentSelector: documentSelector(folder),
    workspaceFolder: folder,
    synchronize: {
      fileEvents: vscode.workspace.createFileSystemWatcher(
        new vscode.RelativePattern(folder, ".quarto-needs.toml"),
      ),
    },
  };
  const client = new LanguageClient(
    `quarto-needs-${folder.index}`,
    `Quarto-Needs (${folder.name})`,
    serverOptions,
    clientOptions,
  );
  clients.set(key, client);
  try {
    await client.start();
  } catch (error) {
    clients.delete(key);
    const message = error instanceof Error ? error.message : String(error);
    void vscode.window.showErrorMessage(
      `Could not start Quarto-Needs language server for ${folder.name}: ${message}`,
    );
  }
}

async function stopClient(folder: vscode.WorkspaceFolder): Promise<void> {
  const key = folderKey(folder);
  const client = clients.get(key);
  if (!client) {
    return;
  }
  clients.delete(key);
  await client.stop();
}

async function syncWorkspaceClients(): Promise<void> {
  const folders = vscode.workspace.workspaceFolders ?? [];
  const active = new Set(folders.map(folderKey));
  for (const [key, client] of clients) {
    if (!active.has(key)) {
      clients.delete(key);
      await client.stop();
    }
  }
  for (const folder of folders) {
    await startClient(folder);
  }
}

async function restartClients(): Promise<void> {
  const folders = vscode.workspace.workspaceFolders ?? [];
  for (const folder of folders) {
    await stopClient(folder);
  }
  for (const folder of folders) {
    await startClient(folder);
  }
}

function showOutput(): void {
  if (clients.size === 0) {
    void vscode.window.showInformationMessage(
      "No Quarto-Needs language server is active in this workspace.",
    );
    return;
  }
  const first = clients.values().next().value as LanguageClient | undefined;
  first?.outputChannel.show(true);
}

export async function activate(context: vscode.ExtensionContext): Promise<void> {
  context.subscriptions.push(
    vscode.commands.registerCommand(
      "quartoNeeds.restartLanguageServer",
      restartClients,
    ),
    vscode.commands.registerCommand(
      "quartoNeeds.showLanguageServerOutput",
      showOutput,
    ),
    vscode.workspace.onDidChangeWorkspaceFolders(syncWorkspaceClients),
    vscode.workspace.onDidChangeConfiguration(async (event) => {
      if (event.affectsConfiguration("quartoNeeds.server")) {
        await restartClients();
      }
    }),
  );
  await syncWorkspaceClients();
}

export async function deactivate(): Promise<void> {
  const running = [...clients.values()];
  clients.clear();
  await Promise.all(running.map((client) => client.stop()));
}
