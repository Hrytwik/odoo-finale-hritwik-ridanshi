from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


class UnsafeTestDatabase(RuntimeError):
    pass


def assert_safe_test_database(test_url: str, dev_url: str) -> None:
    """Stop the run before anything is dropped unless the test database is clearly a throwaway one.

    The test setup runs DROP SCHEMA public CASCADE, which erases every table in its database,
    so a TEST_DATABASE_URL that points at real development data must be refused up front.
    Only the database name is ever put in an error message, never the password.
    """
    try:
        test = make_url(test_url)
    except ArgumentError:
        raise UnsafeTestDatabase("TEST_DATABASE_URL is not a valid database URL") from None

    name = test.database or ""
    if not name.endswith("_test"):
        raise UnsafeTestDatabase(
            f"Refusing to run: TEST_DATABASE_URL points at database '{name}'. The tests erase every table in "
            "their database, so its name must end with '_test' (for example 'everest_test'). "
            "Create a separate database for the tests and point TEST_DATABASE_URL at it."
        )

    try:
        dev_name = make_url(dev_url).database
    except ArgumentError:
        dev_name = None  # an unusable dev URL cannot collide with anything
    if dev_name == name:
        raise UnsafeTestDatabase(
            f"Refusing to run: TEST_DATABASE_URL and DATABASE_URL name the same database ('{name}'). "
            "The tests would erase your development data. Point them at two different databases."
        )
