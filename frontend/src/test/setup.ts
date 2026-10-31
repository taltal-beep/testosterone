import "@testing-library/jest-dom/vitest";
import { configure } from "@testing-library/react";

// waitFor/findBy* give up after 1 s by default. getByRole on a full page in
// jsdom can take most of that on a busy CI runner, so the happy-path walk
// flaked there ("Unable to find role=link") while passing locally.
configure({ asyncUtilTimeout: 5000 });
