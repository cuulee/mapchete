#!/usr/bin/env python

import os
import sys
import argparse
from flask import Flask, send_file, make_response
from functools import update_wrapper
import threading
from PIL import Image
import io
import traceback
import logging
import logging.config

from mapchete import *
from tilematrix import TilePyramid, MetaTilePyramid

import pkgutil

logger = logging.getLogger("mapchete")

def main(args=None):

    if args is None:
        args = sys.argv[1:]

    parser = argparse.ArgumentParser()
    parser.add_argument("mapchete_file", type=str)
    parser.add_argument("--port", "-p", type=int, default=5000)
    parser.add_argument("--zoom", "-z", type=int, nargs='*', )
    parser.add_argument("--bounds", "-b", type=float, nargs='*')
    parser.add_argument("--log", action="store_true")
    parsed = parser.parse_args(args)

    logging.config.dictConfig(get_log_config(parsed.mapchete_file))

    try:
        logger.info("preparing process ...")
        mapchete = Mapchete(
            MapcheteConfig(
                parsed.mapchete_file,
                zoom=parsed.zoom,
                bounds=parsed.bounds
            )
        )
    except Exception as e:
        raise

    app = Flask(__name__)


    metatile_cache = {}
    metatile_lock = threading.Lock()

    @app.route('/', methods=['GET'])
    def get_tasks():
        index_html = pkgutil.get_data('static', 'index.html')
        return index_html

    tile_base_url = '/wmts_simple/1.0.0/mapchete/default/WGS84/'
    @app.route(
        tile_base_url+'<int:zoom>/<int:row>/<int:col>.png',
        methods=['GET']
        )
    def get(zoom, row, col):
        tile = mapchete.tile_pyramid.tilepyramid.tile(zoom, row, col)
        try:
            metatile = mapchete.tile_pyramid.tiles_from_bbox(
                tile.bbox(),
                tile.zoom
                ).next()
            with metatile_lock:
                metatile_event = metatile_cache.get(metatile.id)
                if not metatile_event:
                    metatile_cache[metatile.id] = threading.Event()

            if metatile_event:
                logger.info("%s waiting for metatile %s" %(
                    tile.id,
                    metatile.id
                    ))
                metatile_event.wait()
            else:
                logger.info("%s getting metatile %s" % (
                    tile.id,
                    metatile.id
                    ))

            try:
                image = mapchete.get(tile)
            except:
                raise
            finally:
                if not metatile_event:
                    with metatile_lock:
                        metatile_event = metatile_cache.get(metatile.id)
                        del metatile_cache[metatile.id]
                        metatile_event.set()

            if image:
                resp = make_response(image)
                # set no-cache header:
                resp.cache_control.no_cache = True
                logger.info((tile.id, "ok", "image sent"))
                return resp
            else:
                raise IOError("no image returned")

        except Exception as e:
            error_msg = (tile.id, "failed", e)
            logger.error(error_msg)
            size = mapchete.tile_pyramid.tilepyramid.tile_size
            empty_image = Image.new('RGBA', (size, size))
            pixels = empty_image.load()
            for y in xrange(size):
                for x in xrange(size):
                    pixels[x, y] = (255, 0, 0, 128)
            out_img = io.BytesIO()
            empty_image.save(out_img, 'PNG')
            out_img.seek(0)
            return send_file(out_img, mimetype='image/png')

    app.run(threaded=True, debug=True, port=parsed.port)


if __name__ == '__main__':
    main()
