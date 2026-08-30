const path = require("node:path");
const { runTests } = require("@vscode/test-electron");

async function main() {
  const extensionDevelopmentPath = path.resolve(__dirname, "..");
  const extensionTestsPath = path.resolve(__dirname, "suite", "index.cjs");
  const testWorkspace = path.resolve(__dirname, "fixture");

  await runTests({
    extensionDevelopmentPath,
    extensionTestsPath,
    launchArgs: [testWorkspace],
  });
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
