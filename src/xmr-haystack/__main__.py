from bidict import bidict
from datetime import datetime
import getpass
import random
from sys import stdin, stdout, stderr
from time import time

from .blobcache import BlobCache
from . import handlearg
from . import xmrconn

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

	pubkey_by_index = bidict({entry['global_index']: entry['pubkey'] for entry in trans_data})

	# If available, use the cache to query already built txs_by_key_index and last scan height. Use this information
	# to get height to start scan. If cache not available, default to empty txs_by_key_index and restore height minus
	# some for the start height. We subtract a small amount from the starting height in case of a reorg and to defend
	# against a malicious node attempting to guess our identity from the restore height. Finally calculate the height
	# to end our scan on. It will possibly be updated later during our scan.
	txs_by_key_index = {i: [] for i in pubkey_by_index}
	should_scan_height = True

	if settings['caching'] and settings['cachein'] is not None:
		print("Getting scan information from cache...")
		cached_txs, last_height = get_cached_info(settings['cachein'], pubkey_by_index, password)

		txs_by_key_index.update(cached_txs)

		if last_height is not None:
			height_offset = random.randint(25, 250)
			start_height = max(last_height - height_offset, 0)
			should_scan_height = False

	if should_scan_height:
		print("Getting restore height from wallet...")
		restore_height = wallet.get_restore_height()

		if restore_height is None:
			print("bad output from wallet command", file=stderr)
			return -1

		height_offset = random.randint(25, 250)
		start_height = max(restore_height - height_offset, 0)

	end_height = max(daemon.get_info()['height'] - 1, start_height)

	# Loop through all transactions in all blocks in [start_height, end_height],
	# adding txs to txs_by_key_index if tx contains a public key that belongs to us
	tx_batch_count = 100 if settings['restricted'] else 10000
	tx_hashes = []
	last_time = time()
	tx_found = 0
	prog_fmt = "Scanning blockchain (height: {h}/{e}, progress: {p:.2f}%, found: {f})"

	try:
		for height in range(start_height, end_height + 1):
			block = daemon.get_block(height)

			# For some reason, the node returns an object w/o a 'tx_hashes' key if there are none
			if 'tx_hashes' in block:
				tx_hashes += block['tx_hashes']

			# By batching the responses, I hope to speed up the scanning
			while (len(tx_hashes) >= tx_batch_count or height == end_height) and tx_hashes:
				txs = daemon.get_transactions(tx_hashes[:tx_batch_count])

				# If txs returns None, then that means that the get_transactions failed
				if txs is None:
					return 1

				# For each transaction in block
				for tx in txs:
					# For each input and output stealth address index in transaction
					out_gindexes = [pubkey_by_index.inverse[p] for p in tx.outs if p in pubkey_by_index.values()]
					for kindex in (tx.ins + out_gindexes):
						# If index belongs to us and hasn't been added before
						if kindex in txs_by_key_index and tx not in txs_by_key_index[kindex]:
							txs_by_key_index[kindex].append(tx)
							tx_found += 1

							print("Found tx:", tx.hash)

				tx_hashes = tx_hashes[tx_batch_count:]

				# Poll print progress
				force = height == end_height
				prog = (height - start_height) / (end_height - start_height) * 100
				last_time = poll_progress_print(prog_fmt, last_time, force, h=height, e=end_height,
					p=prog, f=tx_found)
		print('\nDone!')
	except KeyboardInterrupt:
		print("\nCaught keyboard interrupt. Exiting...")

	pretty_print_results(txs_by_key_index, pubkey_by_index, trans_data)

	if settings['caching'] and settings['cacheout'] is not None:
		print("Writing to cache...")
		cache = settings['cachein'] if settings['cachein'] is not None else BlobCache()
		add_to_cache(cache, txs_by_key_index, pubkey_by_index, height, password)
		cache.save(settings['cacheout'])
		settings['cacheout'].close()

	# We made it this far, yay!
	print("Goodbye!")
	return 0

##################################
##### OTHER HELPER FUNCTIONS #####
##################################

def getpassword(prompt='Password: '):
	""" Returns secure password, read from stdin w/o echoing """

	if stdin.isatty():
		return getpass.getpass(prompt)
	else:
		return stdin.readline().rstrip()

def pretty_print_results(txs_by_key_index, pubkey_by_index, transfer_data):
	"""
	Pretty prints the final results of the program

	txs_by_key_index: {int: [str]}, dict of global indexes referencing a list of transactions
	pubkey_by_index: {int: str}, dict of global indexes referencing their corresponding pubkeys
	transfer_data: [dict], result of call to WalletConnection.incoming_transfers()
	"""

	for key_index in txs_by_key_index:
		pubkey = pubkey_by_index[key_index]

		print("Your stealth address:", pubkey)

		txs = txs_by_key_index[key_index]

		if txs:
			for tx in txs:
				print("    [%s]: " % datetime.fromtimestamp(tx.timestamp), end="")

				# Get the transfer which matches the tx_id in transfer_data or None if not found
				matching_transfer = ([None] + [e for e in transfer_data if e['tx_id'] == tx.hash])[-1]

				# If this is originating transaction of current pubkey
				if matching_transfer and matching_transfer['pubkey'] == pubkey:
					print("Pubkey was created. ", end="")
				# If you are sender/recipient of transaction but its not originator of current pubkey
				elif matching_transfer:
					print("Pubkey was spent. ", end="")
				# Otherwise its not yours and thus a decoy
				else:
					print("Used as a decoy. ", end="")

				print("Transaction(hash=%s, height=%d, ins=%d, outs=%d)" % (tx.hash, tx.height, len(tx.ins), len(tx.outs)))
		else:
			print("    * no transactions found *")

def poll_progress_print(fmt_str, last_time, delay=1, force=False, **fmtargs):
	new_time = time()

	if (new_time >= last_time + delay or force) and stdout.isatty():
		prog_str = fmt_str.format(**fmtargs) + '    '
		print(prog_str, end='\r')

		return new_time
	else:
		return last_time

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
