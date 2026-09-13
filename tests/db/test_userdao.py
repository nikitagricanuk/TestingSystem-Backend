import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.models.database import Base, Role, Permission, User
from app.repositories.dao.userdao import UserDAO, RoleEnum
import uuid

@pytest.mark.asyncio
class TestUserDAO:
    @pytest_asyncio.fixture
    async def test_session(self):
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async_session_maker = async_sessionmaker(engine, expire_on_commit=False)
        async with async_session_maker() as session:
            # --- create schools ---
            from app.models.database import School, Settlement, Region
            # Create regions
            region1 = Region(id=uuid.UUID("0e684a53-8b67-4aac-b57b-bd56ebfe6cc9"), region="Irkutsk Oblast")
            region2 = Region(id=uuid.UUID("9f5fd2af-06d3-4cd0-be98-b390f7abdb74"), region="Novosibirsk Oblast")
            session.add_all([region1, region2])
            # Create settlements (cities)
            city1 = Settlement(
                id=uuid.UUID("a4a6d71d-9176-4a14-a184-80ab478e746b"),
                name="Irkutsk",
                type="city",
                region_id=region1.id,
            )
            city2 = Settlement(
                id=uuid.UUID("fe7018ed-dc9e-4330-8968-258c736ee30b"),
                name="Novosibirsk",
                type="city",
                region_id=region2.id,
            )
            session.add_all([city1, city2])
            # Create schools with new schema
            school1 = School(
                id=uuid.UUID("e0679bf7-a980-4643-904b-cae6264eefa3"),
                full_name="Lyceum No. 1",
                short_name="Lyceum 1",
                city_id=city1.id,
            )
            school2 = School(
                id=uuid.UUID("bebecb88-0f97-4297-a818-4fe4cd98af64"),
                full_name="Gymnasium No. 3",
                short_name="Gym 3",
                city_id=city2.id,
            )
            session.add_all([school1, school2])

            # --- seed roles ---
            admin_role = Role(id=uuid.UUID("e39ee8be-9f09-4818-81fc-8ed56ff5ed75"), role="admin")
            student_role = Role(id=uuid.UUID("c6cb0394-d382-46d2-b932-f559c05bfa9c"), role="student")

            # --- seed permissions ---
            perm_read_users = Permission(id=uuid.uuid4(), name="read_users", description="Can read users")
            perm_write_users = Permission(id=uuid.uuid4(), name="write_users", description="Can create or update users")
            perm_manage_roles = Permission(id=uuid.uuid4(), name="manage_roles", description="Can assign roles and permissions")

            # --- assign permissions to roles ---
            # Admin gets broad permissions
            admin_role.permissions.append(perm_read_users)
            admin_role.permissions.append(perm_write_users)
            admin_role.permissions.append(perm_manage_roles)
            # Student gets no user-management permissions on purpose
            # (kept empty to satisfy tests that expect lack of permission)

            session.add_all([
                admin_role,
                student_role,
                perm_read_users,
                perm_write_users,
                perm_manage_roles,
            ])
            await session.commit()
            # Attach schools to session for test use
            session.admin_school = school1
            session.student_school = school2
            yield session

    async def test_create_user(self, test_session):
        dao = UserDAO()
        user = await dao.create(
            full_name="John B. Doe",
            nickname="Johnny",
            age=20,
            email="john@example.com",
            phone="1234567890",
            password="securepassword123",
            role=uuid.UUID("e39ee8be-9f09-4818-81fc-8ed56ff5ed75"),
            school=test_session.admin_school,
            session=test_session
        )
        from sqlalchemy import select
        result = await test_session.execute(
            select(User).where(User.email == "john@example.com")
        )
        user_obj = result.scalar_one_or_none()
        assert user_obj is not None
        assert user_obj.full_name == "John B. Doe"

    async def test_get_user_by_id(self, test_session):
        dao = UserDAO()
        user = await dao.create(
            full_name="Jane A. Smith",
            nickname="Janie",
            age=22,
            email="mail@newmail.com",
            phone="0987654321",
            password="anotherpassword123",
            role=uuid.UUID("c6cb0394-d382-46d2-b932-f559c05bfa9c"),
            school=test_session.student_school,
            session=test_session
        )
        user_id = user.id
        retrieved_user = await dao.get_user_by_id(user_id, session=test_session)
        assert retrieved_user is not None
        assert retrieved_user.id == user_id
        assert retrieved_user.full_name == "Jane A. Smith"

    async def test_update_user_by_id(self, test_session):
        dao = UserDAO()
        user = await dao.create(
            full_name="Alice C. Johnson",
            nickname="Al",
            age=25,
            email="test@test.com",
            phone="1122334455",
            password="password123",
            role=uuid.UUID("c6cb0394-d382-46d2-b932-f559c05bfa9c"),
            school=test_session.student_school,
            session=test_session
        )
        user_id = user.id
        updated_data = {
            "full_name": "Alice Updated",
            "age": 26
        }
        updated_user = await dao.update_user_by_id(user_id, updated_data, session=test_session)
        assert updated_user is not None
        assert updated_user.full_name == "Alice Updated"
        assert updated_user.age == 26

    async def test_update_user_by_email(self, test_session):
        dao = UserDAO()
        user = await dao.create(
            full_name="Bob D. Brown",
            nickname="Bobby",
            age=30,
            email="emailtest@test.com",
            phone="2233445566",
            password="password456",
            role=uuid.UUID("c6cb0394-d382-46d2-b932-f559c05bfa9c"),
            school=test_session.student_school,
            session=test_session
        )
        updated_data = {
            "full_name": "Bob Updated",
            "age": 31
        }
        updated_user = await dao.update_user_by_email("emailtest@test.com", updated_data, session=test_session)
        assert updated_user is not None
        assert updated_user.full_name == "Bob Updated"
        assert updated_user.age == 31

    async def test_delete_user_by_id(self, test_session):
        dao = UserDAO()
        user = await dao.create(
            full_name="Charlie E. Davis",
            nickname="Chuck",
            age=28,
            email="test@test.com",
            phone="3344556677",
            password="password789",
            role=uuid.UUID("c6cb0394-d382-46d2-b932-f559c05bfa9c"),
            school=test_session.student_school,
            session=test_session
        )
        user_id = user.id
        await dao.delete_user_by_id(user_id, session=test_session)
        deleted_user = await dao.get_user_by_id(user_id, session=test_session)
        assert deleted_user is None

    async def test_delete_user_by_email(self, test_session):
        dao = UserDAO()
        user = await dao.create(
            full_name="David F. Wilson",
            nickname="Dave",
            age=35,
            email="test@test.com",
            phone="4455667788",
            password="password101",
            role=uuid.UUID("c6cb0394-d382-46d2-b932-f559c05bfa9c"),
            school=test_session.student_school,
            session=test_session
        )
        await dao.delete_user_by_email("test@test.com", session=test_session)
        deleted_user = await dao.get_user_by_email("test@test.com", session=test_session)
        assert deleted_user is None

    async def test_check_user_permission_no_permission(self, test_session):
        dao = UserDAO()
        user = await dao.create(
            full_name="Eve G. Martinez",
            nickname="Ev",
            age=29,
            email="email@email.com",
            phone="5566778899",
            password="password202",
            role=uuid.UUID("c6cb0394-d382-46d2-b932-f559c05bfa9c"),
            school=test_session.student_school,
            session=test_session
        )
        has_permission = await dao.check_permission_by_id(user.id, "read_users", session=test_session)
        assert has_permission is False

    async def test_check_user_permission_with_permission(self, test_session):
        dao = UserDAO()
        user = await dao.create(
            full_name="Max K. Martinez",
            nickname="Maxy",
            age=31,
            email="max@email.com",
            phone="55646778899",
            password="password202",
            role=uuid.UUID("e39ee8be-9f09-4818-81fc-8ed56ff5ed75"),
            school=test_session.admin_school,
            session=test_session
        )
        has_permission = await dao.check_permission_by_id(user.id, "read_users", session=test_session)
        assert has_permission is True

    async def test_check_user_permission_by_email_admin_true(self, test_session):
        dao = UserDAO()
        # create admin user who should have read_users via role seeding in fixture
        await dao.create(
            full_name="Ada M. Admin",
            nickname="ADM",
            age=27,
            email="ada.admin@example.com",
            phone="100200300",
            password="s3cret",
            role=uuid.UUID("e39ee8be-9f09-4818-81fc-8ed56ff5ed75"),
            school=test_session.admin_school,
            session=test_session,
        )
        has_perm = await dao.check_permission_by_email(
            "ada.admin@example.com", "read_users", session=test_session
        )
        assert has_perm is True

    async def test_check_user_permission_by_email_student_false(self, test_session):
        dao = UserDAO()
        await dao.create(
            full_name="Stu D. Dent",
            nickname="Student",
            age=19,
            email="stu.dent@example.com",
            phone="400500600",
            password="passw0rd",
            role=uuid.UUID("c6cb0394-d382-46d2-b932-f559c05bfa9c"),
            school=test_session.student_school,
            session=test_session,
        )
        has_perm = await dao.check_permission_by_email(
            "stu.dent@example.com", "read_users", session=test_session
        )
        assert has_perm is False

    async def test_check_user_permission_unknown_permission(self, test_session):
        dao = UserDAO()
        user = await dao.create(
            full_name="Nora Q. Permless",
            nickname="N",
            age=23,
            email="nora@example.com",
            phone="777777777",
            password="pw",
            role=uuid.UUID("e39ee8be-9f09-4818-81fc-8ed56ff5ed75"),
            school=test_session.admin_school,
            session=test_session,
        )
        # Check a permission that doesn't exist in DB at all
        has_perm = await dao.check_permission_by_id(
            user.id, "totally_unknown_permission", session=test_session
        )
        assert has_perm is False

    async def test_get_role_id_resolves_teacher_and_admissions_committee(self, test_session):
        teacher_role = Role(id=uuid.uuid4(), role="teacher")
        admissions_role = Role(id=uuid.uuid4(), role="admissions_committee")
        test_session.add_all([teacher_role, admissions_role])
        await test_session.commit()

        dao = UserDAO()
        teacher_id = await dao.get_role_id(RoleEnum.TEACHER, session=test_session)
        admissions_id = await dao.get_role_id(RoleEnum.ADMISSIONS_COMMITTEE, session=test_session)

        assert teacher_id == teacher_role.id
        assert admissions_id == admissions_role.id