import { redirect } from "next/navigation";

// Legacy route — the retraining decision surface is now step 4 of the Automated workflow.
export default function RetrainingLegacyRedirect() {
  redirect("/annotate/automated/retrain");
}
