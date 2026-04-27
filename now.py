import time
from datetime import datetime

now = datetime.now().astimezone()
ts = time.time()
timezone_name = time.tzname[0] if time.tzname else "unknown"

print(f"当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"时区:     {timezone_name}")
print(f"时区名:   {now.tzname() or 'unknown'}")
print(f"偏移:     {now.strftime('%z')}  ({now.strftime('%:z')})")
print(f"时间戳:   {int(ts)}")
print(f"毫秒戳:   {int(ts * 1000)}")
