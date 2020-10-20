from bidict import bidict
from datetime import datetime
import getpass
import random
from sys import stdin, stdout, stderr
from time import time

from .blobcache import BlobCache
from . import handlearg
from . import xmrconn
from .xmrtype import Block, Transaction

def main():
	# Good morning, time to handle arguments
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
	if not settings['quiet']: print("Getting keys from wallet...")
	trans_data = wallet.get_incoming_transfers()

	if not trans_data:
		print("No transfers to show.", file=stderr)
		return 0

	pubkey_by_index = bidict({entry['global_index']: entry['pubkey'] for entry in trans_data})

	# If available, use the cache to query already built txs_by_key_index and scanned_blocks.
	txs_by_key_index = {i: [] for i in pubkey_by_index}
	scanned_blocks = []

	should_read_cache = settings['cachein'] is not None
	if should_read_cache:
		if not settings['quiet']: print("Getting scan information from cache...")
		cached_txs, scanned_blocks = get_cached_info(settings['cachein'], password)

		txs_by_key_index.update(cached_txs)

	# Calculate the start height. If specified on the command line, use that height. If not, try to use
	# scanned_blocks from cache to find newest valid block and start from a little before there. If that
	# doesn't work, then ask the wallet for its restore height and start from a little before there. If
	# all else fails, resort to scanning from beginning of the blockchain. After all that, calculate the
	# height to end the scan.
	if settings['height'] is not None:
		start_height = settings['height']
		scanned_blocks = []
	else:
		need_restore_height = True

		if scanned_blocks:
			newest_valid = newest_block(scanned_blocks, daemon)
			if newest_valid:
				scanned_blocks = [newest_valid]
				height_offset = random.randint(25, 250)
				start_height = max(newest_valid.height - height_offset, 0)
				need_restore_height = False
			else:
				scanned_blocks = []

		if need_restore_height:
			if not settings['quiet']: print("Getting restore height from wallet...")
			restore_height = wallet.get_restore_height()

			if restore_height is None:
				print("Warning: couldn't get restore height from wallet!! Scanning whole blockchain...")
				start_height = 0
			else:
				height_offset = random.randint(25, 250)
				start_height = max(restore_height - height_offset, 0)

	end_height = max(daemon.get_info()['height'] - 1, start_height)

	# Now it's time to scan!
	try:
		scan(start_height, end_height, daemon, settings, pubkey_by_index, txs_by_key_index, scanned_blocks)

		if not settings['quiet']: print('\nDone!')
	except KeyboardInterrupt:
		print("\nCaught keyboard interrupt. Exiting...")

	pretty_print_results(txs_by_key_index, pubkey_by_index, trans_data, extra_quiet=settings['vquiet'])

	# Write txs_by_index and scanned_blocks to output cache
	if settings['cacheout'] is not None:
		cache = settings['cachein'] if settings['cachein'] is not None else BlobCache()
		add_to_cache(cache, txs_by_key_index, scanned_blocks, password)

		try:
			cache_out_file = settings['cacheout']
			cache_out_file.seek(0)
			cache_out_file.truncate()
			cache.save(cache_out_file)
			cache_out_file.close()
		except Exception as e:
			print(e)
			print("Error: writing to cache failed.")
			return 1

	# We made it this far, yay!
	return 0

##################################
##### OTHER HELPER FUNCTIONS #####
##################################

def scan(start_height, end_height, daemon, settings, pubkey_by_gindex, txs_by_key_index, scanned_blocks):
	# Loop through all transactions in all blocks in [start_height, end_height],
	# adding txs to txs_by_key_index if tx contains a public key that belongs to us
	tx_batch_count = 100 if settings['restricted'] else 10000
	tx_hashes = []
	last_time = time()
	tx_found = 0
	prog_fmt = "Scanning blockchain (height: {h}/{e}, progress: {p:.2f}%, found: {f})"
	max_scanned_blocks = 50

	height = start_height
	while height <= end_height:
		block = daemon.get_block(height)
		block_header = block['block_header']

		# If the new block doesn't point to the last block's hash and not a 'decoy scan'. (i.e. when
		# start_height <= height <= scanned_blocks[0].height
		decoy_scan = scanned_blocks and height <= scanned_blocks[0].height
		mismatched_hash = len(scanned_blocks) != 0 and block_header['prev_hash'] != scanned_blocks[-1].hash
		if mismatched_hash and not decoy_scan:
			print("\nReorg detected. Rolling back...")
			scanned_blocks.pop()
			height -= 1

			if not scanned_blocks:
				print("Warning! Rolled back all available scanned blocks. Something might be wrong.")

			continue

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
				out_gindexes = [pubkey_by_gindex.inverse[p] for p in tx.outs if p in pubkey_by_gindex.values()]
				for kindex in (tx.ins + out_gindexes):
					# If index belongs to us
					if kindex in txs_by_key_index:
						# If new tx
						if tx not in txs_by_key_index[kindex]:
							txs_by_key_index[kindex].append(tx)
							if not settings['quiet']: print("Found tx:", tx.hash)
						# If tx already found, replace with newest version. Useful in case of reorg since
						# last scan
						else:
							txs_by_key_index = [(x if x != tx else tx) for x in txs_by_key_index[kindex]]

						tx_found += 1

			tx_hashes = tx_hashes[tx_batch_count:]

			# Poll print progress
			if not settings['vquiet']:
				force = height == end_height
				prog = (height - start_height) / (end_height - start_height) * 100
				last_time = poll_progress_print(prog_fmt, last_time, force=force, h=height, e=end_height,
					p=prog, f=tx_found)

		scanned_blocks.append(Block(block_header['height'], block_header['hash']))
		scanned_blocks[:] = scanned_blocks[-max_scanned_blocks:]
		height += 1

def getpassword(prompt='Password: '):
	""" Returns secure password, read from stdin w/o echoing """

	if stdin.isatty():
		return getpass.getpass(prompt)
	else:
		return stdin.readline().rstrip()

def pretty_print_results(txs_by_key_index, pubkey_by_index, transfer_data, extra_quiet=False):
	"""
	Pretty prints the final results of the program

	txs_by_key_index: {int: [str]}, dict of global indexes referencing a list of transactions
	pubkey_by_index: {int: str}, dict of global indexes referencing their corresponding pubkeys
	transfer_data: [dict], result of call to WalletConnection.incoming_transfers()
	"""

	print()

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

				if not extra_quiet:
					tx_fmt = "Transaction(hash=%s, height=%d, ins=%d, outs=%d)"
					print(tx_fmt % (tx.hash, tx.height, len(tx.ins), len(tx.outs)), end="")

				print()
		else:
			print("    * no transactions found *")

def poll_progress_print(fmt_str, last_time, delay=1, force=False, **fmtargs):
	new_time = time()

	if (new_time >= (last_time + delay) or force) and stdout.isatty():
		prog_str = fmt_str.format(**fmtargs) + '    '
		print(prog_str, end='\r')

		return new_time
	else:
		return last_time

def add_to_cache(blob_cache, txs_by_key_index, scanned_blocks, password):
	"""
	password ->
		txs_by_gindex
		recent block hashes/heights
		minimum height of blocks in block_hashes
	"""

	cache_data = {
		'txs': txs_by_key_index,
		'scanned_blocks': scanned_blocks
	}

	blob_cache.clear_objs(password)
	blob_cache.add_obj(cache_data, password)

def get_cached_info(blob_cache, password):
	cached_objs = blob_cache.get_objs(password)

	if not cached_objs:
		return {}, []

	cached_obj = cached_objs[0]
	txs = {int(i): list(map(Transaction.fromjson, txs)) for i, txs in cached_obj['txs'].items()}
	scanned_blocks = list(map(Block.fromjson, cached_obj['scanned_blocks']))

	return txs, scanned_blocks

def newest_block(blocks, daemon):
	"""
	Quieres the daemon for a list of blocks and returns the newest valid block in the list, or None if not available
	"""

	sorted_blocks = sorted(blocks, key=lambda x: x.height, reverse=True)

	for cached_block in sorted_blocks:
		network_block = daemon.get_block(cached_block.height)

		# If found a match
		if 'block_header' in network_block and network_block['block_header']['hash'] == cached_block.hash:
			return cached_block

# Program entry point
if __name__ == '__main__':
	exitcode = main()
	exit(0 if exitcode is None else exitcode)
