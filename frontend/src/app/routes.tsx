import { createBrowserRouter } from "react-router-dom";

import { AppShell } from "./AppShell";
import { ComparePage } from "../features/compare/ComparePage";
import { DashboardPage } from "../features/dashboard/DashboardPage";
import { ExecutionPage } from "../features/execution/ExecutionPage";
import { HistoryPage } from "../features/history/HistoryPage";
import { RunDetailPage } from "../features/run-detail/RunDetailPage";
import { AIIntegrationSettingsPage } from "../features/settings/AIIntegrationSettingsPage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      {
        index: true,
        element: <DashboardPage />
      },
      {
        path: "execution",
        element: <ExecutionPage />
      },
      {
        path: "history",
        element: <HistoryPage />
      },
      {
        path: "compare",
        element: <ComparePage />
      },
      {
        path: "runs/:runId",
        element: <RunDetailPage />
      },
      {
        path: "settings/ai",
        element: <AIIntegrationSettingsPage />
      }
    ]
  }
]);
