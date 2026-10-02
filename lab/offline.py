"""An optional process-local network boundary; never changes machine settings."""
import ipaddress
import os
import sys

def enable_offline():
    os.environ["LAB_OFFLINE"] = "1"
    def audit(event, args):
        if event == "socket.connect":
            address = args[1]
            if isinstance(address, tuple):
                host = str(address[0])
                try:
                    local = ipaddress.ip_address(host).is_loopback
                except ValueError:
                    local = host.lower() == "localhost"
                if not local:
                    raise OSError("Offline demonstration: external network access is disabled")
        if event == "socket.getaddrinfo" and str(args[0]).lower() not in ("localhost", "127.0.0.1", "::1", "none"):
            raise OSError("Offline demonstration: external name lookup is disabled")
    sys.addaudithook(audit)
