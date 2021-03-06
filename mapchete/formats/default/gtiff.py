"""
Handles writing process output into a pyramid of GeoTIFF files.

output configuration parameters
-------------------------------

mandatory
~~~~~~~~~

bands: integer
    number of output bands to be written
path: string
    output directory
dtype: string
    numpy datatype

optional
~~~~~~~~

tiled: bool
    internal TIFF tiling (default: True)
blockxsize: integer
    internal tile width (default: 256)
blockysize:
    internal tile height (default: 256)
nodata: integer or float
    nodata value used for writing
compress: string
    compression method (default: lzw): lzw, jpeg, packbits, deflate, CCITTRLE,
    CCITTFAX3, CCITTFAX4, lzma
"""

import os
import numpy as np
import numpy.ma as ma
import rasterio

from mapchete.formats import base
from mapchete.tile import BufferedTile
from mapchete.io.raster import write_raster_window


class OutputData(base.OutputData):
    """
    Template class handling process output data.

    Parameters
    ----------
    output_params : dictionary
        output parameters from Mapchete file

    Attributes
    ----------
    path : string
        path to output directory
    file_extension : string
        file extension for output files (.tif)
    output_params : dictionary
        output parameters from Mapchete file
    nodata : integer or float
        nodata value used when writing GeoTIFFs
    pixelbuffer : integer
        buffer around output tiles
    pyramid : ``tilematrix.TilePyramid``
        output ``TilePyramid``
    crs : ``rasterio.crs.CRS``
        object describing the process coordinate reference system
    srid : string
        spatial reference ID of CRS (e.g. "{'init': 'epsg:4326'}")
    """

    METADATA = {
        "driver_name": "GTiff",
        "data_type": "raster",
        "mode": "rw"
    }

    def __init__(self, output_params):
        """Initialize."""
        super(OutputData, self).__init__(output_params)
        self.path = output_params["path"]
        self.file_extension = ".tif"
        self.output_params = output_params
        try:
            self.nodata = output_params["nodata"]
        except KeyError:
            self.nodata = GTIFF_PROFILE["nodata"]

    def read(self, output_tile):
        """
        Read existing process output.

        Parameters
        ----------
        output_tile : ``BufferedTile``
            must be member of output ``TilePyramid``

        Returns
        -------
        process output : array
        """
        if self.tiles_exist(output_tile):
            with rasterio.open(self.get_path(output_tile), "r") as src:
                output_tile.data = src.read(masked=True)
        else:
            output_tile.data = self.empty(output_tile)
        return output_tile

    def write(self, process_tile):
        """
        Write data from process tiles into GeoTIFF file(s).

        Parameters
        ----------
        process_tile : ``BufferedTile``
            must be member of process ``TilePyramid``
        """
        if not os.path.exists(self.path):
            os.makedirs(self.path)
        self.verify_data(process_tile)
        process_tile.data = self.prepare_data(
            process_tile.data, self.profile(process_tile))
        # Convert from process_tile to output_tiles
        for tile in self.pyramid.intersecting(process_tile):
            # skip if file exists and overwrite is not set
            out_path = self.get_path(tile)
            self.prepare_path(tile)
            out_tile = BufferedTile(tile, self.pixelbuffer)
            # write_from_tile(buffered_tile, profile, out_tile, out_path)
            write_raster_window(
                in_tile=process_tile, out_profile=self.profile(out_tile),
                out_tile=out_tile, out_path=out_path)

    def tiles_exist(self, process_tile):
        """
        Check whether all output tiles of a process tile exist.

        Parameters
        ----------
        process_tile : ``BufferedTile``
            must be member of process ``TilePyramid``

        Returns
        -------
        exists : bool
        """
        return all(
            os.path.exists(self.get_path(tile))
            for tile in self.pyramid.intersecting(process_tile)
        )

    def is_valid_with_config(self, config):
        """
        Check if output format is valid with other process parameters.

        Parameters
        ----------
        config : dictionary
            output configuration parameters

        Returns
        -------
        is_valid : bool
        """
        assert isinstance(config, dict)
        assert "bands" in config
        assert isinstance(config["bands"], int)
        assert "path" in config
        assert isinstance(config["path"], str)
        assert "dtype" in config
        assert isinstance(config["dtype"], str)
        return True

    def get_path(self, tile):
        """
        Determine target file path.

        Parameters
        ----------
        tile : ``BufferedTile``
            must be member of output ``TilePyramid``

        Returns
        -------
        path : string
        """
        zoomdir = os.path.join(self.path, str(tile.zoom))
        rowdir = os.path.join(zoomdir, str(tile.row))
        return os.path.join(rowdir, str(tile.col) + self.file_extension)

    def prepare_path(self, tile):
        """
        Create directory and subdirectory if necessary.

        Parameters
        ----------
        tile : ``BufferedTile``
            must be member of output ``TilePyramid``
        """
        zoomdir = os.path.join(self.path, str(tile.zoom))
        if not os.path.exists(zoomdir):
            os.makedirs(zoomdir)
        rowdir = os.path.join(zoomdir, str(tile.row))
        if not os.path.exists(rowdir):
            os.makedirs(rowdir)

    def profile(self, tile):
        """
        Create a metadata dictionary for rasterio.

        Parameters
        ----------
        tile : ``BufferedTile``

        Returns
        -------
        metadata : dictionary
            output profile dictionary used for rasterio.
        """
        dst_metadata = GTIFF_PROFILE
        dst_metadata.pop("transform", None)
        dst_metadata.update(
            crs=tile.crs, width=tile.width, height=tile.height,
            affine=tile.affine, driver="GTiff",
            count=self.output_params["bands"],
            dtype=self.output_params["dtype"]
        )
        try:
            dst_metadata.update(compress=self.output_params["compression"])
        except KeyError:
            pass
        return dst_metadata

    def verify_data(self, tile):
        """
        Verify array data and move array into tuple if necessary.

        Parameters
        ----------
        tile : ``BufferedTile``

        Returns
        -------
        valid : bool
        """
        try:
            assert isinstance(
                tile.data, (np.ndarray, ma.MaskedArray, tuple, list))
        except AssertionError:
            raise ValueError(
                "process output must be 2D NumPy array, masked array or a tuple"
                )
        try:
            if isinstance(tile.data, (tuple, list)):
                for band in tile.data:
                    assert band.ndim == 2
            else:
                assert tile.data.ndim in [2, 3]
        except AssertionError:
            raise ValueError(
                "each output band must be a 2D NumPy array")

    def prepare_data(self, data, profile):
        """
        Convert data into correct output.

        Parameters
        ----------
        data : array
        profile : dictionary

        Returns
        -------
        prepared_data : array
            a 3D masked NumPy array including all bands with the data type
            specified in the configuration
        """
        if isinstance(data, (list, tuple)):
            out_data = ()
            out_mask = ()
            for band in data:
                if isinstance(band, ma.MaskedArray):
                    try:
                        assert band.shape == band.mask.shape
                        out_data += (band, )
                        out_mask += (band.mask, )
                    except:
                        out_data += (band.data, )
                        out_mask += (
                            np.where(band.data == self.nodata, True, False), )
                elif isinstance(band, np.ndarray):
                    out_data += (band)
                    out_mask += (np.where(band == self.nodata, True, False))
                else:
                    raise ValueError("input data bands must be NumPy arrays")
            assert len(out_data) == len(out_mask)
            return ma.MaskedArray(
                data=np.stack(out_data).astype(profile["dtype"]),
                mask=np.stack(out_mask))
        elif isinstance(data, np.ndarray) and data.ndim == 2:
            data = ma.expand_dims(data, axis=0)
        if isinstance(data, ma.MaskedArray):
            try:
                assert data.shape == data.mask.shape
                return data.astype(profile["dtype"])
            except:
                return ma.MaskedArray(
                    data=data.astype(profile["dtype"]),
                    mask=np.where(band.data == self.nodata, True, False))
        elif isinstance(data, np.ndarray):
            return ma.MaskedArray(
                data=data.astype(profile["dtype"]),
                mask=np.where(data == self.nodata, True, False))

    def empty(self, process_tile):
        """
        Return empty data.

        Parameters
        ----------
        process_tile : ``BufferedTile``
            must be member of process ``TilePyramid``

        Returns
        -------
        empty data : array
            empty array with data type provided in output profile
        """
        profile = self.profile(process_tile)
        return ma.masked_array(
            data=np.full(
                (profile["count"], ) + process_tile.shape, profile["nodata"],
                dtype=profile["dtype"]),
            mask=True
        )

    def open(self, tile, process, **kwargs):
        """
        Open process output as input for other process.

        Parameters
        ----------
        tile : ``Tile``
        process : ``MapcheteProcess``
        kwargs : keyword arguments
        """
        try:
            resampling = kwargs["resampling"]
        except KeyError:
            resampling = None
        return InputTile(tile, process, resampling)


class InputTile(base.InputTile):
    """
    Target Tile representation of input data.

    Parameters
    ----------
    tile : ``Tile``
    process : ``MapcheteProcess``
    resampling : string
        rasterio resampling method

    Attributes
    ----------
    tile : ``Tile``
    process : ``MapcheteProcess``
    resampling : string
        rasterio resampling method
    pixelbuffer : integer
    """

    def __init__(self, tile, process, resampling):
        """Initialize."""
        self.tile = tile
        self.process = process
        self.pixelbuffer = None
        self.resampling = resampling
        self._np_cache = None

    def read(self, indexes=None):
        """
        Read reprojected & resampled input data.

        Parameters
        ----------
        indexes : integer or list
            band number or list of band numbers

        Returns
        -------
        data : array
        """
        band_indexes = self._get_band_indexes(indexes)
        if len(band_indexes) == 1:
            return self._from_cache(indexes=band_indexes).next()
        else:
            return self._from_cache(indexes=band_indexes)

    def is_empty(self, indexes=None):
        """
        Check if there is data within this tile.

        Returns
        -------
        is empty : bool
        """
        band_indexes = self._get_band_indexes(indexes)
        src_bbox = self.process.config.process_area()
        tile_geom = self.tile.bbox

        # empty if tile does not intersect with file bounding box
        if not tile_geom.intersects(src_bbox):
            return True

        # empty if source band(s) are empty
        all_bands_empty = True
        for band in self._from_cache(band_indexes):
            if not band.mask.all():
                all_bands_empty = False
                break
        return all_bands_empty

    def _get_band_indexes(self, indexes=None):
        """Return valid band indexes."""
        if indexes:
            if isinstance(indexes, list):
                return indexes
            else:
                return [indexes]
        else:
            return range(
                1, self.process.config.output.profile(self.tile)["count"] + 1)

    def _from_cache(self, indexes=None):
        """Cache reprojected source data for multiple usage."""
        for band_index in indexes:
            if self._np_cache is None:
                tile = self.process.get_raw_output(self.tile)
                self._np_cache = tile.data
            yield self._np_cache[band_index-1]

    def __enter__(self):
        """Enable context manager."""
        return self

    def __exit__(self, t, v, tb):
        """Clear cache on close."""
        del self._np_band_cache


GTIFF_PROFILE = {
    "blockysize": 256,
    "blockxsize": 256,
    "tiled": True,
    "dtype": "uint8",
    "compress": "lzw",
    "interleave": "band",
    "nodata": 0
}
