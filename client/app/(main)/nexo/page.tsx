"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/**
 * NEXO AI Root Page
 *
 * Redirects to the chat as the default landing page.
 */
export default function NexoPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/nexo/chat");
  }, [router]);

  return null;
}
