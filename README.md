# ufo-wave-server

The ufo-wave-server is a server that generates slice maps from raw data for
consumption with the WAVE JavaScript client renderer and uses the UFO framework
to do the low-level image processing.

The client has to

1. POST a request to /maps with a JSON body describing the bounding box and
   output parameters.
2. The POST request returns a Location header to a /queue/<id> URL
3. The client asks the /queue/<id> resource if slice map generation is finished
   or still going on
4. If successful the /queue/<id> resource returns a Location header to
   /maps/<id> containing the slice map

See the `test.py` script for an example.


## General parameters

All parameters to the POST request have to be JSON encoded and send within a
single JSON object.

* `path` specifies the path to a directory containing the raw full-resolution slices.
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
