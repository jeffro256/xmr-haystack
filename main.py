#!/usr/bin/python3

import getpass
import random
from sys import stdin, stdout, stderr
from time import time

import handlearg
import xmrconn

#TODO: Perform lookup for every primary address in wallet

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

	daemon_login = ':'.join([settings['duser'], settings['dpass']]) if settings['dlogin'] else None
	daemon = xmrconn.DaemonConnection(settings['daddr'], settings['dport'], settings['duser'], settings['dpass'])
	wallet = xmrconn.WalletConnection(settings['walletf'], password, daemon.host(), daemon_login, cmd=settings['wallcmd'])

	# Ask wallet for table of transfer information. The password is passed through stdin. Output from stdout
	# is stored in variable res. Construct a dictionary 'pubkey_by_index' where the keys are the global indexes
	# of your own one-time pubkeys and the values are the pubkeys
	print("Getting keys from wallet...")
	trans_data = wallet.get_incoming_transfers()

	if not trans_data:
		print("No transfers to show.", file=stderr)
		return 0

	pubkey_by_index = {entry['global_index']: entry['pubkey'] for entry in trans_data}

	# If available, use the cache to query already built txs_by_key_index and last scan height. Use this information
	# to get height to start scan. If cache not available, default to empty txs_by_key_index and restore height minus
	# some for the start height. We subtract a small amount from the starting height in case of a reorg and to defend
	# against a malicious node attempting to guess our identity from the restore height. Finally calculate the height
	# to end our scan on. It will possibly be updated later during our scan.
	if settings['caching'] and settings['cachein'] is not None:
		print("Getting scan information from cache...")
		txs_by_key_index, last_height = get_cached_info(settings['cachein'], pubkey_by_index, password)
		height_offset = random.randint(25, 250)
		start_height = max(last_height - height_offset, 0)
	else:
		print("Getting restore height from wallet...")
		restore_height = wallet.get_restore_height()

		if restore_height is None:
			print("bad output from wallet command", file=stderr)
			return -1

		height_offset = random.randint(25, 250)
		start_height = max(restore_height - height_offset, 0)
		txs_by_key_index = {i: [] for i in pubkey_by_index]

	end_height = max(daemon.get_info()['height'] - 1, start_height)

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

def add_to_cache(blob_cache, txs_by_key_index, pubkey_by_index, height, password):
	cache_keys_by_index = {i: BlobCache.gen_key(pubkey_by_index[i] + password) for i in pubkey_by_index}

	for ind in cache_keys_by_index:
		cache_key = cache_keys_by_index[ind]

		cache_obj = {
			'height': height,
			'index': ind,
			'pubkey': pubkey_by_index[ind],
			'txs': txs_by_key_index[ind]
		}

		blob_cache.clear_objs(cache_key)
		blob_cache.add_obj(cache_obj, cache_key)

def get_cached_info(blob_cache, pubkey_by_index, password):
	cache_keys = [BlobCache.gen_key(pkey + password) for pkey in pubkey_by_index.values()]

	objs = []
	for cache_key in cache_keys:
		objs.extend(blob_cache.get_objs(cache_key))

	min_height = None
	txs_by_index = {i: [] for i in pubkey_by_index}

	for obj in objs:
		height = obj['height']
		index = obj['index']
		txs = obj['txs']

		if min_height is None or height < min_height:
			min_height = height

		txs_by_index[index] = txs

	return txs_by_index, min_height

# Program entry point
if __name__ == '__main__':
	exitcode = main()
	exit(0 if exitcode is None else exitcode)
