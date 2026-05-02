import { createBrowserRouter } from "react-router-dom";

import { AppShell } from "./AppShell";
import { ExecutionPage } from "../features/execution/ExecutionPage";
import { HistoryPage } from "../features/history/HistoryPage";
import { RunDetailPage } from "../features/run-detail/RunDetailPage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      {
        index: true,
        element: <ExecutionPage />
      },
      {
        path: "history",
        element: <HistoryPage />
      },
      {
        path: "runs/:runId",
        element: <RunDetailPage />
      }
    ]
  }
]);
