def apply_to_all_tenant_schemas(op, ddl_template: str):
    op.execute(ddl_template.format(schema="tenant_template"))
    op.execute("""
        DO $$
        DECLARE
            schema_name TEXT;
        BEGIN
            FOR schema_name IN
                SELECT nspname FROM pg_namespace
                WHERE nspname LIKE 'tenant\_%' AND nspname != 'tenant_template'
            LOOP
                EXECUTE format('{ddl_body}', schema_name);
            END LOOP;
        END $$;
    """.replace("{ddl_body}", ddl_template.replace("'", "''").replace("{schema}", "%I")))
