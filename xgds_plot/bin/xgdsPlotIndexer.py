#!/usr/bin/env python

import time
import datetime

from zmq.eventloop import ioloop
ioloop.install()

from geocamUtil.zmq.subscriber import ZmqSubscriber
from geocamUtil.zmq.util import zmqLoop, getTimestampFields
from geocamUtil import anyjson as json

from isruApp import settings


class XgdsPlotIndexer(object):
    def __init__(self, opts):
        self.opts = opts
        self.subscriber = ZmqSubscriber(**ZmqSubscriber.getOptionValues(self.opts))

    def start(self):
        self.subscriber.start()
        #self.subscriber.subscribeJson(topic, self.handler)


def main():
    import optparse
    parser = optparse.OptionParser('usage: %prog')
    ZmqSubscriber.addOptions(parser, 'xgdsPlotIndexer')
    opts, args = parser.parse_args()
    if args:
        parser.error('expected no arguments')

    x = XgdsPlotIndexer(opts)
    x.start()
    zmqLoop()

if __name__ == '__main__':
    main()
