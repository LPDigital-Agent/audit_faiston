"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/**
 * Faiston Academy Root Page
 *
 * Redirects to the dashboard as the default landing page.
 */
export default function FaistonAcademyPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/ferramentas/academy/dashboard");
  }, [router]);

  return null;
}
