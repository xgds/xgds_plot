#!/usr/bin/env python
# __BEGIN_LICENSE__
# Copyright (C) 2008-2010 United States Government as represented by
# the Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
# __END_LICENSE__

import os
import logging
import atexit

from zmq.eventloop import ioloop
ioloop.install()

from geocamUtil.zmq.util import zmqLoop
from geocamUtil.zmq.subscriber import ZmqSubscriber
from geocamUtil.store import FileStore, LruCacheStore
from geocamUtil.zmq.delayBox import DelayBox

from xgds_plot.tileIndex import TileIndex
from xgds_plot import settings, meta, plotUtil

DATA_PATH = os.path.join(settings.DATA_DIR,
                         settings.XGDS_PLOT_DATA_SUBDIR,
                         'map')

MAX_TILES_IN_MEMORY = 100

class RasterMapIndexer(object):
    def __init__(self, opts):
        self.opts = opts
        self.subscriber = ZmqSubscriber(**ZmqSubscriber.getOptionValues(self.opts))
        self.cacheDir = os.path.join(DATA_PATH, 'cache')
        self.store = None
        self.delayBox = DelayBox(self.writeOutputTile,
                                 maxDelaySeconds=1,
                                 numBuckets=10)
        self.indexes = {}
        for m in meta.TIME_SERIES:
            if 'map' in m:
                index = TileIndex(m, self)
                self.indexes[m['valueCode']] = index

    def writeOutputTile(self, info):
        indexName, tileParams = info
        self.indexes[indexName].writeOutputTile(tileParams)

    def start(self):
        self.store = LruCacheStore(FileStore(self.cacheDir),
                                   MAX_TILES_IN_MEMORY)
        self.delayBox.start()
        self.subscriber.start()
        for index in self.indexes.itervalues():
            print
            print '###################################################'
            print '# initializing map index:', index.valueCode
            print '###################################################'
            index.start()

    def stop(self):
        self.store.sync()
        self.delayBox.stop()
        for index in self.indexes.itervalues():
            index.stop()

    def clean(self):
        plotUtil.rmIfPossible(self.cacheDir)
        for index in self.indexes.itervalues():
            index.clean()


def main():
    import optparse
    parser = optparse.OptionParser('usage: %prog')
    ZmqSubscriber.addOptions(parser, 'rasterMapIndexer')
    parser.add_option('-c', '--clean',
                      action='store_true', default=False,
                      help='Clean out old raster map data at startup')
    parser.add_option('-q', '--quit',
                      action='store_true', default=False,
                      help='Quit after initial indexing is complete')
    opts, args = parser.parse_args()
    if args:
        parser.error('expected no args')
    logging.basicConfig(level=logging.INFO)

    rmi = RasterMapIndexer(opts)
    if opts.clean:
        rmi.clean()
    rmi.start()
    if opts.quit:
        rmi.stop()
    else:
        atexit.register(rmi.stop)
        zmqLoop()

if __name__ == '__main__':
    main()
