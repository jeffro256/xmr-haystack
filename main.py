#!/usr/bin/python3

import argparse
from datetime import datetime
import getpass
import json
import random
import requests
import subprocess as sp
from sys import stdin, stdout, stderr
from time import time

#TODO: Perform lookup for every primary address in wallet
#TODO: add command-line options
#TODO: more graceful error handling
#TODO: update documentation for RPC funcs for addr and port

def main():
	arg_parser = get_parser()
	args = arg_parser.parse_args()
	
	try:
		check_args(args)
	except ValueError as ve:
		arg_parser.print_usage()
		print(ve)
		return 1
	
	daemon_addr = args.addr
	daemon_port = args.port
	wallet_cli_path = args.cli_exe
	wallet_file = getattr(args, 'wallet file')[0].name
	password = getpassword("Wallet password: ")

	print("Getting keys from wallet...")

	# Ask wallet for table of transfer information. The password is passed through stdin
	# Output from stdout is stored in variable res
	wallet_cmd_temp = '{} --wallet-file="{}" --daemon-host={}:{} incoming_transfers verbose'
	wallet_cmd = wallet_cmd_temp.format(wallet_cli_path, wallet_file, daemon_addr, daemon_port)
	wallet_proc = sp.Popen(wallet_cmd, shell=True, stdin=sp.PIPE, stdout=sp.PIPE)
	res, _ = wallet_proc.communicate(input=password.encode())

	# If shell command failed, exit w/ msg
	if wallet_proc.returncode != 0:
		print('error opening wallet.', file=stderr)
		return -1

	# Populate trans_data with all of the data from wallet command 'incoming_transfers verbose' 
	trans_data = []
	for line in res.decode().split('\n'):
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

	# If no data found from wallet command, exit w/ msg
	# @TODO: Handle empty wallet case
	if not trans_data:
		print("bad output from wallet command", file=stderr)
		return -1

	#txids = list(map(lambda x: x['tx_id'], trans_data))

	# Construct a dictionary where the keys are the global indexes of your one-time pubkeys
	# and the values are empty (for now) lists of txs that your pubkeys are used in.
	# Then contrust a dictionary where the keys are the global indexes of your one-time pubkeys
	# and the values are the pubkeys
	txs_by_key_index = {entry['global_index']: [] for entry in trans_data}
	pubkey_by_index = {entry['global_index']: entry['pubkey'] for entry in trans_data}

	print("Getting restore height from wallet...")

	# Query the "restore height" from the wallet to find height to begin scanning at
	# Output from stdout is stored in variable res
	wallet_cmd_temp = '{} --wallet-file="{}" --daemon-host={}:{} restore_height'
	wallet_cmd = wallet_cmd_temp.format(wallet_cli_path, wallet_file, daemon_addr, daemon_port)
	wallet_proc = sp.Popen(wallet_cmd, shell=True, stdin=sp.PIPE, stdout=sp.PIPE)
	res, _ = wallet_proc.communicate(input=password.encode())

	# If shell command failed, exit w/ msg
	if wallet_proc.returncode != 0:
		print('error opening wallet.', file=stderr)
		return -1

	# Find restore height and subtract small random amount to not diclose real
	# restore height to daemon. Also find current blockchain height
	restore_height = int(res.decode().strip().split('\n')[-1])
	height_offset = random.randint(20, 200)
	start_height = max(restore_height - height_offset, 0)
	end_height = max(get_info(addr=daemon_addr, port=daemon_port)['height'] - 10, start_height)

	# Loop through all transactions in all blocks in [start_height, end_height],
	# adding txs to txs_by_key_index if tx contains a public key that belongs to us
	tx_hashes = []
	last_time = time()
	tx_found = 0
	for height in range(start_height, end_height + 1):
		block = get_block(height, addr=daemon_addr, port=daemon_port)

		# For some reason, the node returns an object w/o a 'tx_hashes' key if there are none
		if 'tx_hashes' in block:
			tx_hashes += block['tx_hashes']

		# By batching the responses, I hope to speed up the scanning
		if (height % 100 == 0 or height == end_height) and tx_hashes:
			txs = get_transactions(tx_hashes)

			# If txs returns None, then that means that the get_transactions failed
			if txs is None:
				return 1

			# For each transaction in block
			for i, tx in enumerate(txs):
				# For each stealth address index in transaction
				for kindex in get_key_indexes(tx):
					# If index belongs to us
					if kindex in txs_by_key_index:
						txs_by_key_index[kindex].append(tx_hashes[i])
						tx_found += 1

						print("Found tx:", tx_hashes[i])

			tx_hashes.clear()

		# if it has been at least a second since last print, print ptogress
		new_time = time()
		if new_time >= last_time + 1 and stdout.isatty():
			prog_perc = (height - start_height) / (end_height - start_height) * 100
			prog_line_temp = "Scanning blockchain (height: {}/{}, progress: {:.2f}%, found: {})"
			prog_line = prog_line_temp.format(height, end_height, prog_perc, tx_found)
			print(prog_line, end='\r')
			last_time = new_time

	print("Done!\n")
	print(txs_by_key_index)

	pretty_print_results(txs_by_key_index, pubkey_by_index)

	# We made it this far, yay!
	return 0

#################################
##### RPC COMMAND FUNCTIONS #####
#################################

def get_info(addr='127.0.0.1', port=18081):
	"""Returns json response from get_info RPC command"""

	url = f'http://{addr}:{port}/get_info'
	info = requests.get(url).json()

	return info

def get_transactions(txids, addr='127.0.0.1', port=18081):
	"""
	Returns list of transaction objects represented by JSON from get_transactions RPC command

	txids: list of transaction ids/hashes
	"""

	# Should throw error if not iterable
	iter(txids)

	url = f'http://{addr}:{port}/get_transactions'
	post_data = {'txs_hashes': txids, 'decode_as_json': True}
	resp = requests.post(url, json=post_data)

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

def get_outs(key_indexes, addr='127.0.0.1', port=18081):
	"""
	Returns list of output info objects from get_outs RPC command

	key_indexes: list of one-time public key global indexes
	"""

	return get_outs_raw(key_indexes, addr=addr, port=port)['outs']

def get_outs_raw(key_indexes, addr='127.0.0.1', port=18081):
	"""
	Returns raw json response from get_outs RPC command, including responses status, etc

	key_indexes: list of one-time public key global indexes
	"""

	# Should throw error if not iterable
	iter(key_indexes)

	url = f'http://{addr}:{port}/get_outs'
	post_data = {'outputs': [{'index': x} for x in key_indexes] }
	outs = requests.post(url, json=post_data).json()

	return outs


def get_block(height, addr='127.0.0.1', port=18081):
	"""
	Returns json object representing block from get_block RPC command

	height: height of said block
	"""

	url = f'http://{addr}:{port}/json_rpc'
	post_data = {
		'jsonrpc': '2.0',
		'id': '0',
		'method': 'get_block',
		'params': {
			'height': height
		}
	}

	resp = requests.post(url, json=post_data).json()
	block = resp['result']

	return block

##################################
##### OTHER HELPER FUNCTIONS #####
##################################

def get_key_indexes(tx):
	"""
	Returns a list of all one-time public key global indexes used in a transaction.

	tx: a dict-like transaction object in form as returned by get_transactions RPC command
	"""

	kindexes = []

	for tx_input in tx['vin']:
		key_offsets = tx_input['key']['key_offsets']

		new_indexes = [sum(key_offsets[:i+1]) for i in range(len(key_offsets))]

		kindexes += new_indexes

	return kindexes

def getpassword(prompt='Password: '):
	""" Returns secure password, read from stdin w/o echoing """

	if stdin.isatty():
		return getpass.getpass(prompt)
	else:
		return stdin.readline().rstrip()

def node_needs_login(addr='127.0.0.1', port=18081):
	"""
	Returns a boolean value whether the node at addr:port needs authorization to use RPC commands.
	"""
	
	resp = requests.get(f'{addr}:{port}/get_info')
	
	return resp.status_code == 401

def pretty_print_results(txs_by_key_index, pubkey_by_index):
	"""
	Pretty prints the final results of the program

	txs_by_key_index: {int: [str]}, dict of global indexes referencing a list of transactions 
	"""
	for key_index in txs_by_key_index:
		pubkey = pubkey_by_index[key_index]

		print("Your stealth address:", pubkey)

		used_txids = txs_by_key_index[key_index]

		if used_txids:
			for txid in used_txids:
				print("    tx: ", txid)
		else:
			print("    * no transactions found *")

def get_parser():
	""" Returns an argparse.ArgumentParser object for this program """

	desc = 'America\'s favorite stealth address scanner\u2122'
	parser = argparse.ArgumentParser(description=desc)
	parser.add_argument('wallet file',
		nargs=1,
		help='path to wallet file',
		type=argparse.FileType('r'))
	parser.add_argument('-a', '--daemon-addr',
		nargs=1,
		help='daemon address (e.g. node.xmr.to)',
		default='127.0.0.1',
		type=str,
		dest='addr')
	parser.add_argument('-p', '--daemon-port',
		nargs=1,
		help='daemon port (e.g. 18081)',
		default=18081,
		type=int,
		dest='port')
	parser.add_argument('-s', '--scan-height',
		nargs=1,
		help='rescan blockchain from specified height. defaults to wallet restore height',
		type=int,
		dest='height')
	parser.add_argument('-i', '--cache-input',
		nargs=1,
		help='path to input cache file',
		type=argparse.FileType('r+'),
		dest='cache_in')
	parser.add_argument('-o', '--cache-output',
		nargs=1,
		help='path to output cache file',
		type=argparse.FileType('w'),
		dest='cache_out')
	parser.add_argument('-n', '--no-cache',
		help='do not read from cache file and do not save to cache file',
		action='store_true')
	parser.add_argument('-c', '--wallet-cli-path',
		nargs=1,
		help='path to monero-wallet-cli executable. Helpful if executable is not in PATH',
		type=argparse.FileType('r'),
		dest='cli_exe')

	return parser

def check_args(ns):
	"""
	Checks the arguments in namespace for any conditions not handled by get_parser
	
	Raises a ValueError if there is a unfixable problem with the arguments. Attempts to fix
	problems where it can and inserts defaults where argparse fell short
	
	ns: Namespace object returned by argparse.ArgumentParser.parse_args
	"""
	
	default_cache_path = 'scancache.json'
	
	# Check daemon address + port
	try:
		info = get_info(addr=ns.addr, port=ns.port)
	except:
		err_msg = 'error: daemon at {}:{} not reachable'.format(ns.addr, ns.port)
		raise ValueError(err_msg)
	
	if 'status' not in info or info['status'] != 'OK':
		raise ValueError('error: daemon responded unexpectedly')
	
	# sync_info is a command only allowed in unrestricted RPC mode. If it isn't enabled, there's a
	# good chance that the daemon will reject large get_transactions requests. Warn the user of this 
	sync_url = 'http://{}:{}/json_rpc'.format(ns.addr, ns.port)
	
	try:
		post_data = {'jsonrpc': '2.0', 'id': '0', 'method': 'sync_info'}
		resp = requests.post(sync_url, json=post_data).json()
	except:
		err_msg = 'error: daemon at {}:{} not reachable'.format(ns.addr, ns.port)
		raise ValueError(err_msg)
	
	# If in unrestricted mode then resp['result']['status'] == 'OK'
	if 'result' not in resp or 'status' not in resp['result'] or resp['result']['status'] != 'OK':
		print("Warning: daemon is in restricted RPC mode. Some functionality may not be available")
	
	# Check monero-wallet-cli
	ns.cli_exe = ns.cli_exe if ns.cli_exe is not None else 'monero-wallet-cli'	
	cmd = ns.cli_exe + ' --version'
	proc = sp.Popen(cmd, shell=True, stdout=sp.PIPE)
	res, _ = proc.communicate()

	# A monero-wallet-cli output typically looks something like:
	#     Monero 'Nitrogen Nebula' (v0.16.0.3-release)
	if proc.returncode != 0 or b'Monero' not in res:
		err_msg_temp = 'error: command "{}" gave a bad response. Try specifying --wallet-cli-path'
		err_msg = err_msg_temp.format(ns.cli_exe)
		raise ValueError(err_msg)
	
	# Check cache file arguments
	if ns.no_cache:
		if ns.cache_in is not None or ns.cache_out is not None:
			raise ValueError('--cache-input and --cache-output can\'t be set if --no-cache is set')
	else:
		if ns.cache_in is None:
			try:
				ns.cache_in = open(default_cache_path, 'r+')
			except:
				pass
		
		if ns.cache_out is None:
			if ns.cache_in is None:
				try:
					ns.cache_out = open(default_cache_path, 'w')
				except:
					pass
			else:
				ns.cache_out = ns.cache_in
				
# Program entry point
if __name__ == '__main__':
	exitcode = main()
	exit(0 if exitcode is None else exitcode)

