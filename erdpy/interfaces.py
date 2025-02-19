from typing import Any, Dict, List, Tuple


class IAddress:
    def hex(self) -> str:
        return ""

    def bech32(self) -> str:
        return ""

    def pubkey(self) -> bytes:
        return bytes()


class ITransaction:
    def serialize(self) -> bytes:
        return bytes()

    def serialize_as_inner(self) -> str:
        return ''

    def to_dictionary(self) -> Dict[str, Any]:
        return {}

    def to_dictionary_as_inner(self) -> Dict[str, Any]:
        return {}

    def set_version(self, version: int):
        return

    def set_options(self, options: int):
        return


class IAccount:
    def sign_transaction(self, transaction: ITransaction) -> str:
        return ""


class IElrondProxy:
    def get_account_nonce(self, address: IAddress) -> int:
        return 0

    def send_transaction(self, payload: Any) -> str:
        return ""

    def simulate_transaction(self, payload: Any) -> str:
        return ""

    def send_transactions(self, payload: List[Any]) -> Tuple[int, List[str]]:
        return 0, []

    def send_transaction_and_wait_for_result(self, payload: Any, num_seconds_timeout: int) -> Dict[str, Any]:
        return dict()

    def query_contract(self, payload: Any) -> Any:
        return dict()
