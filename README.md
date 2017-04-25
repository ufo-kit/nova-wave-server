# ufo-wave-server

The ufo-wave-server is a server that generates slice maps from raw data for
consumption with the WAVE JavaScript client renderer and uses the UFO framework
to do the low-level image processing.

The client has to

1. POST a request to `/maps` with a JSON body describing the bounding box and
   output parameters.
2. Follow the location header to a `/queue/<id>` URL as a result of the
   successful POST request.
3. GET the `/queue/<id>` resource if slice map generation is finished
   or still going on.
4. Follow the location header `/queue/<id>` to `/maps/<id>` containing the slice
   map

See the `test.py` script for an example.


## General parameters

All parameters to the POST request have to be JSON encoded and send within a
single JSON object.

* In order to resolve the path to the actual slices we have to authenticate
  against the NOVA REST API server, for this the user's `token` must be
  specified.
* `dataset` is in the form of `collection/dataset` and specifies the path to a
  directory containing the raw full-resolution slices in a subdirectory called
  `slices`.
* The `origin` array containing three float numbers with values between 0 and 1
  specify the *relative* coordinates of the origin of the bounding box. If the
  array is not given, all coordinates are assumed to be zero.
* The `dimensions` array containing two float numbers with values between 0 and
  1 specifies the *relative* width and height of the selected bounding box.
* `size` specifies output size of a single slice within the slice map. If not
  given, a default of 256 pixels is used.
* `subset` specifies the nth slice map, i.e. subset 0 contains the first 64
  slices, 1 the slices 65 to 128 and so on.


## Response

The result is either a JPEG of size 8 × `size` containing the slice map or a
JSON response containing an error message field.
