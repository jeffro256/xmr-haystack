import json
import requests
import subprocess as sp
import sys

from .xmrtype import Transaction

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

	def host(self):
		return f'{self.addr}:{self.port}'

	def auth(self):
		if self.user is not None:
			return requests.auth.HTTPDigestAuth(self.user, self.pwd)
		else:
			return None

	def get_info(self):
		"""Returns json response from get_info RPC command"""

		url = self.url('/get_info')

		info = requests.get(url, auth=self.auth()).json()

		return info

	def sync_info(self):
		""" Returns json response from sync_info RPC command"""

		url = self.url('/json_rpc')
		post_data = {'jsonrpc': '2.0', 'id': '0', 'method': 'sync_info'}

		resp = requests.post(url, json=post_data, auth=self.auth())

		if resp.status_code // 100 != 2:
			return None

		try:
			json_resp = resp.json()

			if 'error' in json_resp or 'result' not in json_resp:
				return None

			return json_resp['result']
		except:
			return None

	def get_transactions(self, txids):
		"""
		Returns list of Transaction objs from get_transactions RPC command

		txids: list of transaction ids/hashes
		"""

		# Should throw error if not iterable
		iter(txids)

		url = self.url('/get_transactions')
		post_data = {'txs_hashes': txids, 'decode_as_json': True, 'prune': True}
		resp = requests.post(url, json=post_data, auth=self.auth())

		try:
			resp_json = resp.json()
		except:
			print("Error! json decoding from monero daemon. Response shown below:", file=sys.stderr)
			print(resp.text, file=sys.stderr)
			print("Input to get_transactions shown below:", file=sys.stderr)
			print(txids, file=sys.stderr)
			return None

		try:
			txs_res = Transaction.all_in_rpc_resp(resp_json)
		except KeyError:
			print("Error! Node rejected your request because it is too large", file=sys.stderr)
			return None

		if len(txs_res) != len(txids):
			print("Error! Response length not equal to request length", file=sys.stderr)
			return None

		return txs_res

	def get_outs(self, key_indexes):
		"""
		Returns list of output info objects from get_outs RPC command

		key_indexes: list of one-time public key global indexes
		"""

		# Should throw error if not iterable
		iter(key_indexes)

		url = self.url('/get_outs')
		post_data = {'outputs': [{'index': x} for x in key_indexes] }
		outs = requests.post(url, json=post_data, auth=self.auth()).json()

		return outs['outs']

	def get_block(self, height):
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

	def needs_login(self):
		"""
		Returns a boolean value whether the daemon needs authorization to use RPC commands.
		"""

		resp = requests.get(self.url('/get_info'))

		return resp.status_code == 401

class WalletConnection(object):
	def __init__(self, wallet_path, password, host=None, host_login=None, cmd='monero-wallet-cli'):
		self.wallet_path = wallet_path
		self.password = password
		self.host = host
		self.host_login = host_login
		self.cmd = cmd

	def send_command(self, cmd_strs):
		"""
		Runs wallet command with subprocess.Popen and returns a tuple of (stdout, stderr, errcode)

		cmd_strs: list of strings to pass as command-line-args to monero-wallet-cli
		stdin: str to pipe to process (after password is piped)
		"""

		daemon_args = []

		if self.host:
			daemon_args.extend(['--daemon-host', self.host])

			if self.host_login:
				daemon_args.extend(['--daemon-login', self.host_login])

		shell_args = [self.cmd, '--wallet-file', self.wallet_path] + daemon_args + cmd_strs
		proc = sp.Popen(shell_args, stdin=sp.PIPE, stdout=sp.PIPE)
		stdout, stderr = proc.communicate(input=self.password.encode())

		return (stdout, stderr, proc.returncode)

	def is_valid(self):
		stdout, stderr, errcode = self.send_command(['balance'])

		return errcode == 0

	def get_incoming_transfers(self):
		stdout, stderr, errcode = self.send_command(['incoming_transfers', 'verbose'])

		if errcode != 0:
			return None

		# Populate trans_data with all of the data from wallet command 'incoming_transfers verbose'
		trans_data = []
		for line in stdout.decode().split('\n'):
			try:
				trans_entry = {}
				line_comps = line.strip().split()

				trans_entry['amount'] = int(float(line_comps[0]) * 10 ** 12)
				trans_entry['spent'] = line_comps[1] == 'T'
				trans_entry['unlocked'] = line_comps[2] == 'unlocked'
				trans_entry['ringct'] = line_comps[3] == 'RingCT'
				trans_entry['global_index'] = int(line_comps[4])
				trans_entry['tx_id'] = line_comps[5][1:-1]
				trans_entry['addr_index'] = int(line_comps[6])
				trans_entry['pubkey'] = line_comps[7][1:-1]
				trans_entry['key_image'] = line_comps[8]

				trans_data.append(trans_entry)
			except:
				pass

		return trans_data

	def get_restore_height(self):
		stdout, stderr, errcode = self.send_command(['restore_height'])

		try:
			return int(stdout.decode().strip().split('\n')[-1])
		except:
			return None

	@classmethod
	def valid_executable(cls, cmd_name='monero-wallet-cli'):
		shell_args = [cmd_name, '--version']
		proc = sp.Popen(shell_args, stdout=sp.PIPE)
		stdout, _ = proc.communicate()

		# A monero-wallet-cli output typically looks something like:
		#     Monero 'Nitrogen Nebula' (v0.16.0.3-release)

		return proc.returncode == 0 and b'Monero' in stdout

