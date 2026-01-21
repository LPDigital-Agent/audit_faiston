"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/**
 * Asset Management Root Page
 *
 * Redirects to the dashboard as the default landing page
 * for the Gestão de Ativos platform.
 *
 * Note: Uses client-side redirect because server-side redirect()
 * doesn't work well with Next.js static export (output: "export").
 */
export default function AssetManagementPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/ferramentas/ativos/dashboard");
  }, [router]);

  return null;
}
