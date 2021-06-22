from datetime import datetime, timedelta, timezone
from aiopvpc import PVPCData, TARIFFS
import pandas as pd
import asyncio
from tabulate import tabulate
import pytz as tz

pvpc_handler = PVPCData(tariff=TARIFFS[0], local_timezone='Europe/Madrid')

start = datetime(2021, 6, 1)
end = datetime.today() + timedelta(days=1)
prices_range = asyncio.get_event_loop().run_until_complete(pvpc_handler.async_download_prices_for_range(start, end))
df = pd.DataFrame([{'datetime': x.astimezone(tz.timezone('Europe/Madrid')),'date': x.astimezone(tz.timezone('Europe/Madrid')).strftime("%d-%m-%Y"), 'hour': f"{x.astimezone(tz.timezone('Europe/Madrid')).strftime('%H')} - {(x.astimezone(tz.timezone('Europe/Madrid'))+timedelta(hours=1)).strftime('%H')} h", 'price': prices_range[x]} for x in prices_range])
print(tabulate(df, headers = 'keys', tablefmt = 'psql'))