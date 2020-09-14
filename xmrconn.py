import requests

class DaemonConnection(object):
	def __init__(self, addr='127.0.0.1', port=18081, user=None, pwd=None, scheme='http'):
		if (user is None) ^ (pwd is None):
			raise ValueError('user and pwd must both either be set or not set')

		self.addr = addr
		self.port = port
		self.user = user
		self.pwd = pwd
		self.scheme = scheme

	def url(self, endpoint=''):
		if not endpoint.startswith('/'):
			endpoint = '/' + endpoint

		url_fmt = '{}://{}:{}{}'
		url = url_fmt.format(self.scheme, self.addr, self.port, endpoint)

		return url

	def auth(self):
		if self.user is not None:
			return requests.auth.HTTPDigestAuth(self.user, self.pwd)
		else:
			return None

	def get_info(self):
		"""Returns json response from get_info RPC command"""

		url = self.url('/get_info')

		if self.auth:
			info = requests.get(url, auth=self.auth()).json()

		return info

	def get_transactions(self, txids):
		"""
		Returns list of transaction objects represented by JSON from get_transactions RPC command

		txids: list of transaction ids/hashes
		"""

		# Should throw error if not iterable
		iter(txids)

		url = self.url('/get_transactions')
		post_data = {'txs_hashes': txids, 'decode_as_json': True}
		resp = requests.post(url, json=post_data, auth=self.auth())

		try:
			transactions = resp.json()
		except:
			print("Error! json decoding from monero daemon. Response shown below:", file=stderr)
			print(resp.text, file=stderr)
			print("Input to get_transactions shown below:", file=stderr)
			print(txids, file=stderr)
			return None

		try:
			trans_json = list(map(lambda x: json.loads(x['as_json']), transactions['txs']))
		except KeyError:
			print("Error! Node rejected your request because it is too large", file=stderr)
			return None

		if len(trans_json) != len(txids):
			print("Error! Response length not equal to request length", file=stderr)
			return None

		return trans_json

	def get_outs(key_indexes):
		"""
		Returns list of output info objects from get_outs RPC command

		key_indexes: list of one-time public key global indexes
		"""

		return self.get_outs_raw(key_indexes)['outs']

	def get_outs_raw(key_indexes):
		"""
		Returns raw json response from get_outs RPC command, including responses status, etc

		key_indexes: list of one-time public key global indexes
		"""

		# Should throw error if not iterable
		iter(key_indexes)

		url = self.url('/get_outs')
		post_data = {'outputs': [{'index': x} for x in key_indexes] }
		outs = requests.post(url, json=post_data, auth=self.auth()).json()

		return outs

	def get_block(height, addr='127.0.0.1', port=18081):
		"""
		Returns json object representing block from get_block RPC command

		height: height of said block
		"""

		url = self.url('/json_rpc')
		post_data = {
			'jsonrpc': '2.0',
			'id': '0',
			'method': 'get_block',
			'params': {
				'height': height
			}
		}

		resp = requests.post(url, json=post_data, auth=self.auth()).json()
		block = resp['result']

		return block
