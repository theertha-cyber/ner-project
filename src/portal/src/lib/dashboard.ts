export function heroVariant(_role: string): "a" | "b" {
  // The design uses the elevated dark gradient hero card for every role's
  // dashboard, not just system_admin.
  return "b";
}
