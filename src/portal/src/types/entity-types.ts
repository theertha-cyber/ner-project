/**
 * `cardinality` decides which generated relation holds an entity type's extracted values: a
 * `single` type becomes one typed column on the tenant's `subject` table, a `multi` type gets
 * its own child table. `value_kind` decides that column's type, which is what makes
 * `WHERE years_experience > 5` possible rather than a string comparison.
 *
 * `sql_identifier` is system-assigned at create and never changes, so it is read-only here:
 * it appears on responses and is never sent back in a payload.
 */
export type EntityCardinality = "single" | "multi";

export interface EntityType {
  id: string;
  name: string;
  description: string;
  examples: string[];
  base_label_mapping: Record<string, string[]>;
  target_table: string | null;
  required_flag: boolean;
  is_active: boolean;
  version: number;
  cardinality: EntityCardinality;
  value_kind: string;
  sql_identifier: string | null;
}

export interface EntityTypeListResponse {
  entity_types: EntityType[];
}
