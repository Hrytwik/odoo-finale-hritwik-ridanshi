import pytest

from tests.db_guard import UnsafeTestDatabase, assert_safe_test_database as guard

DEV = "postgresql+psycopg://localhost:5432/everest"


def test_accepts_a_separate_test_database():
    guard("postgresql+psycopg://localhost:5432/everest_test", DEV)


def test_accepts_a_test_database_next_to_the_dev_one_on_a_hosted_server():
    dev = "postgresql+psycopg://u:p@ep-quiet-123.ap-south-1.aws.neon.tech/everest?sslmode=require"
    test = "postgresql+psycopg://u:p@ep-quiet-123.ap-south-1.aws.neon.tech/everest_test?sslmode=require"
    guard(test, dev)


def test_accepts_a_test_database_on_a_different_server_than_dev():
    guard("postgresql+psycopg://localhost:5432/everest_test", "postgresql+psycopg://u:p@db.example.com/everest")


def test_refuses_the_development_database():
    with pytest.raises(UnsafeTestDatabase, match="must end with '_test'"):
        guard(DEV, DEV)


@pytest.mark.parametrize("name", ["everest", "test_everest", "everest_testing", "testdb", "postgres"])
def test_refuses_names_without_the_test_suffix(name):
    with pytest.raises(UnsafeTestDatabase):
        guard(f"postgresql+psycopg://localhost:5432/{name}", DEV)


def test_refuses_a_url_with_no_database_name():
    with pytest.raises(UnsafeTestDatabase):
        guard("postgresql+psycopg://localhost:5432", DEV)


def test_refuses_when_dev_and_test_point_at_the_same_database_even_if_it_is_named_test():
    same = "postgresql+psycopg://localhost:5432/everest_test"
    with pytest.raises(UnsafeTestDatabase, match="same database"):
        guard(same, same)


def test_refuses_the_same_hosted_database_reached_through_the_pooled_host():
    direct = "postgresql+psycopg://u:p@ep-quiet-123.ap-south-1.aws.neon.tech/everest_test?sslmode=require"
    pooled = "postgresql+psycopg://u:p@ep-quiet-123-pooler.ap-south-1.aws.neon.tech/everest_test?sslmode=require"
    with pytest.raises(UnsafeTestDatabase, match="same database"):
        guard(pooled, direct)


def test_refuses_an_unparseable_url():
    with pytest.raises(UnsafeTestDatabase, match="not a valid"):
        guard("not a url at all", DEV)


def test_the_password_never_appears_in_an_error():
    secret = "s3cr3t%40pass"
    for bad in (f"postgresql+psycopg://u:{secret}@host/everest", f"postgresql+psycopg://u:{secret}@host/everest_test"):
        with pytest.raises(UnsafeTestDatabase) as err:
            guard(bad, bad)
        assert "s3cr3t" not in str(err.value)
