#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
requests
python-telegram-bot
pillow
qrcode
gTTS
"""
from __future__ import print_function
import time, requests, json, re
import logging
import configparser
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
import telegram
import json
from gtts import gTTS
import qrcode
import math


class RPCHost(object):
    def __init__(self, url):
        self._session = requests.Session()
        if re.match(r'.*\.onion/*.*', url):
            self._session.proxies = {}
            self._session.proxies['http'] = 'socks5h://localhost:9050'
            self._session.proxies['https'] = 'socks5h://localhost:9050'
        self._url = url
        self._headers = {'content-type': 'application/json'}

    def call(self, rpcMethod, *params):
        payload = json.dumps({"method": rpcMethod, "params": list(params), "jsonrpc": "2.0"})
        tries = 5
        hadConnectionFailures = False
        while True:
            try:
                response = self._session.post(self._url, headers=self._headers, data=payload)
            except requests.exceptions.ConnectionError:
                tries -= 1
                if tries == 0:
                    raise Exception('Failed to connect for remote procedure call.')
                hadFailedConnections = True
                logger.warning("Couldn't connect for remote procedure call, will sleep for five seconds and then try again ({} more tries)".format(tries))
                time.sleep(10)
            else:
                if hadConnectionFailures:
                    logger.warning('Connected for remote procedure call after retry.')
                break
        if not response.status_code in (200, 500):
            raise Exception('RPC connection failure: ' + str(response.status_code) + ' ' + response.reason)
        responseJSON = response.json()
        if 'error' in responseJSON and responseJSON['error'] != None:
            raise Exception('Error in RPC call: ' + str(responseJSON['error']))
        return responseJSON['result']


logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

config = configparser.RawConfigParser()
config.read('telebtc.conf')
token = config.get('TELEGRAM', 'token')
chain = config.get('TELEGRAM', 'chain')
rpcHost = config.get(chain, 'host')
rpcPort = config.get(chain, 'port')
rpcUser = config.get(chain, 'username')
rpcPassword = config.get(chain, 'password')
rpcWallet = config.get(chain, 'wallet')
rpcPassphrase = config.get(chain, 'passphrase')
serverURL = 'http://' + rpcUser + ':' + rpcPassword + '@'+rpcHost+':' + str(rpcPort)+'/wallet/' + rpcWallet


def send_msg(update, message):
    for i in range(0, math.ceil(len(message)/telegram.constants.MAX_MESSAGE_LENGTH)):
        update.message.reply_text(message[i*telegram.constants.MAX_MESSAGE_LENGTH : (i+1)*telegram.constants.MAX_MESSAGE_LENGTH-1])


def start(update, context):
    """Send a message when the command /start is issued."""
    filename = "START_"+str(update.message.chat.id)+"_"+str(update.message.message_id)
    message = 'TeleBTC is a bot able to show you information about ' + chain + '\n' \
        'TeleBTC is open source: https://github.com/valerio-vaccaro/TeleBTC'
    send_msg(update, message)


def help(update, context):
    """Send a message when the command /help is issued."""
    filename = "HELP_"+str(update.message.chat.id)+"_"+str(update.message.message_id)
    message = 'TeleBTC is a bot able to show you information about ' + chain + '\n' \
        '/block <id> - return information about last block or a specified one (id can be heigh or blockhash).' + '\n' \
        '/tx <id> - if <id> is a txid return information about the transaction (+txoutproof), if <id> is a transaction in hex perform textmempoolaccept and try to broadcast it.' + '\n' \
        '/mempool - return stastistics about mempool' + '\n' \
        '/fee - return fee for 6, 18, 72, 144 blocks (remember to use 1 sat/vbyte and RBF if possible)' + '\n' \
        '/tip - if you want give me a tip call this handler! :)' + '\n' \
        'TeleBTC is open source: https://github.com/valerio-vaccaro/TeleBTC'
    send_msg(update, message)

def mempool(update, context):
    """Send a message when the command /mempool is issued."""
    host = RPCHost(serverURL)
    if (len(rpcPassphrase) > 0):
        result = host.call('walletpassphrase', rpcPassphrase, 60)
    filename = "TIP_"+str(update.message.chat.id)+"_"+str(update.message.message_id)
    mempoolinfo = host.call('getmempoolinfo')
    message = 'Mempool contains '+str(mempoolinfo['size'])+' transactions using '+str(round(mempoolinfo['bytes']/1000, 3))+' kBytes ['+str(round(mempoolinfo['bytes']/mempoolinfo['size']/1000, 3))+' kBytes per transaction on average]'
    send_msg(update, message)

def fee(update, context):
    """Send a message when the command /fee is issued."""
    host = RPCHost(serverURL)
    if (len(rpcPassphrase) > 0):
        result = host.call('walletpassphrase', rpcPassphrase, 60)
    filename = "TIP_"+str(update.message.chat.id)+"_"+str(update.message.message_id)
    fee_6 = host.call('estimatesmartfee', 6)['feerate']
    fee_18 = host.call('estimatesmartfee', 18)['feerate']
    fee_72 = host.call('estimatesmartfee', 72)['feerate']
    fee_144 = host.call('estimatesmartfee', 144)['feerate']

    message = '1 hour (6 blocks) '+str(round(fee_6*10**8, 1))+' sat/vkbyte' + '\n' \
        '3 hours (18 blocks) '+str(round(fee_18*10**8, 1))+' sat/vkbyte' + '\n' \
        '12 hours (72 blocks) '+str(round(fee_72*10**8, 1))+' sat/vkbyte' + '\n' \
        '1 day (144 blocks) '+str(round(fee_144*10**8, 1))+' sat/vkbyte' + '\n' \
        'You can always use '+str(round(0.00001000*10**8, 1))+' sat/vkbyte and RBF flag!'
    send_msg(update, message)


def tx(update, context):
    """Send a message when the command /tx is issued."""
    host = RPCHost(serverURL)
    if (len(rpcPassphrase) > 0):
        result = host.call('walletpassphrase', rpcPassphrase, 60)
    filename = "TX_"+str(update.message.chat.id)+"_"+str(update.message.message_id)
    if len(context.args) > 0:
        subcommand = context.args[0]
    else:
        subcommand = None

    if subcommand == None:
        messgae = 'missing argument'
        send_msg(update, message)
    elif len(subcommand) == 64:
        txid = subcommand
        transaction = host.call('getrawtransaction', txid, 1)
        message = json.dumps(transaction, indent=4)
        send_msg(update, message)
        txoutproof = {'txoutproof' : host.call('gettxoutproof', [txid])}
        message = json.dumps(txoutproof, indent=4)
        send_msg(update, message)
    else:
        tx = subcommand
        test = host.call('testmempoolaccept', [tx], 1)
        message = json.dumps(test, indent=4)
        send_msg(update, message)
        if test[0]['allowed']:
            txid = host.call('sendrawtransaction', tx)
            message = txid
            send_msg(update, message)


def block(update, context):
    """Send a message when the command /block is issued."""
    host = RPCHost(serverURL)
    if (len(rpcPassphrase) > 0):
        result = host.call('walletpassphrase', rpcPassphrase, 60)
    filename = "BLOCK_"+str(update.message.chat.id)+"_"+str(update.message.message_id)
    if len(context.args) > 0:
        subcommand = context.args[0]
    else:
        subcommand = None

    if subcommand == None:
        hash = host.call('getbestblockhash')
        block = host.call('getblockheader', hash)
        #tts = gTTS(hash, slow=True)
        #tts.save('./messages/'+filename+'.ogg')
        #update.message.reply_voice(voice=open('./messages/'+filename+'.ogg', 'rb'))
    elif len(subcommand) == 64:
        hash = subcommand
        block = host.call('getblockheader', hash)
    else:
        height = subcommand
        hash = host.call('getblockhash', int(height))
        block = host.call('getblockheader', hash)

    message = 'hash: '+ block['hash']+'\n'+ \
              'height: '+str(block['height'])+' - confirmations: '+str(block['confirmations'])+'\n'+ \
              'merkleroot: '+block['merkleroot']+'\n'+ \
              'time: '+str(block['time'])+' - mediantime: '+str(block['mediantime'])+'\n'+ \
              'nonce: '+str(block['version'])+'\n'
    if chain == 'bitcoin':
        message = message + 'bits: '+str(block['bits'])+' - difficulty: '+str(block['difficulty'])+'\n'+ \
                  'chainwork: '+str(block['chainwork'])+'\n'
    message = message + 'nTx: '+str(block['nTx'])

    if 'previousblockhash' in block:
        message = message+'\n'+'previousblockhash: '+str(block['previousblockhash'])

    if 'nextblockhash' in block:
        message = message+'\n'+'nextblockhash: '+str(block['nextblockhash'])
    send_msg(update, message)


def tip(update, context):
    """Send a message when the command /tip is issued."""
    host = RPCHost(serverURL)
    if (len(rpcPassphrase) > 0):
        result = host.call('walletpassphrase', rpcPassphrase, 60)
    filename = "TIP_"+str(update.message.chat.id)+"_"+str(update.message.message_id)

    address = host.call('getnewaddress')
    if chain == 'bitcoin':
        message = 'Send me some BTC at address: ' + address
    if chain == 'liquid':
        message = 'Send me some L-BTC at confidential address: ' + address
    send_msg(update, message)

    img = qrcode.make(chain + ':' + address)
    img.save('./messages/'+filename+'.png')
    update.message.reply_photo(photo=open('./messages/'+filename+'.png', 'rb'))


def error(update, context):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, context.error)


def main():
    updater = Updater(token, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help))
    dp.add_handler(CommandHandler("mempool", mempool))
    dp.add_handler(CommandHandler("fee", fee))
    dp.add_handler(CommandHandler("tx", tx))
    dp.add_handler(CommandHandler("block", block))
    dp.add_handler(CommandHandler("tip", tip))
    dp.add_error_handler(error)
    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
