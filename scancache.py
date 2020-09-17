import base64
from cryptography.fernet import Fernet
import hashlib
import json

class ScanCache(object):
	def __init__(self, blobs = []):
		self.blobs = blobs

	def save(self, file):
		contents = {
			'version': ScanCache.current_version(),
			'blobs': [base64.b64encode(blob).decode() for blob in self.blobs]
		}

		file.write(json.dumps(contents))

	def add_obj(self, obj, key):
		f = Fernet(key)

		blob_structure = {
			'blob': True,
			'data': obj
		}

		blob_json_str = json.dumps(blob_structure)
		blob = f.encrypt(blob_json_str.encode())

		self.blobs.append(blob)

	def get_objs(self, keys):
		fernets = [Fernet(key) for key in keys]

		objs = []

		for blob in self.blobs:
			for f in fernets:
				try:
					decrypted = f.decrypt(blob)
					blob_contents = json.loads(decrypted.decode())

					if blob_contents['blob'] is not True:
						continue

					obj = blob_contents['data']
					objs.append(obj)
				except:
					pass

		return objs

	@classmethod
	def load(cls, file):
		contents = json.loads(file.read())

		if 'version' not in contents or 'blobs' not in contents:
			raise ValueError('Incorrect JSON for ScanCache')
		elif contents['version'] != cls.current_version():
			raise ValueError('Incorrect ScanCache version')

		blobs = [base64.b64decode(blob) for blob in contents['blobs']]

		return ScanCache(blobs)

	@classmethod
	def gen_key(cls, pubkey, password):
		if not pubkey or not password:
			raise ValueError('both argument must not be falsey')

		h = hashlib.sha256()
		h.update(pubkey.encode())
		h.update(password.encode())

		b = base64.b64encode(h.digest())

		return b[:44]

	@classmethod
	def gen_keys(cls, pairs):
		keys = [cls.generate_key(*pair) for pair in pairs]

		return keys

	@classmethod
	def current_version(cls):
		return 'sc1'
