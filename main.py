#!/usr/bin/python3

import argparse
from datetime import datetime
import getpass
import json
import random
from sys import stdin, stdout, stderr
from time import time

import xmrconn

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
	
	daemon_login = f'{args.duser}:{args.dpwd}' if args.duser is not None else None
	wallet_file = getattr(args, 'wallet file')
	password = getpassword("Wallet password: ")

	daemon = xmrconn.DaemonConnection(args.addr, args.port, args.duser, args.dpwd)
	wallet = xmrconn.WalletConnection(wallet_file, password, daemon.host(), daemon_login, cmd=args.cli_exe)
	
	# Check that login etc is valid for wallet
	if not wallet.is_valid():
		print('error opening wallet.', file=stderr)
		return -1

	# Ask wallet for table of transfer information. The password is passed through stdin
	# Output from stdout is stored in variable res
	print("Getting keys from wallet...")
	trans_data = wallet.get_incoming_transfers()

	if not trans_data:
		print("No transfers to show.", file=stderr)
		return 0

	# Construct a dictionary where the keys are the global indexes of your one-time pubkeys
	# and the values are empty (for now) lists of txs that your pubkeys are used in.
	# Then contrust a dictionary where the keys are the global indexes of your one-time pubkeys
	# and the values are the pubkeys
	txs_by_key_index = {entry['global_index']: [] for entry in trans_data}
	pubkey_by_index = {entry['global_index']: entry['pubkey'] for entry in trans_data}

	# Find restore height and subtract small random amount to not diclose real
	# restore height to daemon. Also find current blockchain height
	print("Getting restore height from wallet...")
	restore_height = wallet.get_restore_height()

	if restore_height is None:
		print("bad output from wallet command", file=stderr)
		return -1

	height_offset = random.randint(20, 200)
	start_height = max(restore_height - height_offset, 0)
	end_height = max(daemon.get_info()['height'] - 10, start_height)

	# Loop through all transactions in all blocks in [start_height, end_height],
	# adding txs to txs_by_key_index if tx contains a public key that belongs to us
	tx_batch_count = 1 if args.restricted_rpc else 100
	tx_hashes = []
	last_time = time()
	tx_found = 0
	for height in range(start_height, end_height + 1):
		block = daemon.get_block(height)

		# For some reason, the node returns an object w/o a 'tx_hashes' key if there are none
		if 'tx_hashes' in block:
			tx_hashes += block['tx_hashes']

		# By batching the responses, I hope to speed up the scanning
		if (height % tx_batch_count == 0 or height == end_height) and tx_hashes:
			txs = daemon.get_transactions(tx_hashes)

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
		help='path to wallet file')#,
		#type=argparse.FileType('r'))
	parser.add_argument('-a', '--daemon-addr',
		help='daemon address (e.g. node.xmr.to)',
		default='127.0.0.1',
		dest='addr')
	parser.add_argument('-p', '--daemon-port',
		help='daemon port (e.g. 18081)',
		default=18081,
		type=int,
		dest='port')
	parser.add_argument('-l', '--daemon-login',
		help='monerod RPC login in the form of [username]:[password]',
		dest='login')
	parser.add_argument('-s', '--scan-height',
		help='rescan blockchain from specified height. defaults to wallet restore height',
		type=int,
		dest='height')
	parser.add_argument('-i', '--cache-input',
		help='path to input cache file',
		type=argparse.FileType('r+'),
		dest='cache_in')
	parser.add_argument('-o', '--cache-output',
		help='path to output cache file',
		type=argparse.FileType('w'),
		dest='cache_out')
	parser.add_argument('-n', '--no-cache',
		help='do not read from cache file and do not save to cache file',
		action='store_true')
	parser.add_argument('-c', '--wallet-cli-path',
		help='path to monero-wallet-cli executable. Helpful if executable is not in PATH',
		type=argparse.FileType('r'),
		dest='cli_exe_file')

	return parser

def check_args(ns):
	"""
	Checks the arguments in namespace for any conditions not handled by get_parser
	
	Raises a ValueError if there is a unfixable problem with the arguments. Attempts to fix
	problems where it can and inserts defaults where argparse fell short.
	
	ns: Namespace object returned by argparse.ArgumentParser.parse_args
	"""
	
	default_cache_path = 'xmrhaystack.json'
	
	# Check daemon login flag parseability
	if ns.login is not None:
		print("Warning: passing passwords as command-line arguments is unsafe!")
	
		login_comps = ns.login.split(':')
		
		if len(login_comps) != 2:
			raise ValueError('error: --daemon-login must be in form [username]:[password]')

		ns.duser, ns.dpwd = login_comps
	else:
		ns.duser, ns.dpwd = None, None
	
	# Check daemon address + port + login
	conn = xmrconn.DaemonConnection(ns.addr, ns.port, ns.duser, ns.dpwd)

	print("Checking daemon access...")
	try:
		info = conn.get_info()
	except:
		err_msg = 'error: daemon at {} not reachable'.format(conn.host())
		raise ValueError(err_msg)
	
	if 'status' not in info or info['status'] != 'OK':
		raise ValueError('error: daemon responded unexpectedly')
	
	# sync_info is a command only allowed in unrestricted RPC mode. If it isn't enabled, there's a
	# good chance that the daemon will reject large get_transactions requests. Warn the user of this 
	print("Checking restricted RPC command access...")

	try:
		sync_info = conn.sync_info()
	except:
		err_msg = 'error: daemon at {}:{} not reachable'.format(ns.addr, ns.port)
		raise ValueError(err_msg)
	
	# If in unrestricted mode then resp['result']['status'] == 'OK'
	ns.restricted_rpc = sync_info is None
	if ns.restricted_rpc:
		print("Warning: daemon is in restricted RPC mode. Some functionality may not be available")

	
	# Check monero-wallet-cli
	ns.cli_exe = ns.cli_exe_file.name if ns.cli_exe_file else 'monero-wallet-cli'
	if not xmrconn.WalletConnection.valid_executable(ns.cli_exe):
		err_msg_temp = 'error: command "{}" gave a bad response. Try specifying --wallet-cli-path'
		err_msg = err_msg_temp.format(ns.cli_exe)
		raise ValueError(err_msg)

	# Check cache file arguments
	if ns.no_cache:
		if ns.cache_in is not None or ns.cache_out is not None:
			raise ValueError('error: --cache-input and --cache-output can\'t be set if" \
				" --no-cache is set')
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

