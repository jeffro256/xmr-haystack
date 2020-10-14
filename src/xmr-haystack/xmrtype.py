from collections import namedtuple
import json

class Block(namedtuple('Block', 'height hash')):
	@classmethod
	def fromjson(cls, obj):
		return cls(*obj)

	def __eq__(self, other):
		return self.hash == other.hash

	def __ne__(self, other):
		return self.hash != other.hash

class Transaction(namedtuple('Transaction', 'hash height timestamp ins outs')):
	"""
	Lightweight class to represent the important information about a monero transaction. Easily
	serialiable to and from JSON.

	Fields:
		hash - str, hash of transaction
		height - int, height of block that contains transaction
		timestamp - int, UNIX timestamp of block that contains transaction
		ins - list[int], flat list of all gindexes in all rings of stealth addresses in tx
		outs - list[str], list of all output stealth addresses (targets) in transaction
	"""

	@classmethod
	def fromjson(cls, json_data):
		return cls(*json_data)

	@classmethod
	def all_in_rpc_resp(cls, json_resp):
		"""
		Returns a list of Transaction objects respresenting all valid transactions that are
		contained in a RPC command /get_transactions JSON response. json_resp is just a JSON
		obj parsed from the text response from the RPC command. It is used in the method
		DaemonConnection.get_transactions().

		Doc: https://web.getmonero.org/resources/developer-guides/daemon-rpc.html#get_transactions
		"""

		return [cls._fromrpcobj(x) for x in json_resp['txs']]

	@classmethod
	def _fromrpcobj(cls, json_data):
		"""
		Returns a Transaction object from JSON object inside response of RPC /get_transactions
		command. json_data is a json obj representation of a tx found at resp["txs"][x], where
		resp is the json response from monerod and x is an index.

		Doc: https://web.getmonero.org/resources/developer-guides/daemon-rpc.html#get_transactions
		"""

		tx_hash = json_data['tx_hash']
		blk_height = json_data['block_height']
		timestamp = json_data['block_timestamp']

		tx_json = json.loads(json_data['as_json'])

		ins = []
		outs = []

		# I don't know why this structure is so damn convoluted
		for in_entry in tx_json['vin']:
			k = in_entry['key']
			gindex_offsets = k['key_offsets']
			gindexes = [sum(gindex_offsets[:i+1]) for i in range(len(gindex_offsets))]

			ins.extend(gindexes)

		for out_entry in tx_json['vout']:
			key = out_entry['target']['key']

			outs.append(key)

		return cls(tx_hash, blk_height, timestamp, ins, outs)

	def __eq__(self, other):
		""" Returns True if hashes are equal """
		return self.hash == other.hash

	def __ne__(self, other):
		""" Returns True if hashes are not equal """

		return self.hash != other.hash
