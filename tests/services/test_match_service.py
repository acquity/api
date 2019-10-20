from datetime import datetime
from unittest.mock import patch

from src.config import APP_CONFIG
from src.database import (
    BuyOrder,
    Match,
    Round,
    Security,
    SellOrder,
    User,
    session_scope,
)
from src.services import MatchService
from tests.fixtures import create_buy_order, create_round, create_sell_order

match_service = MatchService(
    config=APP_CONFIG, BuyOrder=BuyOrder, SellOrder=SellOrder, Match=Match
)


def test_run_matches():
    round = create_round()

    buy_order_id = create_buy_order("1", round_id=round["id"])["id"]
    create_buy_order("2", round_id=round["id"])
    sell_order_id = create_sell_order("3", round_id=round["id"])["id"]
    create_sell_order("4", round_id=round["id"])

    with patch(
        "src.services.match_buyers_and_sellers",
        return_value=[(buy_order_id, sell_order_id)],
    ), patch("src.services.RoundService.get_active", return_value=round):
        match_service.run_matches()

    with session_scope() as session:
        match = session.query(Match).one()
        assert match.buy_order_id == buy_order_id
        assert match.sell_order_id == sell_order_id

        assert session.query(Round).get(round["id"]).is_concluded