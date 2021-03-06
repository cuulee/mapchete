================================
How to create a Mapchete process
================================

A Mapchete process has two parts. First, the process itself has to be
implemented by creating a file with a ``MapcheteProcess`` class. This class
requires besides some initial properties an ``execute()`` function, where you
can define what shall happen with your data.

Second, a Mapchete process requires a configuration where all the necessary
information is collected such as the location to your process Python file, the
output location and format, and any user-defined parameters desired. This
configuration file has a YAML syntax and has to have a ``.mapchete`` file
extension.

If you have both ready, you can point either ``mapchete serve`` or ``mapchete
execute`` to your process configuration (``.mapchete``) file to either view your
process output in a browser or batch process a larger area.

.. code-block:: shell

    mapchete serve my_process.mapchete

Starts a local web server on port 5000 with a simple OpenLayers interface.

.. code-block:: shell

    mapchete execute my_process.mapchete --zoom 5 10

Executes your process on zoom level 5 to 10.

To access the process parameters, use the dictionary stored in ``self.params``.
To read and write data, use the ``self.open(input_file)`` and
``self.write(array)`` functions.


---------
Reference
---------


Open and read data
==================

.. code-block:: python

    self.open(input_file, resampling="nearest")

* ``input_file``: Input file from ``self.params``. Can be a raster or vector
  file or the configuration file from another Mapchete process.
* ``resampling``: Resampling method to be used when reading the data.

Opens a reader object, depending on the data source (raster, vector, Mapchete
process). This object offers following functions:


The data reader object
----------------------

.. code-block:: python

    .is_empty(indexes=None)

* ``indexes``: A list of bands, a single band index or ``None`` to check all
  bands.

Returns ``bool`` indicating whether data within this tile is available or not.

.. code-block:: python

    .read(indexes=None)

* ``indexes``: A list of bands, a single band index or ``None`` to read all
  bands.

For raster files it either returns a ``generator`` of masked ``numpy arrays``
for multiple bands, or a masked ``numpy array`` of reprojected and resampled
data fitting to the current tile.

For vector files it returns a ``generator`` of ``GeoJSON``-like geometry and
attribute data intersecting with and clipped to current tile boundaries.

If reading a Mapchete file, either vector or raster data in the form described
above is returned.


Modify data
===========

After reading the data you can do whatever you want. For vector data, shapely_
provides a rich selection of functions to deal with geometries, for raster data,
NumPy_, SciPy_ or Pillow_ are excellent packages for image processing and other
desired tasks.

Mapchete also comes with some [common purpose functions](common_functions.md)
which allow clipping, calculating a hillshade or extract contour lines from an
elevation model.

.. _shapely: https://github.com/Toblerity/Shapely
.. _NumPy: http://www.numpy.org/
.. _SciPy: http://scipy.org/
.. _Pillow: http://pillow.readthedocs.io/en/3.3.x/


Write data
==========

.. code-block:: python

    self.write(output_data)

* ``output_data``: For raster data either a single or a * ``tuple`` of
  ``numpy array(s)``. For vector data, a ``GeoJSON``-like ``iterator`` of
  properties-geometry pairs. The write options are specified in the process
  configuration.


-------
Example
-------

The process file should look like this:

.. code-block:: python

    #!/usr/bin/env python

    from mapchete import MapcheteProcess

    class Process(MapcheteProcess):
        """Main process class."""

        def __init__(self, **kwargs):
            """Process initialization."""

            # init process
            MapcheteProcess.__init__(self, **kwargs)
            self.identifier = "my_process_id",
            self.title="My long process title",
            self.version = "0.1",
            self.abstract="short description on what my process does"

        def execute(self):
            """User defined process."""

            # Reading and writing data works like this:
            with self.open(
                self.params["input_files"]["raster_file"],
                resampling="bilinear"
                ) as my_raster_rgb_file:
                if my_raster_rgb_file.is_empty():
                    return "empty" # this assures a transparent tile instead of a
                    # pink error tile is returned when using mapchete_serve
                r, g, b = my_raster_rgb_file.read()

            self.write((r, g, b))
