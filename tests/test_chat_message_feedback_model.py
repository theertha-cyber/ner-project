import pytest
from sqlalchemy import text

pytestmark = [pytest.mark.verification, pytest.mark.asyncio]


class TestFeedbackTableIndependence:
    async def test_feedback_table_references_message_by_fk_not_embedded_column(self, engine, tenant_schema):
        _tid, schema = tenant_schema
        async with engine.begin() as conn:
            result = await conn.execute(
                text("""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_schema = :schema AND table_name = 'chat_message_feedback'
                """),
                {"schema": schema},
            )
            feedback_columns = {row[0] for row in result.fetchall()}

            result = await conn.execute(
                text("""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_schema = :schema AND table_name = 'chat_messages'
                """),
                {"schema": schema},
            )
            message_columns = {row[0] for row in result.fetchall()}

        assert "message_id" in feedback_columns
        assert "rating" in feedback_columns
        # chat_messages carries no rating/feedback column of its own — the
        # judgment lives only in chat_message_feedback.
        assert "rating" not in message_columns
        assert "feedback" not in message_columns

    async def test_message_id_is_unique_in_feedback_table(self, engine, tenant_schema):
        _tid, schema = tenant_schema
        async with engine.begin() as conn:
            result = await conn.execute(
                text("""
                    SELECT tc.constraint_type
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu
                        ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
                    WHERE tc.table_schema = :schema AND tc.table_name = 'chat_message_feedback'
                        AND kcu.column_name = 'message_id'
                """),
                {"schema": schema},
            )
            constraint_types = {row[0] for row in result.fetchall()}

        assert "UNIQUE" in constraint_types or "PRIMARY KEY" in constraint_types

    async def test_additive_column_can_be_added_without_breaking_existing_rows(self, engine, tenant_schema):
        """Simulates a future additive migration (e.g. adding `category`) — proves
        the standalone-table design absorbs new feedback attributes without
        touching chat_messages or existing rows."""
        _tid, schema = tenant_schema
        async with engine.begin() as conn:
            await conn.execute(text(f"""
                INSERT INTO {schema}.conversations (id, tenant_id, user_id) VALUES ('conv-x', 'test-tenant', 'u1')
            """))
            await conn.execute(text(f"""
                INSERT INTO {schema}.chat_messages (id, conversation_id, role, content, answer_kind)
                VALUES ('msg-x', 'conv-x', 'assistant', 'hi', 'answer')
            """))
            await conn.execute(text(f"""
                INSERT INTO {schema}.chat_message_feedback (id, message_id, tenant_id, user_id, rating)
                VALUES ('fb-x', 'msg-x', 'test-tenant', 'u1', 'up')
            """))

            await conn.execute(text(f"ALTER TABLE {schema}.chat_message_feedback ADD COLUMN IF NOT EXISTS category TEXT NULL"))

            result = await conn.execute(text(f"SELECT rating, category FROM {schema}.chat_message_feedback WHERE id = 'fb-x'"))
            row = result.fetchone()

        assert row.rating == "up"
        assert row.category is None
