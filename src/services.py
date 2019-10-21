from datetime import datetime

from operator import itemgetter
import requests
from passlib.hash import argon2
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.sql import func
from src.database import (
    BannedPair,
    BuyOrder,
    Match,
    Round,
    Security,
    SellOrder,
    User,
    Chat,
    ChatRoom,
    session_scope,
)
from sqlalchemy import desc, asc
from sqlalchemy import or_, and_
from src.exceptions import (
    InvalidRequestException,
    NoActiveRoundException,
    ResourceNotOwnedException,
    UnauthorizedException,
)
from src.match import match_buyers_and_sellers
from src.schemata import (
    CREATE_ORDER_SCHEMA,
    CREATE_USER_SCHEMA,
    DELETE_ORDER_SCHEMA,
    EDIT_ORDER_SCHEMA,
    EMAIL_RULE,
    INVITE_SCHEMA,
    LINKEDIN_BUYER_PRIVILEGES_SCHEMA,
    LINKEDIN_CODE_SCHEMA,
    LINKEDIN_TOKEN_SCHEMA,
    USER_AUTH_SCHEMA,
    UUID_RULE,
    validate_input,
)


class DefaultService:
    def __init__(self, config):
        self.config = config


class UserService(DefaultService):
    def __init__(self, config, User=User, hasher=argon2):
        super().__init__(config)
        self.User = User
        self.hasher = hasher

    @validate_input(CREATE_USER_SCHEMA)
    def create(self, email, password, full_name):
        with session_scope() as session:
            hashed_password = self.hasher.hash(password)
            user = self.User(
                email=email,
                full_name=full_name,
                hashed_password=hashed_password,
                can_buy=False,
                can_sell=False,
            )
            session.add(user)
            session.commit()

            result = user.asdict()
        result.pop("hashed_password")
        return result

    @validate_input({"user_id": UUID_RULE})
    def activate_buy_privileges(self, user_id):
        with session_scope() as session:
            user = session.query(self.User).get(user_id)
            user.can_buy = True
            session.commit()
            result = user.asdict()
        result.pop("hashed_password")
        return result

    @validate_input(INVITE_SCHEMA)
    def invite_to_be_seller(self, inviter_id, invited_id):
        with session_scope() as session:
            inviter = session.query(self.User).get(inviter_id)
            if not inviter.can_sell:
                raise UnauthorizedException("Inviter is not a previous seller.")

            invited = session.query(self.User).get(invited_id)
            invited.can_sell = True

            session.commit()

            result = invited.asdict()
        result.pop("hashed_password")
        return result

    @validate_input(USER_AUTH_SCHEMA)
    def authenticate(self, email, password):
        with session_scope() as session:
            user = session.query(self.User).filter_by(email=email).one()
            if self.hasher.verify(password, user.hashed_password):
                return user.asdict()
            else:
                return None

    @validate_input({"id": UUID_RULE})
    def get_user(self, id):
        with session_scope() as session:
            user = session.query(self.User).get(id)
            if user is None:
                raise NoResultFound
            user_dict = user.asdict()
        user_dict.pop("hashed_password")
        return user_dict

    @validate_input({"email": EMAIL_RULE})
    def get_user_by_email(self, email):
        with session_scope() as session:
            user = session.query(self.User).filter_by(email=email).one().asdict()
        user.pop("hashed_password")
        return user


class LinkedinService(DefaultService):
    def __init__(self, config):
        super().__init__(config)

    @validate_input(LINKEDIN_BUYER_PRIVILEGES_SCHEMA)
    def activate_buyer_privileges(self, code, redirect_uri, user_email):
        linkedin_email = self._get_user_data(code=code, redirect_uri=redirect_uri)
        if linkedin_email == user_email:
            user = UserService(self.config).get_user_by_email(email=user_email)
            return UserService(self.config).activate_buy_privileges(
                user_id=user.get("id")
            )
        else:
            raise InvalidRequestException("Linkedin email does not match")

    @validate_input(LINKEDIN_CODE_SCHEMA)
    def _get_user_data(self, code, redirect_uri):
        token = self._get_token(code=code, redirect_uri=redirect_uri)
        return self._get_user_email(token=token)

    @validate_input(LINKEDIN_CODE_SCHEMA)
    def _get_token(self, code, redirect_uri):
        token = requests.post(
            "https://www.linkedin.com/oauth/v2/accessToken",
            headers={"Content-Type": "x-www-form-urlencoded"},
            params={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": self.config["CLIENT_ID"],
                "client_secret": self.config["CLIENT_SECRET"],
            },
        ).json()
        return token.get("access_token")

    @validate_input(LINKEDIN_TOKEN_SCHEMA)
    def _get_user_email(self, token):
        email = requests.get(
            "https://api.linkedin.com/v2/emailAddress?q=members&projection=(elements*(handle~))",
            headers={"Authorization": f"Bearer {token}"},
        ).json()
        return email.get("elements")[0].get("handle~").get("emailAddress")


class SellOrderService(DefaultService):
    def __init__(self, config, SellOrder=SellOrder, User=User, Round=Round):
        super().__init__(config)
        self.SellOrder = SellOrder
        self.User = User
        self.Round = Round

    @validate_input(CREATE_ORDER_SCHEMA)
    def create_order(self, user_id, number_of_shares, price, security_id):
        with session_scope() as session:
            user = session.query(self.User).get(user_id)
            if not user.can_sell:
                raise UnauthorizedException("This user cannot sell securities.")

            sell_order = self.SellOrder(
                user_id=user_id,
                number_of_shares=number_of_shares,
                price=price,
                security_id=security_id,
            )

            active_round = RoundService(self.config).get_active()
            if active_round is None:
                session.add(sell_order)
                session.commit()
                if RoundService(self.config).should_round_start():
                    RoundService(self.config).set_orders_to_new_round()
            else:
                sell_order.round_id = active_round["id"]
                session.add(sell_order)

            session.commit()
            return sell_order.asdict()

    @validate_input({"user_id": UUID_RULE})
    def get_orders_by_user(self, user_id):
        with session_scope() as session:
            sell_orders = session.query(self.SellOrder).filter_by(user_id=user_id).all()
            return [sell_order.asdict() for sell_order in sell_orders]

    @validate_input({"id": UUID_RULE, "user_id": UUID_RULE})
    def get_order_by_id(self, id, user_id):
        with session_scope() as session:
            order = session.query(self.SellOrder).get(id)
            if order.user_id != user_id:
                raise ResourceNotOwnedException("")
            return order.asdict()

    @validate_input(EDIT_ORDER_SCHEMA)
    def edit_order(self, id, subject_id, new_number_of_shares=None, new_price=None):
        with session_scope() as session:
            sell_order = session.query(self.SellOrder).get(id)
            if sell_order.user_id != subject_id:
                raise UnauthorizedException("You need to own this order.")

            if new_number_of_shares is not None:
                sell_order.number_of_shares = new_number_of_shares
            if new_price is not None:
                sell_order.price = new_price

            session.commit()
            return sell_order.asdict()

    @validate_input(DELETE_ORDER_SCHEMA)
    def delete_order(self, id, subject_id):
        with session_scope() as session:
            sell_order = session.query(self.SellOrder).get(id)
            if sell_order.user_id != subject_id:
                raise UnauthorizedException("You need to own this order.")

            session.delete(sell_order)
        return {}


class BuyOrderService(DefaultService):
    def __init__(self, config, BuyOrder=BuyOrder, User=User):
        super().__init__(config)
        self.BuyOrder = BuyOrder
        self.User = User

    @validate_input(CREATE_ORDER_SCHEMA)
    def create_order(self, user_id, number_of_shares, price, security_id):
        with session_scope() as session:
            user = session.query(self.User).get(user_id)
            if not user.can_buy:
                raise UnauthorizedException("This user cannot buy securities.")

            active_round = RoundService(self.config).get_active()

            buy_order = self.BuyOrder(
                user_id=user_id,
                number_of_shares=number_of_shares,
                price=price,
                security_id=security_id,
                round_id=(active_round and active_round["id"]),
            )

            session.add(buy_order)
            session.commit()
            return buy_order.asdict()

    @validate_input({"user_id": UUID_RULE})
    def get_orders_by_user(self, user_id):
        with session_scope() as session:
            buy_orders = session.query(self.BuyOrder).filter_by(user_id=user_id).all()
            return [buy_order.asdict() for buy_order in buy_orders]

    @validate_input({"id": UUID_RULE, "user_id": UUID_RULE})
    def get_order_by_id(self, id, user_id):
        with session_scope() as session:
            order = session.query(self.BuyOrder).get(id)
            if order.user_id != user_id:
                raise ResourceNotOwnedException("")
            return order.asdict()

    @validate_input(EDIT_ORDER_SCHEMA)
    def edit_order(self, id, subject_id, new_number_of_shares=None, new_price=None):
        with session_scope() as session:
            buy_order = session.query(self.BuyOrder).get(id)
            if buy_order.user_id != subject_id:
                raise UnauthorizedException("You need to own this order.")

            if new_number_of_shares is not None:
                buy_order.number_of_shares = new_number_of_shares
            if new_price is not None:
                buy_order.price = new_price

            session.commit()
            return buy_order.asdict()

    @validate_input(DELETE_ORDER_SCHEMA)
    def delete_order(self, id, subject_id):
        with session_scope() as session:
            buy_order = session.query(self.BuyOrder).get(id)
            if buy_order.user_id != subject_id:
                raise UnauthorizedException("You need to own this order.")

            session.delete(buy_order)
        return {}


class SecurityService(DefaultService):
    def __init__(self, config, Security=Security):
        super().__init__(config)
        self.Security = Security

    def get_all(self):
        with session_scope() as session:
            return [sec.asdict() for sec in session.query(self.Security).all()]


class RoundService(DefaultService):
    def __init__(self, config, Round=Round, SellOrder=SellOrder, BuyOrder=BuyOrder):
        super().__init__(config)
        self.Round = Round
        self.SellOrder = SellOrder
        self.BuyOrder = BuyOrder

    def get_all(self):
        with session_scope() as session:
            return [r.asdict() for r in session.query(self.Round).all()]

    def get_active(self):
        with session_scope() as session:
            active_round = (
                session.query(self.Round)
                .filter(
                    self.Round.end_time >= datetime.now(),
                    self.Round.is_concluded == False,
                )
                .one_or_none()
            )
            return active_round and active_round.asdict()

    def should_round_start(self):
        with session_scope() as session:
            unique_sellers = (
                session.query(self.SellOrder.user_id)
                .filter_by(round_id=None)
                .distinct()
                .count()
            )
            if (
                unique_sellers
                >= self.config["ACQUITY_ROUND_START_NUMBER_OF_SELLERS_CUTOFF"]
            ):
                return True

            total_shares = (
                session.query(func.sum(self.SellOrder.number_of_shares))
                .filter_by(round_id=None)
                .scalar()
                or 0
            )
            return (
                total_shares
                >= self.config["ACQUITY_ROUND_START_TOTAL_SELL_SHARES_CUTOFF"]
            )

    def set_orders_to_new_round(self):
        with session_scope() as session:
            new_round = self.Round(
                end_time=datetime.now() + self.config["ACQUITY_ROUND_LENGTH"],
                is_concluded=False,
            )
            session.add(new_round)
            session.flush()

            for sell_order in session.query(self.SellOrder).filter_by(round_id=None):
                sell_order.round_id = str(new_round.id)
            for buy_order in session.query(self.BuyOrder).filter_by(round_id=None):
                buy_order.round_id = str(new_round.id)


class MatchService(DefaultService):
    def __init__(
        self,
        config,
        BuyOrder=BuyOrder,
        SellOrder=SellOrder,
        Match=Match,
        BannedPair=BannedPair,
    ):
        super().__init__(config)
        self.BuyOrder = BuyOrder
        self.SellOrder = SellOrder
        self.Match = Match
        self.BannedPair = BannedPair

    def run_matches(self):
        round_id = RoundService(self.config).get_active()["id"]

        with session_scope() as session:
            buy_orders = [
                b.asdict()
                for b in session.query(self.BuyOrder).filter_by(round_id=round_id).all()
            ]
            sell_orders = [
                s.asdict()
                for s in session.query(self.SellOrder)
                .filter_by(round_id=round_id)
                .all()
            ]
            banned_pairs = [
                (bp.buyer_id, bp.seller_id)
                for bp in session.query(self.BannedPair).all()
            ]

        match_results = match_buyers_and_sellers(buy_orders, sell_orders, banned_pairs)

        with session_scope() as session:
            for buy_order_id, sell_order_id in match_results:
                match = self.Match(
                    buy_order_id=buy_order_id, sell_order_id=sell_order_id
                )
                session.add(match)

            session.query(Round).get(round_id).is_concluded = True


class BannedPairService(DefaultService):
    def __init__(self, config, BannedPair=BannedPair):
        super().__init__(config)
        self.BannedPair = BannedPair

    @validate_input({"my_user_id": UUID_RULE, "other_user_id": UUID_RULE})
    def ban_user(self, my_user_id, other_user_id):
        # Currently this bans the user two-way: both as buyer and as seller
        with session_scope() as session:
            session.add_all(
                [
                    self.BannedPair(buyer_id=my_user_id, seller_id=other_user_id),
                    self.BannedPair(buyer_id=other_user_id, seller_id=my_user_id),
                ]
            )

class ChatService(DefaultService):
    def __init__(self, config, UserService=UserService, Chat=Chat, ChatRoom=ChatRoom):
        self.Chat = Chat
        self.UserService = UserService
        self.ChatRoom = ChatRoom
        self.config = config

    def get_last_message(self, chat_room_id):
        with session_scope() as session:
            last_message = session.query(self.Chat)\
                .filter_by(chat_room_id=chat_room_id)\
                .order_by(desc("created_at"))\
                .first()
            if last_message == None:
                return {}
            return last_message.asdict()

    def add_message(self, chat_room_id, message, img, author_id):
        with session_scope() as session:
            chat = Chat(
                    chat_room_id=str(chat_room_id),
                    message=message,
                    img=img,
                    author_id=str(author_id),
                )
            session.add(chat)
            session.flush()
            session.refresh(chat)
            chat = chat.asdict()

            chat_room = session.query(self.ChatRoom).filter_by(id=chat_room_id).one().asdict()

            dealer_id = chat_room.get("seller_id") \
                if chat_room.get("buyer_id") == author_id \
                else chat_room.get("buyer_id")
            dealer = self.UserService().get_user(id=dealer_id)

            chat["dealer_name"] = dealer.get("full_name")
            chat["dealer_id"] = dealer.get("full_name")
            chat["created_at"] = datetime.timestamp(chat.get("created_at"))
            chat["updated_at"] = datetime.timestamp(chat.get("updated_at"))
            chat["author_name"] = self.UserService(self.config).get_user(id=chat.get("author_id")).get("full_name")
            return chat
    
    def get_conversation(self, user_id, chat_room_id):
        with session_scope() as session:
            return [
                {
                    **chat.asdict(),
                    "created_at": datetime.timestamp(chat.asdict().get("created_at")),
                    "updated_at": datetime.timestamp(chat.asdict().get("updated_at")),
                    "author_name": self.UserService(self.config).get_user(id=chat.asdict().get("author_id")).get("full_name")
                } for chat in session.query(self.Chat)\
                    .filter_by(chat_room_id=chat_room_id)
                    .order_by(asc("created_at"))
            ]


class ChatRoomService(DefaultService):
    def __init__(self, config, UserService=UserService, ChatRoom=ChatRoom, ChatService=ChatService):
        self.UserService=UserService
        self.ChatRoom = ChatRoom
        self.ChatService = ChatService
        self.config = config

    def get_chat_rooms(self, user_id):
        rooms = []
        data = []
        with session_scope() as session:
            data = session.query(self.ChatRoom)\
            .filter(or_(self.ChatRoom.buyer_id==user_id, self.ChatRoom.seller_id==user_id))\
            .all()
            
            for chat_room in data:
                chat_room = chat_room.asdict()
                chat = self.ChatService(self.config).get_last_message(chat_room_id=chat_room.get("id"))

                author_id = chat.get("author_id", None)
                author = {} if author_id == None else self.UserService(self.config).get_user(id=author_id)

                dealer_id = chat_room.get("seller_id") \
                    if chat_room.get("buyer_id") == user_id \
                    else chat_room.get("buyer_id")
                dealer = self.UserService(self.config).get_user(id=dealer_id)
                rooms.append({
                    "author_name": author.get("full_name"),
                    "author_id": author_id,
                    "dealer_name": dealer.get("full_name"),
                    "dealer_id": dealer_id,
                    "message": chat.get("message", "Start Conversation!"),
                    "created_at": datetime.timestamp(chat.get("created_at", datetime.now())),
                    "updated_at": datetime.timestamp(chat.get("updated_at", datetime.now())),
                    "chat_room_id": chat_room.get("id")
                })
        return sorted(rooms, key=itemgetter('created_at')) 