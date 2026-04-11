/**
 * Renders each React Email template to a self-contained HTML file and writes
 * the output to backend/app/core/email_templates/.
 *
 * Dynamic values (URLs, etc.) are left as {{PLACEHOLDER}} tokens so the Python
 * backend can do a simple string replacement before sending.
 *
 * Run: npm run build
 */
import { render } from "@react-email/render";
import * as fs from "fs";
import * as path from "path";
import * as React from "react";
import { VerifyEmail } from "../emails/VerifyEmail";
import { ResetPassword } from "../emails/ResetPassword";

const OUTPUT_DIR = path.resolve(
  __dirname,
  "../../backend/app/core/email_templates"
);

async function buildTemplate(
  name: string,
  element: React.ReactElement
): Promise<void> {
  const html = await render(element);
  const outPath = path.join(OUTPUT_DIR, `${name}.html`);
  fs.writeFileSync(outPath, html, "utf-8");
  console.log(`✓ ${name}.html → ${outPath}`);
}

async function main() {
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });

  await buildTemplate("verify_email", React.createElement(VerifyEmail));
  await buildTemplate("reset_password", React.createElement(ResetPassword));

  console.log("\nBuild complete. Commit the generated HTML files.");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
