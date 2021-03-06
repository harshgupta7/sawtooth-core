# Copyright 2016 Intel Corporation
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

import json
from http.client import RemoteDisconnected
import requests
# pylint: disable=no-name-in-module,import-error
# needed for the google.protobuf imports to pass pylint
from google.protobuf.message import Message as BaseMessage

from sawtooth_cli.exceptions import CliException


class RestClient(object):
    def __init__(self, base_url=None):
        self._base_url = base_url or 'http://localhost:8080'

    def list_blocks(self):
        return self._get('/blocks')['data']

    def get_block(self, block_id):
        return self._get('/blocks/' + block_id)['data']

    def list_batches(self):
        return self._get('/batches')['data']

    def get_batch(self, batch_id):
        return self._get('/batches/' + batch_id)['data']

    def list_transactions(self):
        return self._get('/transactions')['data']

    def get_transaction(self, transaction_id):
        return self._get('/transactions/' + transaction_id)['data']

    def list_state(self, subtree=None, head=None):
        return self._get('/state', address=subtree, head=head)

    def get_leaf(self, address, head=None):
        return self._get('/state/' + address, head=head)

    def get_statuses(self, batch_ids, wait=None):
        """Fetches the committed status for a list of batch ids.

        Args:
            batch_ids (list of str): The ids to get the status of.
            wait (optional, int): Indicates that the api should wait to
                respond until the batches are committed or the specified
                time in seconds has elapsed.

        Returns:
            dict: A statuses map, with ids as keys, and statuses values
        """
        return self._post('/batch_status', batch_ids, wait=wait)['data']

    def send_batches(self, batch_list):
        """Sends a list of batches to the validator.

        Args:
            batch_list (:obj:`BatchList`): the list of batches

        Returns:
            dict: the json result data, as a dict
        """
        if isinstance(batch_list, BaseMessage):
            batch_list = batch_list.SerializeToString()

        return self._post('/batches', batch_list)

    def _get(self, path, **queries):
        code, json_result = self._submit_request(
            self._base_url + path,
            params=self._format_queries(queries),
        )

        # concat any additional pages of data
        while code == 200 and 'next' in json_result.get('paging', {}):
            previous_data = json_result.get('data', [])
            code, json_result = self._submit_request(
                json_result['paging']['next'])
            json_result['data'] = previous_data + json_result.get('data', [])

        if code == 200:
            return json_result
        elif code == 404:
            return None
        else:
            raise CliException("({}): {}".format(code, json_result))

    def _post(self, path, data, **queries):
        if isinstance(data, bytes):
            headers = {'Content-Type': 'application/octet-stream'}
        else:
            data = json.dumps(data).encode()
            headers = {'Content-Type': 'application/json'}
        headers['Content-Length'] = '%d' % len(data)

        code, json_result = self._submit_request(
            self._base_url + path,
            params=self._format_queries(queries),
            data=data,
            headers=headers,
            method='POST')

        if code == 200 or code == 201 or code == 202:
            return json_result
        else:
            raise CliException("({}): {}".format(code, json_result))

    def _submit_request(self, url, params=None, data=None, headers=None,
                        method="GET"):
        """Submits the given request, and handles the errors appropriately.

        Args:
            url (str): the request to send.
            params (dict): params to be passed along to get/post
            data (bytes): the data to include in the request.
            headers (dict): the headers to include in the request.
            method (str): the method to use for the request, "POST" or "GET".

        Returns:
            tuple of (int, str): The response status code and the json parsed
                body, or the error message.

        Raises:
            `CliException`: If any issues occur with the URL.
        """
        try:
            if method == 'POST':
                result = requests.post(
                    url, params=params, data=data, headers=headers)
            elif method == 'GET':
                result = requests.get(
                    url, params=params, data=data, headers=headers)
            result.raise_for_status()
            return (result.status_code, result.json())
        except requests.exceptions.HTTPError as e:
            return (e.response.status_code, e.response.reason)
        except RemoteDisconnected as e:
            raise CliException(e)
        except requests.exceptions.ConnectionError as e:
            raise CliException(
                ('Unable to connect to "{}": '
                 'make sure URL is correct').format(self._base_url))

    @staticmethod
    def _format_queries(queries):
        queries = {k: v for k, v in queries.items() if v is not None}
        return queries if queries else ''
