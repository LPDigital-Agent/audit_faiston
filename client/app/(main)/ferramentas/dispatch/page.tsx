"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/**
 * Dispatch Center Root Page
 *
 * Redirects to the dashboard as the default landing page.
 */
export default function DispatchCenterPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/ferramentas/dispatch/dashboard");
  }, [router]);

  return null;
}
