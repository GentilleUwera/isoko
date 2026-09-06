"""One isolated node process. JSON control over local stdin/stdout."""
import json
import sys
from .core import Node

node = Node(sys.argv[1])
for line in sys.stdin:
    try:
        request = json.loads(line)
        op = request.pop('op')
        if op not in ('receive', 'items', 'ack', 'attempted', 'select'):
            raise ValueError('Unsupported operation')
        result = getattr(node, op)(**request)
        print(json.dumps({'ok': result}), flush=True)
    except Exception as error:
        print(json.dumps({'error': str(error)}), flush=True)
node.close()
