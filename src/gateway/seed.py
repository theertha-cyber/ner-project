"""Seed script: create bootstrap System Admin user and a demo tenant."""
import asyncio
import uuid
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from src.shared.auth import hash_password

async def seed():
    from src.shared.config import settings
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as db:
        system_tenant_id = "system"
        tenant_result = await db.execute(
            text("SELECT id FROM public.tenants WHERE id = :id"),
            {"id": system_tenant_id},
        )
        if not tenant_result.fetchone():
            await db.execute(
                text("""
                    INSERT INTO public.tenants (id, name, slug, status)
                    VALUES (:id, 'System', 'system', 'active')
                """),
                {"id": system_tenant_id},
            )
            print("Created system tenant")

        admin_id = str(uuid.uuid4())
        admin_email = "admin@nerplatform.io"
        admin_password = hash_password("Admin123!")

        result = await db.execute(
            text("SELECT id FROM public.tenant_users WHERE email = :email AND role = 'system_admin'"),
            {"email": admin_email},
        )
        if not result.fetchone():
            await db.execute(
                text("""
                    INSERT INTO public.tenant_users (id, tenant_id, email, password_hash, role, status)
                    VALUES (:id, 'system', :email, :pwd, 'system_admin', 'active')
                """),
                {"id": admin_id, "email": admin_email, "pwd": admin_password},
            )
            print(f"Created System Admin: {admin_email} / Admin123!")
        else:
            print("System Admin already exists")

        await db.commit()

    await engine.dispose()
    print("Seed complete")


if __name__ == "__main__":
    asyncio.run(seed())
