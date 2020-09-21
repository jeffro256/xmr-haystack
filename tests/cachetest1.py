from blobcache import BlobCache

data = {chr(x + ord('A')):x for x in range(26)}
key = BlobCache.gen_key('password123')
save_file = 'cachetest1_out.json'

b = BlobCache()
b.add_obj(data, key)

print(b.get_objs(key))

with open(save_file, 'w') as f:
	b.save(f)
