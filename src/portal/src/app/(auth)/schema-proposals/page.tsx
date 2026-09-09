import { redirect } from "next/navigation";

// Legacy route — the schema proposal screen is now step 1 of the Automated workflow.
export default function SchemaProposalsLegacyRedirect() {
  redirect("/annotate/automated/schema");
}
