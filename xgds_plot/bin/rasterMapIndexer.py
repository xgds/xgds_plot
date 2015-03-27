#!/usr/bin/env python
# __BEGIN_LICENSE__
#Copyright © 2015, United States Government, as represented by the 
#Administrator of the National Aeronautics and Space Administration. 
#All rights reserved.
#
#The xGDS platform is licensed under the Apache License, Version 2.0 
#(the "License"); you may not use this file except in compliance with the License. 
#You may obtain a copy of the License at 
#http://www.apache.org/licenses/LICENSE-2.0.
#
#Unless required by applicable law or agreed to in writing, software distributed 
#under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR 
#CONDITIONS OF ANY KIND, either express or implied. See the License for the 
#specific language governing permissions and limitations under the License.
# __END_LICENSE__

import os
import sys
import logging
import atexit
import logging
import signal

from zmq.eventloop import ioloop
ioloop.install()

from geocamUtil.zmqUtil.util import zmqLoop
from geocamUtil.zmqUtil.subscriber import ZmqSubscriber
from geocamUtil.store import FileStore, LruCacheStore
from geocamUtil.zmqUtil.delayBox import DelayBox

from xgds_plot.tileIndex import TileIndex
from xgds_plot import settings, meta, plotUtil

DATA_PATH = os.path.join(settings.DATA_DIR,
                         settings.XGDS_PLOT_DATA_SUBDIR,
                         'map')

MAX_TILES_IN_MEMORY = 200


class RasterMapIndexer(object):
    def __init__(self, opts):
        self.opts = opts
        self.subscriber = ZmqSubscriber(**ZmqSubscriber.getOptionValues(self.opts))
        self.cacheDir = os.path.join(DATA_PATH, 'cache')
        self.store = None
        self.delayBox = DelayBox(self.writeOutputTile,
                                 maxDelaySeconds=5,
                                 numBuckets=10)

        if opts.timeSeries:
            timeSeriesList = opts.timeSeries.split(',')
            print 'indexing only the following time series:'
            for valueCode in timeSeriesList:
                print '  %s' % valueCode
            timeSeriesSet = set(opts.timeSeries.split(','))
        else:
            timeSeriesSet = None

        self.indexes = {}
        for m in meta.TIME_SERIES:
            if 'map' in m:
                if timeSeriesSet and m['valueCode'] not in timeSeriesSet:
                    continue
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
        logging.info('cleaning up indexer...')
        self.store.sync()
        self.delayBox.stop()
        for index in self.indexes.itervalues():
            index.stop()
        logging.info('  ... done')

    def clean(self):
        plotUtil.rmIfPossible(self.cacheDir)
        for index in self.indexes.itervalues():
            index.clean()


def main():
    import optparse
    parser = optparse.OptionParser('usage: %prog')
    ZmqSubscriber.addOptions(parser, 'rasterMapIndexer')
    parser.add_option('--timeSeries',
                      help='Specify a comma-separated subset of time series to index')
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

    # insure atexit handlers are called on receiving SIGINT or SIGTERM
    def sigHandler(signo, frame):
        logging.warn('caught signal %s, exiting', signo)
        sys.exit(0)
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, sigHandler)

    rmi = RasterMapIndexer(opts)
    if opts.clean:
        rmi.clean()
    rmi.start()
    atexit.register(rmi.stop)
    if not opts.quit:
        zmqLoop()

if __name__ == '__main__':
    main()
