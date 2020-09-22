import appdirs
import argparse
import os.path

from .blobcache import BlobCache
from . import xmrconn

def get_parser():
	""" Returns an argparse.ArgumentParser object for this program """

	prog = 'python3 -m xmr-haystack'
	desc = 'America\'s favorite stealth address scanner\u2122'
	parser = argparse.ArgumentParser(prog=prog, description=desc)
	parser.add_argument('wallet file',
		help='path to wallet file')
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

def validate_and_process(ns, wallet_pass=None):
	"""
	Checks the arguments in namespace for any conditions not handled by get_parser

	Raises a ValueError if there is a unfixable problem with the arguments. Attempts to fix
	problems where it can and inserts defaults where argparse fell short. Wallet password 
	is not in ns because the wallet password shouldn't be passed on the command-line.

	ns: Namespace object returned by argparse.ArgumentParser.parse_args
	wallet_pass: str, password for wallet. If None, then doesn't check wallet login

	Returns: a dict containing following entries:
		'walletf' -> str, valid path to monero wallet file
		'height' -> int >= 0, height to scan from instead of default. None if program should decide
		'daddr' -> str, valid address (port not included) of monero daemon
		'dport' -> int, valid port of monero daemon
		'dlogin' -> bool, True if valid login is specified, False if not specified
		'duser' -> str, valid daemon username. None if daemon_login == False
		'dpass' -> str, valid daemon password. None if daemon_login == False
		'restricted' -> bool, True if only restricted RPC is enabled
		'caching' -> bool, True if program should cache, False only if explicitly specified
		'cachein' -> BlobCache, cache object at --cache-input file. None if not caching or unable to load cache
		'cacheout' -> open() file, writable file at --cache-output. None if not caching
		'wallcmd' -> str, monero-wallet-cli shell command name
	"""

	settings = {}
	cache_base = appdirs.user_cache_dir('xmr-haystack')
	default_cache_path = os.path.join(cache_base, 'xmrhaystack.json')

	settings['walletf'] = getattr(ns, 'wallet file')

	# Check scan height
	settings['height'] = ns.height

	if ns.height is not None and ns.height < 0:
		raise ValueError('error: --height can not be less than zero')

	# Check daemon login flag parseability
	settings['dlogin'] = ns.login is not None

	if ns.login is not None:
		print("Warning: passing passwords as command line arguments is unsafe!")

		login_comps = ns.login.split(':')

		if len(login_comps) != 2:
			raise ValueError('error: --daemon-login must be in form [username]:[password]')

		settings['duser'], settings['dpass'] = login_comps
	else:
		settings['duser'], settings['dpass'] = None, None

	# Check daemon address + port + login
	conn = xmrconn.DaemonConnection(ns.addr, ns.port, settings['duser'], settings['dpass'])

	print("Checking daemon access...")
	try:
		info = conn.get_info()
	except:
		err_msg = 'error: daemon at {} not reachable'.format(conn.host())
		raise ValueError(err_msg)

	if 'status' not in info or info['status'] != 'OK':
		raise ValueError('error: daemon responded unexpectedly')

	settings['daddr'] = ns.addr
	settings['dport'] = ns.port

	# sync_info is a command only allowed in unrestricted RPC mode. If it isn't enabled, there's a
	# good chance that the daemon will reject large get_transactions requests. Warn the user of this
	print("Checking restricted RPC command access...")

	try:
		sync_info = conn.sync_info()
	except:
		err_msg = 'error: daemon at {}:{} not reachable'.format(ns.addr, ns.port)
		raise ValueError(err_msg)

	# If in unrestricted mode then resp['result']['status'] == 'OK'
	settings['restricted'] = sync_info is None
	if settings['restricted']:
		print("Warning: daemon is in restricted RPC mode. Some functionality may not be available")

	# Check monero-wallet-cli
	settings['wallcmd'] = ns.cli_exe_file.name if ns.cli_exe_file else 'monero-wallet-cli'
	if not xmrconn.WalletConnection.valid_executable(settings['wallcmd']):
		err_msg_temp = 'error: command "{}" gave a bad response. Try specifying --wallet-cli-path'
		err_msg = err_msg_temp.format(settings['wallcmd'])
		raise ValueError(err_msg)

	# Check wallet login if password is supplied
	if wallet_pass is not None:
		print("Checking wallet login...")
		wallet = xmrconn.WalletConnection(settings['walletf'], wallet_pass, conn.host(), ns.login, cmd=settings['wallcmd'])

		if not wallet.is_valid():
			raise ValueError('error: failed to login to wallet')

	# Check cache file arguments
	settings['caching'] = not ns.no_cache
	if ns.no_cache:
		if ns.cache_in is not None or ns.cache_out is not None:
			raise ValueError('error: --cache-input and --cache-output can\'t be set if" \
				" --no-cache is set')

		settings['cachein'] = None
		settings['cacheout'] = None
	else: # should cache
		# Prepare cache dir
		try:
			os.makedirs(cache_base, exist_ok=True)
		except:
			print("Warning: could not prepare cache directory!")

		# Work on input cache. Output cache depends on input cache if unspecified
		if ns.cache_in is not None:
			try:
				settings['cachein'] = cache_in_file = BlobCache.load(ns.cache_in)
			except:
				raise ValueError(f'error: unable to open cache file "{ns.cache_in}"')
		else: # cache in not specified
			try:
				if os.path.isfile(default_cache_path):
					cache_in_file = open(default_cache_path, 'r+')
					settings['cachein'] = BlobCache.load(cache_in_file)
				else:
					cache_in_file = open(default_cache_path, 'w+')
					settings['cachein'] = None
			except Exception as e:
				print(e)
				print(f"Can't open default cache file \"{default_cache_path}\". Continuing without cache...")
				cache_in_file = None
				settings['cachein'] = None

		# At this point cache_in_file is either a file object or None
		# Now to do cache output

		if ns.cache_out:
			settings['cacheout'] = ns.cache_out
		else:
			if cache_in_file is not None:
				# If file has already been read as cache input, and output is same file, clear then assign
				# cachin to cacheout
				cache_in_file.seek(0)
				cache_in_file.truncate()
				settings['cacheout'] = cache_in_file
			else:
				try:
					settings['cacheout'] = open(default_cache_path, 'w')
				except:
					print(f"Can't write to file \"{default_cache_path}\". Continuing without cache...")
					settings['cacheout'] = None

	return settings
