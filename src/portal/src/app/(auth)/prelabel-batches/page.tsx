import { redirect } from "next/navigation";

// Legacy route — batch pre-labeling is now step 2 of the Automated workflow.
export default function PrelabelBatchesLegacyRedirect() {
  redirect("/annotate/automated/prelabel");
}
