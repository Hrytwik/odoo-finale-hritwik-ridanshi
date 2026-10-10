"""B7: the buyer portal shows the real delivery date. The portal itself is Ridanshi's; everything else about it (the
timeline, the trucks, the 404 rules, progress) is tested in tests/test_contract_portal.py."""
import datetime as dt

import pytest
from app.core.auth import COOKIE_NAME, create_token
from app.modules.llm import data as assistant_data
from app.modules.llm.data import ToolContext
from tests.factories import make_user
from tests.insights_world import build_mill

DAY = dt.timedelta(days=1)


@pytest.fixture
def mill(db):
    return build_mill(db)


def as_buyer(client, db, mill):
    user = make_user(db, role="buyer", buyer_id=mill.buyer.id)
    client.cookies.set(COOKIE_NAME, create_token(user.id))
    return user


def test_the_portal_shows_the_real_delivery_date(client, db, mill):
    as_buyer(client, db, mill)
    rows = {o["code"]: o for o in client.get("/api/portal/orders").json()}
    assert rows[mill.order_a.code]["delivery_date"] == str(mill.today + 4 * DAY)
    assert rows[mill.order_a.code]["deadline"] == str(mill.today + 3 * DAY)               # promised the 3rd day, expected the 4th
    assert rows[mill.order_b.code]["delivery_date"] == str(mill.today + 6 * DAY)
    assert client.get(f"/api/portal/orders/{mill.order_a.code}").json()["delivery_date"] == str(mill.today + 4 * DAY)


def test_the_buyer_and_the_staff_see_the_same_date(client, login_as, db, mill):
    as_buyer(client, db, mill)
    portal = {o["code"]: o["delivery_date"] for o in client.get("/api/portal/orders").json()}
    login_as("owner")
    staff = {o["code"]: o["delivery_date"] for o in client.get("/api/orders").json()}
    assert portal and portal == {code: staff[code] for code in portal}


def test_a_cancelled_order_is_listed_but_has_no_delivery_date(client, db, mill):
    mill.order_b.state = "cancelled"
    db.flush()
    as_buyer(client, db, mill)
    rows = {o["code"]: o for o in client.get("/api/portal/orders").json()}
    assert rows[mill.order_b.code]["delivery_date"] is None
    assert rows[mill.order_a.code]["delivery_date"] == str(mill.today + 4 * DAY)


def test_the_assistants_buyer_tools_get_the_date(db, mill):
    user = make_user(db, role="buyer", buyer_id=mill.buyer.id)
    ctx = ToolContext(db, user)
    assert {o["code"]: o["delivery_date"] for o in assistant_data.my_orders(ctx)}[mill.order_a.code] == str(mill.today + 4 * DAY)
    assert assistant_data.my_order(ctx, mill.order_a.code)["delivery_date"] == str(mill.today + 4 * DAY)
