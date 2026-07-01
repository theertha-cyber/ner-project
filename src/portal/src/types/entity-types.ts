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
}

export interface EntityTypeListResponse {
  entity_types: EntityType[];
}
