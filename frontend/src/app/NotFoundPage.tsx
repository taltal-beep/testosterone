import { Link } from "react-router-dom";

import { MuscleShrug } from "../components/mascot";
import { EmptyState, buttonClasses } from "../components/ui";
import { usePageTitle } from "../lib/usePageTitle";

export function NotFoundPage() {
  usePageTitle("Page not found");
  return (
    <EmptyState
      headingLevel={1}
      mascot={<MuscleShrug />}
      title="Page not found"
      message="There is nothing at this address."
      action={
        <Link to="/" className={buttonClasses("primary", "sm")}>
          Go to dashboard
        </Link>
      }
    />
  );
}
