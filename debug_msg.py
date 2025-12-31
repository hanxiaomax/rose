from rosbags.highlevel import AnyReader
from pathlib import Path
import sys

bag_path = Path("roseApp/tests/bash_tests/demo1.bag")
with AnyReader([bag_path]) as reader:
    # Get first connection
    if not reader.connections:
        print("No connections found")
        sys.exit(1)
        
    conn = reader.connections[0]
    print(f"Topic: {conn.topic}")
    
    gen = reader.messages(connections=[conn])
    conn, ts, raw = next(gen)
    msg = reader.deserialize(raw, conn.msgtype)
    
    print(f"Type: {type(msg)}")
    print(f"Has __slots__: {hasattr(msg, '__slots__')}")
    if hasattr(msg, '__slots__'):
        print(f"Slots: {msg.__slots__}")
        
    print(f"Has __dict__: {hasattr(msg, '__dict__')}")
    print(f"Dir: {dir(msg)}")
