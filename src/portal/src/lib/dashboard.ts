export function heroVariant(role: string): "a" | "b" {
  return role === "system_admin" ? "b" : "a";
}
