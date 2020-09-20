import base64
from cryptography.fernet import Fernet
import hashlib
import json

class BlobCache(object):
	def __init__(self, blobs = {}):
		self.blobs = blobs

	def save(self, file):
		contents = {
			'version': BlobCache.current_version(),
			'blobs': self.blobs
		}

		file.write(json.dumps(contents))

	def add_obj(self, obj, key):
		f = Fernet(key)
		key_id = BlobCache.key_id(key)

		blob_structure = {
			'blob': True,
			'data': obj
		}

		blob_json_str = json.dumps(blob_structure)
		blob_encrypted = f.encrypt(blob_json_str.encode())
		blob = base64.b64encode(blob_encrypted).decode()

		if key_id in self.blobs:
			self.blobs[key_id].append(blob)
		else:
			self.blobs[key_id] = [blob]

	def get_objs(self, key):
		f = Fernet(key)
		key_id = BlobCache.key_id(key)

		if key_id not in self.blobs:
			return []

		blobs = self.blobs[key_id]
		objs = []

		for blob in blobs:
			try:
				blob_decoded = base64.b64decode(blob.encode())
				blob_decrypted = f.decrypt(blob_decoded)
				blob_contents = json.loads(blob_decrypted.decode())

				if blob_contents['blob'] is not True:
					continue

				obj = blob_contents['data']
				objs.append(obj)
			except:
				pass

		return objs

	def clear_objs(self, key):
		key_id = BlobCache.key_id(key)

		if key_id in self.blobs:
			self.blobs.pop(key_id, None)

	def pop_objs(self, key):
		objs = self.get_objs(key)
		self.clear_objs(key)

		return objs

	@classmethod
	def load(cls, file):
		contents = json.loads(file.read())

		if 'version' not in contents or 'blobs' not in contents:
			raise ValueError('Incorrect JSON for ScanCache')
		elif contents['version'] != cls.current_version():
			raise ValueError('Incorrect ScanCache version')

		blobs = contents['blobs']

		return BlobCache(blobs)

	@classmethod
	def gen_key(cls, seed):
		if not seed:
			raise ValueError('key seed must not be falsey')
		elif type(seed) == str:
			seed = seed.encode()

		h = hashlib.sha256()
		h.update(seed)
		b = base64.b64encode(h.digest())
		key = b[:44]

		return key

	@classmethod
	def key_id(cls, key):
		h = hashlib.sha256()
		h.update(key)
		id = base64.b64encode(h.digest()).decode()

		return id

	@classmethod
	def current_version(cls):
		return 'sc1'
