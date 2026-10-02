import subprocess
import sys

def test_offline_guard_blocks_external_sockets_and_dns_without_changing_host():
    code = '''
from lab.offline import enable_offline
import socket
enable_offline()
blocked = 0
for attempt in [lambda: socket.getaddrinfo('example.com',443), lambda: socket.socket().connect(('1.1.1.1',443))]:
    try: attempt()
    except OSError as error:
        assert 'Offline demonstration' in str(error)
        blocked += 1
assert blocked == 2
assert socket.getaddrinfo('127.0.0.1',8765)
server = socket.socket()
server.bind(('127.0.0.1',0))
server.listen(1)
client = socket.socket()
client.connect(server.getsockname())
peer, _ = server.accept()
client.send(b'local')
assert peer.recv(5) == b'local'
print('External access blocked; localhost works')
'''
    result = subprocess.run([sys.executable,"-c",code],capture_output=True,text=True,timeout=15)
    assert result.returncode == 0, result.stderr
