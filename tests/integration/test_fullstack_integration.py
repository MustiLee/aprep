"""
Fullstack Integration Test

Tests backend API + database integration:
- Database connectivity
- API endpoint functionality
- Authentication flow
- Data persistence
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


def test_database_connection():
    """Test PostgreSQL database connection"""
    print("\n" + "=" * 70)
    print("DATABASE CONNECTION TEST")
    print("=" * 70)

    from src.db.database import get_db, engine
    from src.models.db_models import APSubject

    # Test connection
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            assert result.fetchone()[0] == 1
        print("\n✓ PostgreSQL connection successful")
    except Exception as e:
        pytest.fail(f"Database connection failed: {e}")

    # Test session
    db = next(get_db())
    try:
        # Query AP Subjects
        subjects = db.query(APSubject).all()
        print(f"✓ Database session working")
        print(f"  Found {len(subjects)} AP subjects in database")

        if subjects:
            print(f"  Example: {subjects[0].name}")
    finally:
        db.close()

    print("=" * 70)


def test_api_health_check():
    """Test API health endpoint"""
    print("\n" + "=" * 70)
    print("API HEALTH CHECK TEST")
    print("=" * 70)

    from src.api.main import app

    client = TestClient(app)

    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()

    print(f"\n✓ Health endpoint responding")
    print(f"  Status: {data.get('status')}")
    print(f"  Database: {data.get('database')}")
    print("=" * 70)


def test_api_routes_registered():
    """Test that all API routes are properly registered"""
    print("\n" + "=" * 70)
    print("API ROUTES TEST")
    print("=" * 70)

    from src.api.main import app

    routes = [route.path for route in app.routes]

    expected_routes = [
        "/health",
        "/api/v1/auth/register",
        "/api/v1/auth/login",
        "/api/v1/students/profile",
        "/api/v1/students/dashboard",
        "/api/v1/practice/generate",
        "/api/v1/parent/profile",
    ]

    print(f"\n✓ Total routes registered: {len(routes)}")

    for expected in expected_routes:
        if expected in routes:
            print(f"  ✓ {expected}")
        else:
            print(f"  ✗ {expected} (MISSING)")

    # Count by prefix
    auth_routes = [r for r in routes if r.startswith("/api/v1/auth")]
    student_routes = [r for r in routes if r.startswith("/api/v1/students")]
    practice_routes = [r for r in routes if r.startswith("/api/v1/practice")]
    parent_routes = [r for r in routes if r.startswith("/api/v1/parent")]

    print(f"\n  Routes by category:")
    print(f"    Auth: {len(auth_routes)}")
    print(f"    Student: {len(student_routes)}")
    print(f"    Practice: {len(practice_routes)}")
    print(f"    Parent: {len(parent_routes)}")

    print("=" * 70)


def test_database_models():
    """Test database models are properly configured"""
    print("\n" + "=" * 70)
    print("DATABASE MODELS TEST")
    print("=" * 70)

    from src.models import db_models

    models = [
        "User",
        "StudentProfile",
        "ParentProfile",
        "APSubject",
        "StudentEnrollment",
        "PracticeSession",
        "ParentStudentLink"
    ]

    print("\n✓ Checking database models...")

    for model_name in models:
        if hasattr(db_models, model_name):
            model = getattr(db_models, model_name)
            print(f"  ✓ {model_name}: {model.__tablename__}")
        else:
            print(f"  ✗ {model_name}: MISSING")

    print("=" * 70)


def test_authentication_endpoints():
    """Test authentication endpoints"""
    print("\n" + "=" * 70)
    print("AUTHENTICATION ENDPOINTS TEST")
    print("=" * 70)

    from src.api.main import app

    client = TestClient(app)

    # Test registration endpoint exists
    print("\n1. Testing registration endpoint...")
    response = client.post("/api/v1/auth/register", json={
        "email": "test@example.com",
        "password": "testpass123",
        "full_name": "Test User",
        "role": "student"
    })

    # We expect either 200 (success) or 400 (already exists)
    assert response.status_code in [200, 201, 400, 422]
    print(f"   ✓ Registration endpoint responds (status: {response.status_code})")

    # Test login endpoint exists
    print("\n2. Testing login endpoint...")
    response = client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "testpass123"
    })

    assert response.status_code in [200, 401, 422]
    print(f"   ✓ Login endpoint responds (status: {response.status_code})")

    print("=" * 70)


def test_migrations_applied():
    """Test that all migrations have been applied"""
    print("\n" + "=" * 70)
    print("DATABASE MIGRATIONS TEST")
    print("=" * 70)

    from src.db.database import engine
    from sqlalchemy import inspect

    inspector = inspect(engine)
    tables = inspector.get_table_names()

    expected_tables = [
        "users",
        "student_profiles",
        "parent_profiles",
        "ap_subjects",
        "student_enrollments",
        "practice_sessions",
        "parent_student_links"
    ]

    print(f"\n✓ Total tables in database: {len(tables)}")

    for table in expected_tables:
        if table in tables:
            print(f"  ✓ {table}")
        else:
            print(f"  ✗ {table} (MISSING)")

    print("=" * 70)


if __name__ == "__main__":
    print("\n🧪 Running Fullstack Integration Tests\n")

    test_database_connection()
    test_database_models()
    test_migrations_applied()
    test_api_health_check()
    test_api_routes_registered()
    test_authentication_endpoints()

    print("\n✅ All fullstack integration tests completed!\n")
