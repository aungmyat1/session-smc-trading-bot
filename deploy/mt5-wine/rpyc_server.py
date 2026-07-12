from typing import Optional

import rpyc
from rpyc.utils.server import ThreadedServer

import MetaTrader5 as mt5

TERMINAL_PATH = r'C:\Program Files\MetaTrader 5\terminal64.exe'


class MT5Service(rpyc.Service):
    def exposed_login(self, login: str, password: str, server: str) -> bool:
        if not mt5.initialize(path=TERMINAL_PATH, portable=True):
            raise RuntimeError(f'MT5 initialize failed: {mt5.last_error()}')
        ok = mt5.login(int(login), password=password, server=server)
        if not ok:
            raise RuntimeError(f'MT5 login failed: {mt5.last_error()}')
        return True

    def exposed_account_info(self) -> dict:
        info = mt5.account_info()
        return {'balance': info.balance, 'equity': info.equity, 'margin': info.margin, 'free_margin': info.margin_free}

    def exposed_positions_get(self, symbol: Optional[str] = None) -> list:
        positions = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
        return [p._asdict() for p in (positions or [])]

    def exposed_symbol_info_tick(self, symbol: str) -> dict:
        tick = mt5.symbol_info_tick(symbol)
        return {'bid': tick.bid, 'ask': tick.ask, 'time': tick.time}


if __name__ == '__main__':
    ThreadedServer(MT5Service(), port=18812, protocol_config={'allow_public_attrs': True}).start()
