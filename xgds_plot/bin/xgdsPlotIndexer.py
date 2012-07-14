#!/usr/bin/env python

import time
import datetime
import os
import sys
import atexit

from zmq.eventloop import ioloop
ioloop.install()

from geocamUtil.zmq.subscriber import ZmqSubscriber
from geocamUtil.zmq.util import zmqLoop, getTimestampFields

from xgds_plot import settings
from xgds_plot.meta import TIME_SERIES
from xgds_plot.segmentIndex import SegmentIndex


class XgdsPlotIndexer(object):
    def __init__(self, opts):
        self.opts = opts
        self.subscriber = ZmqSubscriber(**ZmqSubscriber.getOptionValues(self.opts))
        self.indexes = {}
        for meta in TIME_SERIES:
            index = SegmentIndex(meta, self.subscriber)
            self.indexes[meta['valueCode']] = index

    def start(self):
        self.subscriber.start()
        for index in self.indexes.itervalues():
            print
            print '###################################################'
            print '# initializing time series:', index.valueCode
            print '###################################################'
            index.start()

    def stop(self):
        for index in self.indexes.itervalues():
            index.stop()

    def clean(self):
        for index in self.indexes.itervalues():
            index.clean()

def main():
    import optparse
    parser = optparse.OptionParser('usage: %prog')
    ZmqSubscriber.addOptions(parser, 'xgdsPlotIndexer')
    parser.add_option('-c', '--clean',
                      action='store_true', default=False,
                      help='Delete indexes and start from scratch')
    parser.add_option('-q', '--quit',
                      action='store_true', default=False,
                      help='Quit after initial indexing is complete')
    opts, args = parser.parse_args()
    if args:
        parser.error('expected no arguments')

    x = XgdsPlotIndexer(opts)
    if opts.clean:
        x.clean()
    x.start()
    if opts.quit:
        x.stop()
    else:
        atexit.register(x.stop)
        zmqLoop()

if __name__ == '__main__':
    main()
