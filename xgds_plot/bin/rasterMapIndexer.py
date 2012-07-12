#!/usr/bin/env python
# __BEGIN_LICENSE__
# Copyright (C) 2008-2010 United States Government as represented by
# the Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
# __END_LICENSE__

import logging
import atexit

from zmq.eventloop import ioloop
ioloop.install()

from geocamUtil.zmq.util import zmqLoop
from geocamUtil.zmq.subscriber import ZmqSubscriber

from xgds_plot.nsRasterMap import NsListener


def main():
    import optparse
    parser = optparse.OptionParser('usage: %prog')
    ZmqSubscriber.addOptions(parser, 'neutronSpectrometerListener')
    parser.add_option('-c', '--clean',
                      action='store_true', default=False,
                      help='Clean out old raster map data at startup')
    opts, args = parser.parse_args()
    if args:
        parser.error('expected no args')
    logging.basicConfig(level=logging.INFO)

    if opts.clean:
        print 'cleaning out old raster map data'
        NsListener.clean()

    ns = NsListener(['snCdRatio',
                     'snScalar',
                     ],
                    opts)
    ns.start()
    atexit.register(ns.stop)
    zmqLoop()

if __name__ == '__main__':
    main()
