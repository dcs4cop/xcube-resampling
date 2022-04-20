# The MIT License (MIT)
# Copyright (c) 2022 by the xcube development team and contributors
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.

import unittest
import pyproj
import numpy as np
import dask.array as da
from xcube_resampling.grid import Grid
from xcube_resampling.rectifier import Rectifier

# noinspection PyTypeChecker
class RectificationTest(unittest.TestCase):

    @classmethod
    def setUpClass(self) -> None:
        #self._client = Client(LocalCluster(n_workers=8, processes=True))
        #self._client = Client(n_workers=1, threads_per_worker=6)
        self.src_lat = da.from_array([[53.98, 53.94, 53.90],
                                 [53.88, 53.84, 53.80],
                                 [53.78, 53.74, 53.70],
                                 [53.68, 53.64, 53.60]], chunks=((3,1),(2,1)))
        self.src_lon = da.from_array([[10.35, 10.50, 10.65],
                                 [10.25, 10.40, 10.55],
                                 [10.15, 10.30, 10.45],
                                 [10.05, 10.20, 10.35]], chunks=((3,1),(2,1)))
        self.dst_grid = Grid(pyproj.CRS(4326), (10.0, 54.0), (0.2, -0.125), (3, 3), (2, 2))

    @classmethod
    def tearDownClass(self) -> None:
        #self._client.close()
        pass

    def test_dst_pixels_of_src_block(self):
        src_lat = self.src_lat.blocks[1, 0]
        src_lon = self.src_lon.blocks[1, 0]
        trafo = pyproj.Transformer.from_crs(pyproj.CRS(4326),
                                            self.dst_grid.crs,
                                            always_xy=True)
        block_result = Rectifier.block_dst_pixels_of_src_block(src_lon, src_lat, trafo=trafo, dst_grid=self.dst_grid)
        assert np.array_equal(block_result,
                              [[[0, 0]], [[2, 2]]])
        print(block_result)

    def test_forward_pixel_index(self):
        r = Rectifier(self.src_lon, self.src_lat, self.dst_grid)
        index = r.create_forward_pixel_index()
        result = index.compute()
        assert np.array_equal(result,
                              [[[1, 2, 3], [1, 2, 2], [0, 1, 2], [0, 0, 1]],
                               [[0, 0, 0], [0, 1, 1], [1, 2, 2], [2, 2, 3]]])
        print(index)
        print("i", result[0])
        print("j", result[1])

    def test_bbox_block(self):
        r = Rectifier(self.src_lon, self.src_lat, self.dst_grid)
        forward_index = r.create_forward_pixel_index().compute()
        print(forward_index[:,0:3,0:2])
        result = r.dst_bboxes_of_src_block(forward_index[:,0:3,0:2],
                                           self.dst_grid,
                                           (3, 2),
                                           (4, 3),
                                           (0, 0))
        result = result.reshape(result.shape[0:3])
        assert np.array_equal(result,
                              np.array([[[0, 1], [1, 3]],
                                        [[0, 0], [2, 4]],
                                        [[1, 2], [2, -1]],
                                        [[3, 2], [3, -1]]]))
        print(result.shape)
        print("min_x ", result[0])
        print("max_x ", result[2])
        print("min_y ", result[1])
        print("max_y ", result[3])

    def test_bbox_block2(self):
        r = Rectifier(self.src_lon, self.src_lat, self.dst_grid)
        forward_index = r.create_forward_pixel_index().compute()
        result = r.dst_bboxes_of_src_block(forward_index[:,0:3,2:3],
                                           self.dst_grid,
                                           (3, 2),
                                           (4, 3),
                                           (0, 1))
        result = result.reshape(result.shape[0:3])
        assert np.array_equal(result,
                              np.array([[[3, 2], [3, 2]],
                                        [[4, 1], [4, 2]],
                                        [[-1, 3], [-1, 3]],
                                        [[-1, 2], [-1, 3]]]))

    def test_bbox_blocks_raw(self):
        r = Rectifier(self.src_lon, self.src_lat, self.dst_grid)
        r.create_forward_pixel_index()
        bbox_blocks_raw = da.map_blocks(r.dst_bboxes_of_src_block,
                                        r.forward_index,
                                        dst_grid=r.dst_grid,
                                        src_tile_size=r.src_lat.chunksize,
                                        src_size=r.src_lat.shape,
                                        drop_axis=0,
                                        new_axis=[0,1,2],
                                        meta=np.array([], dtype=np.int32),
                                        name=r.name + "_bboxes")
        print()
        print(bbox_blocks_raw)
        bbox_blocks_raw = bbox_blocks_raw.compute()
        assert np.array_equal(bbox_blocks_raw[:,:,:,0,0],
                              np.array([[[0, 1], [1, 3]],
                                        [[0, 0], [2, 4]],
                                        [[1, 2], [2, -1]],
                                        [[3, 2], [3, -1]]]))
        assert np.array_equal(bbox_blocks_raw[:,:,:,0,1],
                              np.array([[[3, 2], [3, 2]],
                                        [[4, 1], [4, 2]],
                                        [[-1, 3], [-1, 3]],
                                        [[-1, 2], [-1, 3]]]))
        assert np.array_equal(bbox_blocks_raw[:,:,:,1,0],
                              np.array([[[3, 3], [0, 3]],
                                        [[4, 4], [3, 4]],
                                        [[-1, -1], [2, -1]],
                                        [[-1, -1], [4, -1]]]))
        assert np.array_equal(bbox_blocks_raw[:,:,:,1,1],
                              np.array([[[3, 3], [3, 3]],
                                        [[4, 4], [4, 4]],
                                        [[-1, -1], [-1, -1]],
                                        [[-1, -1], [-1, -1]]]))
        bbox_blocks = np.stack((np.min(bbox_blocks_raw[0], axis=(2,3)),
                                np.min(bbox_blocks_raw[1], axis=(2,3)),
                                np.max(bbox_blocks_raw[2], axis=(2,3)),
                                np.max(bbox_blocks_raw[3], axis=(2,3))))
        assert np.array_equal(bbox_blocks,
                              np.array([[[0, 1], [0, 2]],
                                        [[0, 0], [2, 2]],
                                        [[1, 3], [2, 3]],
                                        [[3, 2], [4, 3]]]))
        print(bbox_blocks)

    def test_inverse_index_of_dst_block_with_src_subset(self):
        r = Rectifier(self.src_lon, self.src_lat, self.dst_grid)
        r.create_forward_pixel_index()
        bbox_blocks_raw = da.map_blocks(r.dst_bboxes_of_src_block,
                                        r.forward_index,
                                        dst_grid=r.dst_grid,
                                        src_tile_size=r.src_lat.chunksize,
                                        src_size=r.src_lat.shape,
                                        drop_axis=0,
                                        new_axis=[0,1,2],
                                        meta=np.array([], dtype=np.int32),
                                        name=r.name + "_bboxes").compute()
        bbox_blocks = np.stack((np.min(bbox_blocks_raw[0], axis=(2,3)),
                                np.min(bbox_blocks_raw[1], axis=(2,3)),
                                np.max(bbox_blocks_raw[2], axis=(2,3)),
                                np.max(bbox_blocks_raw[3], axis=(2,3))))
        src_lon_lat = da.stack((self.src_lon, self.src_lat))
        # determine src box that covers dst block plus buffer
        tj = 0
        ti = 0
        src_offset_i = bbox_blocks[0, tj, ti]
        src_offset_j = bbox_blocks[1, tj, ti]
        src_subset_lon_lat = src_lon_lat[:,
                                         src_offset_j:bbox_blocks[3, tj, ti],
                                         src_offset_i:bbox_blocks[2, tj, ti]]
        src_subset_lon_lat = src_subset_lon_lat.compute()
        index = Rectifier.inverse_index_of_dst_block_with_src_subset(src_subset_lon_lat,
                                                                     (src_offset_i, src_offset_j),
                                                                     self.dst_grid,
                                                                     (ti, tj))
        print(index)




