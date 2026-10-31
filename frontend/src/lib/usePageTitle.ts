import { useEffect } from "react";

const APP = "Testosterone";

/**
 * Names the browser tab (and what a screen reader announces on navigation)
 * after the page: "Runs · Testosterone". Every route shared one title before.
 */
export function usePageTitle(title: string | undefined) {
  useEffect(() => {
    if (title) document.title = `${title} · ${APP}`;
  }, [title]);
}
