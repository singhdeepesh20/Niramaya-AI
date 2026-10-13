import { dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { FlatCompat } from "@eslint/eslintrc";
import { defineConfig, globalIgnores } from "eslint/config";

const compat = new FlatCompat({ baseDirectory: dirname(fileURLToPath(import.meta.url)) });
const nextRules = [...compat.extends("next/core-web-vitals", "next/typescript")];

export default defineConfig([
  globalIgnores([".next/**", "out/**", "build/**", "next-env.d.ts"]),
  ...nextRules,
]);
