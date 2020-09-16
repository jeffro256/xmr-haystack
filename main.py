#!/usr/bin/python3

import getpass
import random
from sys import stdin, stdout, stderr
from time import time

import handlearg
import xmrconn

#TODO: Perform lookup for every primary address in wallet
#TODO: add command-line options
#TODO: more graceful error handling
#TODO: update documentation for RPC funcs for addr and port

def main():
	arg_parser = handlearg.get_parser()
	args = arg_parser.parse_args()
	
	password = getpassword("Wallet password: ")

	try:
		settings = handlearg.validate_and_process(args, wallet_pass=password)
	except ValueError as ve:
		arg_parser.print_usage()
		print(ve)

		return 1
	
	daemon_login = ':'.join([settings['duser'], settings['dpass']]) if settings['login'] else None	
	daemon = xmrconn.DaemonConnection(settings['daddr'], settings['dport'], settings['duser'], settings['dpass'])
	wallet = xmrconn.WalletConnection(settings['walletf'], password, daemon.host(), daemon_login, cmd=settings['wallcmd'])
	
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
	tx_batch_count = 1 if settings['restricted'] else 100
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
				
# Program entry point
if __name__ == '__main__':
	exitcode = main()
	exit(0 if exitcode is None else exitcode)
