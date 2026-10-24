// Lint config for the React UI. Type checking stays with `tsc` (npm run typecheck);
// this catches what the compiler does not: hook rules, unused code, suspicious patterns.
import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist/", "src/lib/api-schema.ts"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["**/*.{ts,tsx}"],
    languageOptions: { globals: { ...globals.browser } },
    plugins: { "react-hooks": reactHooks },
    rules: {
      // The classic hook rules. The plugin's newer React Compiler rules (e.g.
      // set-state-in-effect) would flag the form-sync effects this app relies on.
      "react-hooks/rules-of-hooks": "error",
      "react-hooks/exhaustive-deps": "warn",
      "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_", varsIgnorePattern: "^_" }],
    },
  },
  {
    files: ["*.config.{js,ts,cjs}", "vite.config.ts"],
    languageOptions: { globals: { ...globals.node } },
  },
);
