"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

// Model registry merged into the Models & Training section.
export default function ModelsPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/training-jobs");
  }, [router]);

  return null;
}
