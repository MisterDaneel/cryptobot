import json
import requests
from base_logger import crash_stack, logger

from binance.client import Client
from binance.websockets import BinanceSocketManager
from binance.exceptions import BinanceRequestException, BinanceAPIException, BinanceWithdrawException


class Exchange:

    # valid intervals - 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h,
    #                   1d, 3d, 1w, 1M

    def __init__(self, asset, pair):
        """
        Initializes binance module with the given config
        """
        api_key = config['api_key'] 
        api_secret = config['api_secret']
        self.client =  Client(api_key, api_secret)
        self.asset = asset
        self.pair = pair
        self.interval = "1d"

        info = self.client.get_symbol_info('{}{}'.format(asset, pair))
        self.tick = info["filters"][0]["tickSize"]
        self.step = info["filters"][2]["stepSize"]
        self.min = float(info["filters"][2]["minQty"])

        self.get_candles()
        self.bsm = BinanceSocketManager(self.client)

    def start_symbol_ticker(self, asset_trade_process):
        """
        Initializes and starts the symbol ticker socket
        """
        conn_key = self.bsm.start_symbol_ticker_socket(
            symbol='{}{}'.format(self.asset, self.pair),
            callback=asset_trade_process
        )
        self.bsm.start()

    def start_kline_ticker(self, asset_trade_process):
        conn_key = self.bsm.start_kline_socket(
            symbol='{}USDT'.format(self.asset),
            interval=self.interval,
            callback=asset_trade_process
        )
        self.bsm.start()

    def get_order(self, order_id):
        #print('get_order', order_id)
        result = self.client.get_order(
            symbol='{}{}'.format(self.asset, self.pair),
            orderId=order_id
        )
        logger.debug(result)
        result = self.format_result(result)
        return result

    def cancel_order(self, order_id):
        #print('cancel_order', order_id)
        result = self.client.cancel_order(
            symbol='{}{}'.format(self.asset, self.pair),
            orderId=order_id
        )
        return result

    def stop_ticker(self):
        self.bsm.close()
        logger.info('Stop the client...')

    def symbol_ticker_parser(self, msg):
        """
        Get price from the symbol ticker socket
        """
        if msg['e'] == 'error':
            return
        price = float(msg['c'])
        return price

    def kline_ticker_parser(self, msg):
        """
        Get price from the klines socket
        """
        if msg['e'] == 'error':
            return

        candle = [
            msg['k']["t"],
            msg['k']["o"],
            msg['k']["h"],
            msg['k']["l"],
            msg['k']["c"],
        ]

        if msg["k"]["x"] == False:
            self.candles = self.candles[:-1]
            self.candles.append(candle)
        else:
            self.candles = self.candles[1:]
            self.candles.append(candle)

        return float(candle[4])


    def create_limit_order(self, side, quantity, price):
        result = self.client.order_limit(
            symbol='{}{}'.format(self.asset, self.pair),
            side=side,
            quantity=quantity,
            price=price
        )
        return result

    def create_stop_limit_order(self, side, quantity, price):
        result = self.client.create_order(
            symbol='{}{}'.format(self.asset, self.pair),
            side=side,
            quantity=quantity,
            price=price,
            stopPrice=price,
            type='STOP_LOSS_LIMIT',
            newOrderRespType='FULL',
            timeInForce='GTC'
        )
        return result

    def create_oco_order(self, side, quantity, price, stop_loss):
        result = self.client.create_oco_order(
            symbol='{}{}'.format(self.asset, self.pair),
            side=side,
            quantity=quantity,
            price=price,
            stopPrice=stop_loss,
            stopLimitPrice=stop_loss,
            stopLimitTimeInForce='GTC'
        )
        return result

    def create_order(self, side, quantity, price, order, stop_loss):
        result = 0
        #print(order, side, quantity, price, stop_loss)
        try:
            if order == 'LIMIT':
                result = self.create_limit_order(side, quantity, price)
            elif order == 'STOPLIMIT':
                result = self.create_stop_limit_order(side, quantity, price)
            elif order == 'OCO':
                result = self.create_oco_order(side, quantity, price, stop_loss)
            else:
                logger.error('Order exception: {}'.format(
                    e.message
                ))
                return 0
            logger.info(result)
            result = self.format_result(result, side, quantity, price, stop_loss)
            #print(result)
        except BinanceAPIException as e:
            crash_stack(e)
            logger.error('BinanceAPIException; {}'.format(
                e.message
            ))
        except BinanceWithdrawException as e:
            logger.error('BinanceWithdrawException; {}'.format(
                e.message
            ))
        except requests.exceptions.Timeout:
            logger.error('Request timeout')
        except Exception as e:
            crash_stack(e)
        return result

    def format_result(self, result, side='UNKNOWN', quantity=0, price=0, stop_loss=0):
        formatted_result = {}
        formatted_result['side'] = side
        formatted_result['quantity'] = quantity
        formatted_result['price'] = price
        if stop_loss:
            formatted_result['stop_loss'] = stop_loss
        if 'timestamp' in result:
            formatted_result['timestamp'] = result['timestamp']
        if 'orderId' in result:
            formatted_result['type'] = 'order'
            formatted_result['order_id'] = result['orderId']
        elif 'orderListId' in result:
            formatted_result['type'] = 'order_list'
            formatted_result['order_id'] = result['orderListId']
            formatted_result['orders'] = []
            for order in result['orderReports']:
                 if order['type'] == 'STOP_LOSS_LIMIT':
                    result_order = self.format_result(
                        order,
                        side,
                        float(order['origQty']),
                        float(order['stopPrice']),
                        1
                    )
                    formatted_result['orders'].append(result_order)
                 if order['type'] == 'LIMIT_MAKER':
                    result_order = self.format_result(
                        order,
                        side,
                        float(order['origQty']),
                        float(order['price']),
                        0
                    )
                    formatted_result['orders'].append(result_order)
        if 'status' in result:
            if result['status'] in ['NEW', 'PARTIALLY_FILLED']:
                formatted_result['status'] = 'NEW'
            elif result['status'] in ['FILLED']:
                formatted_result['status'] = 'DONE'
            else:
                formatted_result['status'] = 'FAILED'
        elif 'listOrderStatus' in result:
            if result['listOrderStatus'] in ['EXECUTING']:
                formatted_result['status'] = 'NEW'
            elif result['listOrderStatus'] in ['ALL_DONE']:
                formatted_result['status'] = 'DONE'
            else:
                formatted_result['status'] = 'FAILED'
        else:
            formatted_result['status'] = 'UNKNOWN'
        return formatted_result


    def get_candles(self):
        try:
            self.candles = self.client.get_klines(
                symbol='{}USDT'.format(self.asset),
                interval=self.interval,
                #limit=2,
            )
        except BinanceRequestException as e:
            self.logger.error('BinanceRequestException; {} {}'.format(
                e.message
            ))
        except BinanceAPIException as e:
            self.logger.error('BinanceAPIException; {} {}'.format(
                e.message
            ))
        except requests.exceptions.Timeout:
            self.logger.error('Request timeout')
        except requests.exceptions.ConnectionError:
            self.logger.error('Request connection error')
        except Exception as e:
            crash_stack(e)

        # delete unwanted data - just keep date, open, high, low, close
        for candle in self.candles:
            del candle[5:]

    def get_asset_balance(self):
        """
        Get asset balance
        """    
        try:
            balance = client.get_asset_balance(asset=asset)
            return float(balance['free'])
        except BinanceRequestException as e:
            logger.error('BinanceRequestException; {} {}'.format(
                e.config_code,
                e.message
            ))
        except BinanceAPIException as e:
            logger.error('BinanceAPIException; {} {}'.format(
                e.config_code,
                e.message
            ))
        except requests.exceptions.Timeout:
            logger.error('Request timeout')
        except Exception as e:
            crash_stack(e)
        return 0

with open('config/binance.json', 'r') as json_file:
    config = json.load(json_file)
