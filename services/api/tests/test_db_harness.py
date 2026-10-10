from sqlalchemy import text


def test_db_fixture_talks_to_test_database(db):
    name = db.execute(text("select current_database()")).scalar_one()
    assert name.endswith("_test")


def test_changes_are_rolled_back_between_tests_part1(db):
    db.execute(text("create table if not exists harness_probe (x int)"))
    db.execute(text("insert into harness_probe values (1)"))
    db.commit()  # endpoints call commit(); it must still not persist beyond this test
    assert db.execute(text("select count(*) from harness_probe")).scalar_one() == 1


def test_changes_are_rolled_back_between_tests_part2(db):
    exists = db.execute(text("select to_regclass('harness_probe')")).scalar_one()
    assert exists is None
