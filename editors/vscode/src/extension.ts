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

function clientId(folder: vscode.WorkspaceFolder): string {
  const stable = folder
    .uri
    .toString()
    .replace(/[^A-Za-z0-9_-]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return `quarto-needs-${stable || "workspace"}`;
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
    await vscode.workspace.fs.stat(
      vscode.Uri.joinPath(folder.uri, ".quarto-needs.toml"),
    );
    return true;
  } catch {
    return false;
  }
}

async function startClient(folder: vscode.WorkspaceFolder): Promise<void> {
  const key = folderKey(folder);
  if (clients.has(key) || !(await projectMarkerExists(folder))) {
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
  };
  const client = new LanguageClient(
    clientId(folder),
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

async function stopClientByKey(key: string): Promise<void> {
  const client = clients.get(key);
  if (!client) {
    return;
  }
  clients.delete(key);
  await client.stop();
}

async function stopClient(folder: vscode.WorkspaceFolder): Promise<void> {
  await stopClientByKey(folderKey(folder));
}

async function desiredProjectFolders(): Promise<vscode.WorkspaceFolder[]> {
  const folders = vscode.workspace.workspaceFolders ?? [];
  const states = await Promise.all(
    folders.map(async (folder) => ({
      folder,
      enabled: await projectMarkerExists(folder),
    })),
  );
  return states.filter((state) => state.enabled).map((state) => state.folder);
}

async function syncWorkspaceClients(): Promise<void> {
  const desired = await desiredProjectFolders();
  const activeKeys = new Set(desired.map(folderKey));
  for (const key of [...clients.keys()]) {
    if (!activeKeys.has(key)) {
      await stopClientByKey(key);
    }
  }
  for (const folder of desired) {
    await startClient(folder);
  }
}

async function restartClients(): Promise<void> {
  const folders = await desiredProjectFolders();
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
  const markerWatcher = vscode.workspace.createFileSystemWatcher(
    "**/.quarto-needs.toml",
  );
  context.subscriptions.push(
    markerWatcher,
    markerWatcher.onDidCreate(syncWorkspaceClients),
    markerWatcher.onDidDelete(syncWorkspaceClients),
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
