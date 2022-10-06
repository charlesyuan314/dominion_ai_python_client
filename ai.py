from argparse import ArgumentParser
import json
from websocket import create_connection


ACTIONS = {'Cellar', 'Market', 'Merchant', 'Militia', 'Mine',
           'Moat', 'Remodel', 'Smithy', 'Village', 'Workshop'}

CARDS = ["Market", "Village", "Merchant", "Smithy", "Moat"]


def action_phase(strategy, state):
    while ACTIONS.intersection(state.hand) != set() and state.actions > 0:
        for card in CARDS:
            if card in state.hand:
                play_card(card, state)
                break


def buy_phase(strategy, state):
    for card in [card for card in state.hand if card in {"Copper", "Silver", "Gold"}]:
        play_card(card, state)
    for card in find_cards_to_buy(strategy, state):
        if state.supply[card] > 0:
            buy_card(card, state)


def find_cards_to_buy(strategy, state):
    if strategy == "curses":
        return ["Curse"]
    if state.treasure >= 8:
        return ["Province"]
    elif state.treasure >= 6:
        return ["Gold"]
    elif strategy == "fancy" and state.treasure >= 5 and "Market" in state.supply and state.deck_cards.count("Market") <= 2:
        return ["Market"]
    elif strategy in ("fancy", "smithy") and state.treasure >= 4 and "Smithy" in state.supply and state.deck_cards.count("Smithy") == 0:
        return ["Smithy"]
    elif strategy == "fancy" and state.treasure >= 3 and "Workshop" in state.supply and state.deck_cards.count("Merchant") == 0:
        return ["Merchant"]
    elif strategy == "fancy" and state.treasure >= 3 and "Workshop" in state.supply and state.deck_cards.count("Village") == 0:
        return ["Village"]
    elif state.treasure >= 3:
        return ["Silver"]
    elif strategy == "fancy" and state.treasure >= 2 and "Moat" in state.supply and state.deck_cards.count("Moat") == 0:
        return ["Moat"]
    return []


class State(object):
    def __init__(self) -> None:
        self.hand = []
        self.discard = 0
        self.deck = 0
        self.deck_cards = []
        self.supply = {}
        self.buys = 1
        self.actions = 1
        self.treasure = 0
        self.payload = None
        self.conn = None

    def __repr__(self) -> str:
        return "${} | {} actions | {} buys | {} discard | {} deck | hand: {}".format(
            self.treasure, self.actions, self.buys, self.discard, self.deck, self.hand)


def play_card(card, state):
    state.payload["method"] = "Play"
    state.payload["params"] = {"card": card, "data": {}}
    print("Playing", card)
    state.conn.send(json.dumps(state.payload))
    action_response(state)


def buy_card(card, state):
    state.payload["method"] = "Buy"
    state.payload["params"] = {"card": card}
    print("Buying", card)
    state.conn.send(json.dumps(state.payload))
    action_response(state)
    state.deck_cards.append(card)


def action_response(state):
    response = json.loads(state.conn.recv())
    if (error := response.get("error")) is not None:
        print("Fatal error:", error)
        exit(1)
    elif (result := response.get("result")) is not None:
        parse_response(state, result)
        print(state)


def parse_response(state, response):
    state.hand = response["hand"]
    state.discard = response["discard"]
    state.deck = response["deck"]
    state.supply = response["supply"]
    if "buys" in response:
        state.buys = response["buys"]
    if "actions" in response:
        state.actions = response["actions"]
    if "treasure" in response:
        state.treasure = response["treasure"]


def end_turn(state):
    state.payload["method"] = "EndTurn"
    if "params" in state.payload:
        state.payload.pop("params")
    state.conn.send(json.dumps(state.payload))


def run_server(conn, strategy):
    state = State()
    while True:
        payload = {
            "jsonrpc": "2.0",
            "id": 0,
        }
        response = json.loads(conn.recv())

        if (method := response.get("method")) is None:
            continue
        if method == "StartGame":
            payload_id = response["id"]
            payload["id"] = payload_id
            payload["result"] = {}
            conn.send(json.dumps(payload))
            print("Kingdom:", response["params"]["kingdom"])
        elif method == "FatalError":
            print("Fatal error:", response["message"])
            exit(1)
        elif method == "StartTurn":
            parse_response(state, response["params"])
            print(state)
            state.payload = payload
            state.conn = conn
            action_phase(strategy, state)
            buy_phase(strategy, state)
            end_turn(state)
        elif method == "GameOver":
            print(response["params"])
            break
    conn.close()


def main(args):
    parser = ArgumentParser()
    parser.add_argument("--http_endpoint", action="store",
                        help="Dominai Endpoint with or without default name.", type=str)
    parser.add_argument("--player", action="store",
                        help="Dominai player number", type=str)
    parser.add_argument("--strategy", action="store",
                        help="Strategy name", type=str)
    args = parser.parse_args(args)
    args_dict = vars(args)

    def parse_http_endpoint(endpoint):
        ws_endpoint = "ws" + endpoint.split("http")[1]
        return ws_endpoint.split("?name=")[0]

    def make_connection(parsed_endpoint, player_number):
        return create_connection(parsed_endpoint + "?name=player{}".format(player_number))

    endpoint = parse_http_endpoint(args_dict["http_endpoint"])
    connection = make_connection(endpoint, args_dict["player"])
    run_server(connection, args_dict["strategy"])


if __name__ == '__main__':
    import sys
    main(sys.argv[1:])
