# Copyright 2017 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ------------------------------------------------------------------------------

import hashlib
import base64
import time
import random
import requests
import yaml
import cbor

from sawtooth_signing import create_context
from sawtooth_signing import CryptoFactory

from sawtooth_sdk.protobuf.transaction_pb2 import TransactionHeader
from sawtooth_sdk.protobuf.transaction_pb2 import Transaction
from sawtooth_sdk.protobuf.batch_pb2 import BatchList
from sawtooth_sdk.protobuf.batch_pb2 import BatchHeader
from sawtooth_sdk.protobuf.batch_pb2 import Batch


def _sha512(data):
    return hashlib.sha512(data).hexdigest()


context = create_context("secp256k1")


def get_new_signer(private_key=None):
    if private_key is None:
        private_key = context.new_random_private_key()
    return CryptoFactory(context).new_signer(private_key)


class IntkeyClient:
    def __init__(self, url):
        self.url = url
        self._signer = get_new_signer()

    def set(self, name, value, wait=None):
        return self._send_transaction("set", str(name), value, wait=wait)

    def inc(self, name, value, wait=None):
        return self._send_transaction("inc", str(name), value, wait=wait)

    def dec(self, name, value, wait=None):
        return self._send_transaction("dec", str(name), value, wait=wait)

    def list(self):
        result = self._send_request("state?address={}".format(self._get_prefix()))

        try:
            encoded_entries = yaml.safe_load(result)["data"]

            return [
                cbor.loads(base64.b64decode(entry["data"])) for entry in encoded_entries
            ]

        except BaseException:
            return None

    def show(self, name):
        address = self._get_address(name)

        result = self._send_request(
            "state/{}".format(address),
            name=name,
        )

        try:
            return cbor.loads(base64.b64decode(yaml.safe_load(result)["data"]))[name]

        except BaseException:
            return None

    def _get_status(self, batch_id, wait):
        result = self._send_request(
            "batch_statuses?id={}&wait={}".format(batch_id, wait),
        )
        return yaml.safe_load(result)["data"][0]["status"]

    def _get_prefix(self):
        return _sha512("intkey".encode("utf-8"))[0:6]

    def _get_address(self, name):
        prefix = self._get_prefix()
        game_address = _sha512(name.encode("utf-8"))[64:]
        return prefix + game_address

    def _send_request(self, suffix, data=None, content_type=None, name=None):
        if self.url.startswith("http://"):
            url = "{}/{}".format(self.url, suffix)
        else:
            url = "http://{}/{}".format(self.url, suffix)

        headers = {}

        if content_type is not None:
            headers["Content-Type"] = content_type

        if data is not None:
            result = requests.post(url, headers=headers, data=data)
        else:
            result = requests.get(url, headers=headers)

        return result.text

    def _send_transaction(self, verb, name, value, wait=None):
        payload = cbor.dumps(
            {
                "Verb": verb,
                "Name": name,
                "Value": value,
            }
        )

        # Construct the address
        address = self._get_address(name)

        header = TransactionHeader(
            signer_public_key=self._signer.get_public_key().as_hex(),
            family_name="intkey",
            family_version="1.0",
            inputs=[address],
            outputs=[address],
            dependencies=[],
            payload_sha512=_sha512(payload),
            batcher_public_key=self._signer.get_public_key().as_hex(),
            nonce=hex(random.randint(0, 2**64)),
        ).SerializeToString()

        signature = self._signer.sign(header)

        transaction = Transaction(
            header=header, payload=payload, header_signature=signature
        )

        batch_list = self._create_batch_list([transaction])
        batch_id = batch_list.batches[0].header_signature

        if wait and wait > 0:
            wait_time = 0
            start_time = time.time()
            response = self._send_request(
                "batches",
                batch_list.SerializeToString(),
                "application/octet-stream",
            )
            while wait_time < wait:
                status = self._get_status(
                    batch_id,
                    wait - int(wait_time),
                )
                wait_time = time.time() - start_time

                if status != "PENDING":
                    return response

            return response

        return self._send_request(
            "batches",
            batch_list.SerializeToString(),
            "application/octet-stream",
        )

    def _create_batch_list(self, transactions):
        transaction_signatures = [t.header_signature for t in transactions]

        header = BatchHeader(
            signer_public_key=self._signer.get_public_key().as_hex(),
            transaction_ids=transaction_signatures,
        ).SerializeToString()

        signature = self._signer.sign(header)

        batch = Batch(
            header=header, transactions=transactions, header_signature=signature
        )
        return BatchList(batches=[batch])
