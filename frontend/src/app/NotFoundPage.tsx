import { Link } from "react-router-dom";

import { MuscleShrug } from "../components/mascot";
import { Button, EmptyState } from "../components/ui";

export function NotFoundPage() {
  return (
    <EmptyState
      mascot={<MuscleShrug />}
      title="Page not found"
      message="There is nothing at this address."
      action={
        <Link to="/">
          <Button size="sm">Go to dashboard</Button>
        </Link>
      }
    />
  );
}
