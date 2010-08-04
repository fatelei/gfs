"""
In the GFS the client's job is to:
- request reads and mutations from the master
- write data to all chunkservers
- retry failures
- break writes into small enough chunks to succeed
- manage any locking or operation ordering (in GFS two clients can
  write to the same chunk in an append, both writes may succeed but
  the order will be uncontrolled by the GFS)

Client operations:
- create
- delete
- open
- close
- read
- write
- snapshot
- append
"""
import random

# package modules
import net
import msg
from log import log as _log # cheesy

try:
	import settings # Assumed to be in the same directory.
except ImportError:
	sys.stderr.write("Error: Can't find the file 'settings.py' in the directory containing %r. This is required\n" % __file__)
	sys.exit(1)
	
	if(settings.DEBUG):
		reload(settings)


def log(str):
	_log("[client] " + str)


def read(fname, offset, len):
	"""involves these steps:
	1 request (fname/offset) from the master
	1a master puts read lock on fname
      2 receive a chunk handle and set of chunkservers with chunk
	3 pick a chunkserver (nearest), request the data
	4 close handle on the master
	4a master releases lock
	"""
	log("read(%s,%i,%i)"%(fname,offset,len))
	sock = net.client_sock(settings.MASTER_ADDR, settings.MASTER_CLIENT_PORT)
	log("read: connected to master")
	sock.setblocking(False)
	master_comm  = net.PakComm(sock)
	chunk_index = offset/settings.CHUNK_SIZE
	master_comm.send_obj(msg.ClientRead(fname,chunk_index,len))

	# wait for handle (yield)
	log("read: entering wait loop")
	while True:
		chunk_info = master_comm.recv_obj()
		if not chunk_info:
			yield None
		else:
			break
	if isinstance(chunk_info,msg.ReadErr):
		log("read request failed: '%s'" % str(chunk_info))
		return 

	# pick a chunkserver to talk to
	random.shuffle(chunk_info.servers)
	chunkaddr = chunk_info.servers[0]
	chunksock = net.client_sock(chunkaddr, settings.CHUNK_CLIENT_PORT)
	chunk_comm = net.PakComm(chunksock)
	read_req = msg.ClientRead(chunk_info.id,offset,len)
	chunk_comm.send_obj(read_req)

	# wait for handle (yield)
	yield None
	while True:
		read_res = chunk_comm.recv_obj()
		if not read_res: 
			yield None
		else:
			break
	yield read_res
	return 

def test():
	read("foo",0,32)
