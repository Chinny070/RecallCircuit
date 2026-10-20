"""Read-only network gate. Never switches networks or submits transactions."""
import json
import sys
from urllib.request import Request, urlopen

RPC='https://studio.genlayer.com/api'
CHAIN=61999

def check():
    payload=json.dumps({'jsonrpc':'2.0','id':1,'method':'eth_chainId','params':[]}).encode()
    request=Request(RPC,payload,{'Content-Type':'application/json'})
    with urlopen(request,timeout=12) as response:
        obj=json.load(response)
    actual=int(obj['result'],16)
    if actual != CHAIN:
        raise RuntimeError(f'STOP: wrong chain {actual}, expected {CHAIN}')
    print(f'PASS: StudioNet chain {actual} at {RPC} (read-only)')

if __name__=='__main__':
    try:check()
    except Exception as e:
        print(f'BLOCKED: {e}',file=sys.stderr)
        sys.exit(2)
