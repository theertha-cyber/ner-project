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

/**
 * Few-shot context for LLM pre-labeling only. Optional on an entity type — a type with no
 * QA pairs is still fully eligible for extraction, so this must never be treated as a
 * precondition for anything.
 */
export interface QaExample {
  question: string;
  answer: string;
}

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
  qa_examples?: QaExample[] | null;
  /** How the type came to exist — assigned at creation, immutable. */
  provenance?: "manual" | "suggested" | "imported";
  provenance_ref?: string | null;
}

export interface EntityTypeListResponse {
  entity_types: EntityType[];
}
