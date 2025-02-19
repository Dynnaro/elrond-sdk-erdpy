import base64
import logging
from typing import Any, List, Optional

from Cryptodome.Hash import keccak

from erdpy import config, constants, errors
from erdpy.accounts import Account, Address
from erdpy.interfaces import IElrondProxy
from erdpy.transactions import Transaction
from erdpy.utils import Object

logger = logging.getLogger("contracts")

HEX_PREFIX = "0X"


class QueryResult(Object):
    def __init__(self, as_base64: str, as_hex: str, as_number: int):
        self.base64 = as_base64
        self.hex = as_hex
        self.number = as_number


class SmartContract:
    def __init__(self, address: Optional[Address] = None, bytecode=None, metadata=None):
        self.address = Address(address)
        self.bytecode = bytecode
        self.metadata = metadata or CodeMetadata()

    def deploy(self, owner: Account, arguments: List[Any], gas_price: int, gas_limit: int, value: int, chain: str, version: int) -> Transaction:
        self.owner = owner
        self.compute_address()

        arguments = arguments or []
        gas_price = int(gas_price)
        gas_limit = int(gas_limit)
        value = value or 0

        tx = Transaction()
        tx.nonce = owner.nonce
        tx.value = str(value)
        tx.sender = owner.address.bech32()
        tx.receiver = Address.zero().bech32()
        tx.gasPrice = gas_price
        tx.gasLimit = gas_limit
        tx.data = self.prepare_deploy_transaction_data(arguments)
        tx.chainID = chain
        tx.version = version

        tx.sign(owner)
        return tx

    def prepare_deploy_transaction_data(self, arguments: List[Any]):
        tx_data = f"{self.bytecode}@{constants.VM_TYPE_WASM_VM}@{self.metadata.to_hex()}"

        for arg in arguments:
            tx_data += f"@{_prepare_argument(arg)}"

        return tx_data

    def compute_address(self):
        """
        8 bytes of zero + 2 bytes for VM type + 20 bytes of hash(owner) + 2 bytes of shard(owner)
        """
        owner_bytes = self.owner.address.pubkey()
        nonce_bytes = self.owner.nonce.to_bytes(8, byteorder="little")
        bytes_to_hash = owner_bytes + nonce_bytes
        address = keccak.new(digest_bits=256).update(bytes_to_hash).digest()
        address = bytes([0] * 8) + bytes([5, 0]) + address[10:30] + owner_bytes[30:]
        self.address = Address(address)

    def execute(self, caller: Account, function: str, arguments: List[str], gas_price: int, gas_limit: int, value: int, chain: str, version: int) -> Transaction:
        self.caller = caller

        arguments = arguments or []
        gas_price = int(gas_price)
        gas_limit = int(gas_limit)
        value = value or 0

        tx = Transaction()
        tx.nonce = caller.nonce
        tx.value = str(value)
        tx.sender = caller.address.bech32()
        tx.receiver = self.address.bech32()
        tx.gasPrice = gas_price
        tx.gasLimit = gas_limit
        tx.data = self.prepare_execute_transaction_data(function, arguments)
        tx.chainID = chain
        tx.version = version

        tx.sign(caller)
        return tx

    def prepare_execute_transaction_data(self, function: str, arguments: List[Any]):
        tx_data = function

        for arg in arguments:
            tx_data += f"@{_prepare_argument(arg)}"

        return tx_data

    def upgrade(self, owner: Account, arguments: List[Any], gas_price: int, gas_limit: int, value: int, chain: str, version: int) -> Transaction:
        self.owner = owner

        arguments = arguments or []
        gas_price = int(gas_price or config.DEFAULT_GAS_PRICE)
        gas_limit = int(gas_limit)
        value = value or 0

        tx = Transaction()
        tx.nonce = owner.nonce
        tx.value = str(value)
        tx.sender = owner.address.bech32()
        tx.receiver = self.address.bech32()
        tx.gasPrice = gas_price
        tx.gasLimit = gas_limit
        tx.data = self.prepare_upgrade_transaction_data(arguments)
        tx.chainID = chain
        tx.version = version

        tx.sign(owner)
        return tx

    def prepare_upgrade_transaction_data(self, arguments: List[Any]):
        tx_data = f"upgradeContract@{self.bytecode}@{self.metadata.to_hex()}"

        for arg in arguments:
            tx_data += f"@{_prepare_argument(arg)}"

        return tx_data

    def query(
        self,
        proxy: IElrondProxy,
        function: str,
        arguments: List[Any],
        value: int = 0,
        caller: Optional[Address] = None
    ) -> List[Any]:
        response_data = self.query_detailed(proxy, function, arguments, value, caller)
        return_data = response_data.get("returnData", []) or response_data.get("ReturnData", [])
        return [self._interpret_return_data(data) for data in return_data]

    def query_detailed(self, proxy: IElrondProxy, function: str, arguments: List[Any], value: int = 0, caller: Optional[Address] = None) -> Any:
        arguments = arguments or []
        prepared_arguments = [_prepare_argument(argument) for argument in arguments]

        payload = {
            "scAddress": self.address.bech32(),
            "funcName": function,
            "args": prepared_arguments,
            "value": str(value)
        }

        if caller:
            payload["caller"] = caller.bech32()

        response = proxy.query_contract(payload)
        response_data = response.get("data", {})
        return response_data

    def _interpret_return_data(self, data: str) -> Any:
        if not data:
            return data

        try:
            as_bytes = base64.b64decode(data)
            as_hex = as_bytes.hex()
            as_number = int(as_hex, 16)

            result = QueryResult(data, as_hex, as_number)
            return result
        except Exception:
            logger.warn(f"Cannot interpret return data: {data}")
            return None


def _prepare_argument(argument: Any):
    as_string = str(argument).upper()

    if as_string.startswith(HEX_PREFIX):
        return _prepare_hexadecimal(as_string)

    return _prepare_decimal(as_string)


def _prepare_hexadecimal(argument: str) -> str:
    argument = argument[len(HEX_PREFIX):]
    argument = ensure_even_length(argument)
    try:
        _ = int(argument, 16)
    except ValueError:
        raise errors.UnknownArgumentFormat(argument)
    return argument


def _prepare_decimal(argument: str) -> str:
    if not argument.isnumeric():
        raise errors.UnknownArgumentFormat(argument)

    as_number = int(argument)
    as_hexstring = hex(as_number)[len(HEX_PREFIX):]
    as_hexstring = ensure_even_length(as_hexstring)
    return as_hexstring


def ensure_even_length(string: str) -> str:
    if len(string) % 2 == 1:
        return '0' + string
    return string


class CodeMetadata:
    def __init__(self, upgradeable: bool = True, payable: bool = False):
        self.upgradeable = upgradeable
        self.payable = payable

    def to_hex(self):
        return ("01" if self.upgradeable else "00") + ("02" if self.payable else "00")
