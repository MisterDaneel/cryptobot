import sys
import time
import json
import requests
import threading
from base_logger import crash_stack, logger, my_logger, timestamp

# cli
from cli import run_cli, update

# binance
from exchanges.binance import Exchange

# valid intervals - 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h,
#                   1d, 3d, 1w, 1M

def print_result(asset, result):
    ''' just print order result '''

    logger.info(
        '\n{}'.format(
            json.dumps(result, indent=4)
        )
    )

    bot_message(
        '<code>{}</code>'.format(json.dumps(result, indent=4))
    )
    try:
        result['timestamp'] = timestamp()
        with open(
            'logs/' + asset + '_order_history.json',
            mode='a',
            encoding='utf-8'
        ) as logfile:
            json.dump(result, logfile, indent=4)
    except Exception as e:
        crash_stack(e)


def truncate(value, n):
    '''Truncates/pads a float f to n decimal places without rounding'''
    s = '{}'.format(value)
    i, p, d = s.partition('.')
    return float('.'.join([i, (d+('0'*n))[:n]]))


def value_filter(value, value_filter):
    number_after_dot = str(value_filter.split(".")[1])
    index = number_after_dot.find("1")
    if index == -1:
        value = int(value)
    else:
        value = truncate(float(value), int(index + 1))
    return float(value)


def create_order(side, quantity, price, order, break_even=0):
    price = value_filter(price, exchange.tick)
    break_even = value_filter(break_even, exchange.tick)
    quantity = value_filter(quantity, exchange.step)
    result = exchange.create_order(side, quantity, price, order, break_even)
    if not result:
        exchange.stop_ticker()
        return result
    print_result(asset, result)
    return result


def check_order(tp_status, state, price):
    if status['count'] == 0:
        if tp_status['type'] == 'order_list':
            for order in tp_status['orders']:
                if 'stop_loss' not in order:
                    result = exchange.get_order(order['order_id'])
        else:
            result = exchange.get_order(tp_status['order_id'])
        tp_status['status'] = result['status']
        status['count'] += 1
    else:
        status['count'] += 1
        if status['count'] == 60:
            status['count'] = 0
    infos = '{}: {}$ | {:.2f}% | {} {}'.format(
        asset,
        price,
        percent(config['PRU'], price),
        state.upper(),
        tp_status['status'],
    )
    return infos


def percent(PRU, price):
    if price == PRU:
        percent = 0
    elif price < PRU:
        percent = -1 * (100 - (100 * price / PRU))
    else:
        percent = (100 - (100 * PRU / price))
    return percent


def trade(price):
    infos = '{}: {}$ | {:.2f}%'.format(
        asset,
        price,
        percent(config['PRU'], price),
    )

    if not status['entry']['status']:
        # buy entry order
        result = create_order(
            'BUY',
            status['quantity'],
            config['PRU'],
            'LIMIT'
        )
        if not result:
            return
        status['entry'] = result
        status['count'] = 0
    elif status['entry']['status'] != 'DONE':
        # check buy limit order status
        infos = check_order(status['entry'], 'entry', price) 
    elif 'TPS' in status:
        TPS = status['TPS']
        if not TPS['TP1']['order_id']:
            # sell TP1 order
            result = exchange.get_order(status['entry']['order_id'])
            print_result(asset, result)
            # TP1
            if "STOPLOSS" in config:
                result = create_order(
                    'SELL',
                    TPS['TP1']['quantity'],
                    TPS['TP1']['price'],
                    'OCO',
                    config['STOPLOSS'],
                )
                result_sl = create_order(
                    'SELL',
                    status['quantity'] - TPS['TP1']['quantity'],
                    config['STOPLOSS'],
                    'STOPLIMIT'
                )
                status['STOPLOSS'] = result_sl
            else:
                result = create_order(
                    'SELL',
                    TPS['TP1']['quantity'],
                    TPS['TP1']['price'],
                    'LIMIT',
                )
            if not result:
                return
            TPS['TP1'] = result
            status['count'] = 0
        elif TPS['TP1']['status'] != 'DONE':
            # check sell limit order status
            infos = check_order(TPS['TP1'], 'TP1', price) 
            if "STOPLOSS" in config:
                for order in TPS['TP1']['orders']:
                    if 'stop_loss' not in order:
                        result = exchange.get_order(order['order_id'])
            else:
                result = exchange.get_order(TPS['TP1']['order_id'])
        elif ((TPS['TP1']['status'] == 'DONE') and ('order_id' not in TPS['TP2'])):
            if "STOPLOSS" in config:
                exchange.cancel_order(status['STOPLOSS']['order_id'])
                status['STOPLOSS']['status'] = 'CANCELED'
            break_even = config['PRU'] * 1.01
            for TP in TPS:
                if TP == 'TP1':
                    continue
                result = create_order(
                    'SELL',
                    TPS[TP]['quantity'],
                    TPS[TP]['price'],
                    'OCO',
                    break_even
                )
                if not result:
                    continue
                TPS[TP] = result
        else:
            for TP in TPS:
                if TPS[TP]['status'] == 'DONE':
                    continue
                infos = check_order(TPS[TP], TP, price) 
                break # only check next to not done
    #sys.stdout.flush()
    #sys.stdout.write(str(infos).ljust(70) + "\r")
    update(cli_msg(config['PRU'], price, status['quantity']))


def save_status():
    try:
        with open(
            config['asset'] + '_status.json',
            'w'
        ) as status_file :
            json.dump(status, status_file, indent=4)
    except Exception as e:
        crash_stack(e)


def asset_trade_process(msg):
    ''' define how to process incoming WebSocket messages '''

    price = exchange.kline_ticker_parser(msg)
    if not price:
        return

    trade(price)
    save_status()


def tp_infos(tp_price, tp_quantity):
    percent = '{:.2f}'.format(100 - (100 * config['PRU'] / tp_price))
    profits = '{:.2f}'.format((tp_price - config['PRU']) * tp_quantity)
    return {'profits': profits, 'percent': percent, 'quantity': tp_quantity}


def print_initial_conf():
    text = '<b>{}</b>/{}\n'.format(asset, config['pair'])
    text += '<b>WAGER</b> {}\n'.format(config['wager'])
    text += '<b>PRU</b> {} ({:g} {})\n'.format(
        config['PRU'],
        status['quantity'],
        asset
    )
    if 'STOPLOSS' in config:
        text += '<b>STOPLOSS</b> {}\n'.format(config['STOPLOSS'])

    def print_tp(TP, tp_price, tp_quantity):
        infos = tp_infos(tp_price, tp_quantity)
        return '<b>{}</b> {} ({}%) <i>profit: {}$ ({} {})</i>\n'.format(
                TP,
                tp_price,
                infos['percent'],
                infos['profits'],
                infos['quantity'],
                asset,
            )

    if 'TPS' in status:
        for TP in sorted(status['TPS']):
            print(TP)
            print(status['TPS'][TP])
            text += print_tp(
                TP,
                status['TPS'][TP]['price'],
                status['TPS'][TP]['quantity']
            )
    bot_message(text)


def cli_msg(PRU, price, quantity):
    price = value_filter(
        price,
        exchange.tick
    )
    gain = value_filter(
        quantity*(price-PRU),
        exchange.tick
    )
    entry = {
        'status': 'NEW',
        'price':  config['PRU'],
        'wager':  config['wager'],
        'quantity':  status['quantity'],
    }
    if status['entry']['status']:
        entry['status'] =status['entry']['status']
    stoploss = 'None'
    if "STOPLOSS" in config:
        stoploss = config["STOPLOSS"]
    res = {
        'coin': asset,
        'price': price,
        'gain': gain,
        '%': '{:.2f}'.format(percent(PRU, price)),
        'entry': entry,
        'stoploss': stoploss,
        'TPS': status['TPS']
    }
    return res


def get_tps_from_config():
    TP1_quantity = status['quantity'] * 0.3
    if TP1_quantity < exchange.min:
        TP1_quantity = exchange.min
    TP1_quantity = value_filter(
        TP1_quantity,
        exchange.step
    )
    remainder = status['quantity'] - TP1_quantity
    TP_quantity = remainder / (len(config['TPS']) - 1)
    TP_quantity = value_filter(
        TP_quantity,
        exchange.step
    )
    status['TPS'] = {}
    for count, TP in enumerate(sorted(config['TPS'])):
        count += 1
        status['TPS']['TP{}'.format(count)] = {
            'status': 'NEW',
            'order_id': None,
            'quantity': TP1_quantity if count == 1 else TP_quantity,
            'price': TP,
        }


if __name__ == "__main__":

    config_file = sys.argv[1]

    with open(config_file, 'r') as json_file:
        config = json.load(json_file)

    if not 'pair' in config:
        config['pair'] = 'USDT'

    asset = config['asset']
    my_logger.set_asset(asset)

    print('Initialize the client...')
    exchange = Exchange(asset, config['pair'])

    # get status
    with open(
        config['asset'] + '_status.json',
        'r'
    ) as json_file:
        status = json.load(json_file)
    try:
        with open(
            config['asset'] + '_status.json',
            'r'
        ) as json_file:
            status = json.load(json_file)
    except:
        quantity = (config['wager']) / config['PRU']
        quantity = value_filter(
            quantity,
            exchange.step
        )

        status = {
            'quantity': quantity,
            'entry': { 
                'status': None,
                'order_id': None,
            },
        }

    if not 'TPS' in status: 
        if 'TPS' in config:
            get_tps_from_config() 

    status['count'] = 0

    print(json.dumps(status))
    print_initial_conf()

    print('Start...')

    t = threading.Thread(target=exchange.start_kline_ticker, args=(asset_trade_process, ))
    t.start()
    # cli
    run_cli()
