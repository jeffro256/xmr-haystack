import base64
from cryptography.fernet import Fernet
import hashlib
import json
import os

class BlobCache(object):
	def __init__(self, blobs = {}, salt=None):
		self.blobs = blobs
		self.salt = salt if salt else base64.b64encode(os.urandom(32)).decode()

	def save(self, file):
		contents = {
			'version': self.current_version(),
			'blobs': self.blobs,
			'salt': self.salt
		}

		file.write(json.dumps(contents))

	def add_obj(self, obj, passphrase):
		key = self.gen_key(passphrase)

		f = Fernet(key)
		key_id = self.key_id(key)

		blob_json_str = json.dumps(obj)
		blob_encrypted = f.encrypt(blob_json_str.encode())
		blob = base64.b64encode(blob_encrypted).decode()

		if key_id in self.blobs:
			self.blobs[key_id].append(blob)
		else:
			self.blobs[key_id] = [blob]

	def get_objs(self, passphrase):
		key = self.gen_key(passphrase)
		f = Fernet(key)
		key_id = self.key_id(key)

		if key_id not in self.blobs:
			return []

		blobs = self.blobs[key_id]
		objs = []

		for blob in blobs:
			try:
				blob_decoded = base64.b64decode(blob.encode())
				blob_decrypted = f.decrypt(blob_decoded)
				blob_contents = json.loads(blob_decrypted.decode())

				objs.append(blob_contents)
			except:
				pass

		return objs

	def clear_objs(self, passphrase):
		key = self.gen_key(passphrase)
		key_id = self.key_id(key)

		if key_id in self.blobs:
			self.blobs.pop(key_id, None)

	def pop_objs(self, passphrase):
		key = self.gen_key(passphrase)
		objs = self.get_objs(key)
		self.clear_objs(key)

		return objs

	def gen_key(self, seed):
		if not seed:
			raise ValueError('key seed must not be falsey')
		elif type(seed) != bytes:
			seed = str(seed).encode()

		h = hashlib.sha256()
		h.update(seed)
		h.update(self.salt.encode())
		key = base64.b64encode(h.digest())

		return key

	@classmethod
	def load(cls, file):
		contents = json.loads(file.read())

		if 'version' not in contents or 'blobs' not in contents or 'salt' not in contents:
			raise ValueError('Incorrect JSON for ScanCache')
		elif contents['version'] != cls.current_version():
			raise ValueError('Incorrect ScanCache version')

		blobs = contents['blobs']
		salt = contents['salt']

		return cls(blobs, salt)

	@classmethod
	def key_id(cls, key):
		h = hashlib.sha256()
		h.update(key)
		kid = base64.b64encode(h.digest()).decode()

		return kid

	@classmethod
	def current_version(cls):
		return 'sc1'

