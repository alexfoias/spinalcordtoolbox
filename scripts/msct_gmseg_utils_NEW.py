#!/usr/bin/env python
########################################################################################################################
#
#
# Utility functions used for the segmentation of the gray matter
#
# ----------------------------------------------------------------------------------------------------------------------
# Copyright (c) 2014 Polytechnique Montreal <www.neuro.polymtl.ca>
# Author: Sara Dupont
# Created: 2016-06-14
#
# About the license: see the file LICENSE.TXT
########################################################################################################################
from msct_image import Image
from sct_image import set_orientation, pad_image
from sct_resample import main as sct_resample_main
from sct_create_mask import main as sct_create_mask_main
from sct_utils import add_suffix, extract_fname, printv
from sct_maths import denoise_ornlm
import numpy as np
import os
import time
import random
import shutil

########################################################################################################################
#                                   CLASS SLICE
########################################################################################################################
class Slice:
    """
    Slice instance used in the model dictionary for the segmentation of the gray matter
    """
    def __init__(self, slice_id=None, im=None, gm_seg=None, wm_seg=None, reg_to_m=None, im_m=None, gm_seg_m=None, wm_seg_m=None, level=None):
        """
        Slice constructor
        :param slice_id: slice ID number, type: int
        :param im: original image (a T2star 2D image croped around the spinal cord), type: numpy array
        :param gm_seg: manual gray matter segmentation of the original image, type: list of numpy array
        :param wm_seg: manual white matter segmentation of the original image, type: list of numpy array
        :param reg_to_m: name of the file containing the transformation for this slice to go from the image original space to the model space, type: string
        :param im_m: image in the model space, type: numpy array
        :param gm_seg_m: manual gray matter segmentation in the model space, type: numpy array
        :param wm_seg_m: manual white matter segmentation in the model space, type: numpy array
        :param level: vertebral level of the slice, type: int
        """
        self.id = slice_id
        self.im = im
        self.gm_seg = gm_seg
        self.wm_seg = wm_seg
        self.reg_to_M = reg_to_m
        self.im_M = im_m
        self.gm_seg_M = gm_seg_m
        self.wm_seg_M = wm_seg_m
        self.level = level

    def set(self, slice_id=None, im=None, gm_seg=None, wm_seg=None, reg_to_m=None, im_m=None, gm_seg_m=None, wm_seg_m=None, level=None):
        """
        Slice setter, only the specified parameters are set
        :param slice_id: slice ID number, type: int
        :param im: original image (a T2star 2D image croped around the spinal cord), type: numpy array
        :param gm_seg: manual gray matter segmentation of the original image, type: list of numpy array
        :param wm_seg: manual white matter segmentation of the original image, type: list of numpy array
        :param reg_to_m: name of the file containing the transformation for this slice to go from the image original space to the model space, type: string
        :param im_m: image in the model space, type: numpy array
        :param gm_seg_m: manual gray matter segmentation in the model space, type: numpy array
        :param wm_seg_m: manual white matter segmentation in the model space, type: numpy array
        :param level: vertebral level of the slice, type: int
        """
        if slice_id is not None:
            self.id = slice_id
        if im is not None:
            self.im = im
        if gm_seg is not None:
            self.gm_seg = gm_seg
        if wm_seg is not None:
            self.wm_seg = wm_seg
        if reg_to_m is not None:
            self.reg_to_M = reg_to_m
        if im_m is not None:
            self.im_M = im_m
        if gm_seg_m is not None:
            self.gm_seg_M = gm_seg_m
        if wm_seg_m is not None:
            self.wm_seg_M = wm_seg_m
        if level is not None:
            self.level = level

    def __repr__(self):
        s = '\nSlice #' + str(self.id)
        if self.level is not None:
            s += 'Level : ' + str(self.level)
        s += '\nImage : \n' + str(self.im)
        s += '\nGray matter segmentation : \n' + str(self.gm_seg)
        s += '\nTransformation to model space : ' + str(self.reg_to_M)
        if self.im_M is not None:
            s += '\nImage in the common model space: \n' + str(self.im_M)
        if self.gm_seg_M is not None:
            s += '\nGray matter segmentation in the common model space: \n' + str(self.gm_seg_M)
        return s


########################################################################################################################
#                               FUNCTIONS USED FOR PRE-PROCESSING
########################################################################################################################
# ----------------------------------------------------------------------------------------------------------------------
def pre_processing(fname_target, fname_sc_seg, fname_level=None, fname_manual_gmseg=None, new_res=0.3, square_size_size_mm=22.5, denoising=True, verbose=1):
    printv('\nPre-processing data ...', verbose, 'normal')

    tmp_dir = 'tmp_preprocessing_' + time.strftime("%y%m%d%H%M%S") + '_' + str(random.randint(1, 1000000)) + '/'
    if not os.path.exists(tmp_dir):
        os.mkdir(tmp_dir)

    shutil.copy(fname_target, tmp_dir)
    shutil.copy(fname_sc_seg, tmp_dir)
    os.chdir(tmp_dir)

    original_info = {'orientation': None, 'im_target_rpi': None, 'interpolated_images': []}

    im_target = Image(fname_target)
    im_sc_seg = Image(fname_sc_seg)

    # get original orientation
    printv('\n\tReorient ...', verbose, 'normal')
    original_info['orientation'] = im_target.orientation

    # assert images are in the same orientation
    assert im_target.orientation == im_sc_seg.orientation, "ERROR: the image to segment and it's SC segmentation are not in the same orientation"

    im_target_rpi = set_orientation(im_target, 'RPI')
    im_sc_seg_rpi = set_orientation(im_sc_seg, 'RPI')
    original_info['im_target_rpi'] = im_target_rpi  # target image in RPI will be used to post-process segmentations

    # interpolate image to reference square image (resample and square crop centered on SC)
    printv('\n\tInterpolate data to the model space ...', verbose, 'normal')
    list_im_slices = interpolate_im_to_ref(im_target_rpi, im_sc_seg_rpi, new_res=new_res, sq_size_size_mm=square_size_size_mm)
    original_info['interpolated_images'] = list_im_slices

    # denoise using P. Coupe non local means algorithm (see [Manjon et al. JMRI 2010]) implemented in dipy
    if denoising:
        printv('\n\tDenoise ...', verbose, 'normal')
        from dipy.denoise.nlmeans import nlmeans
        from dipy.denoise.noise_estimate import estimate_sigma
        nx, ny, nz = list_im_slices[0].data.shape
        data = np.asarray([im.data.reshape(nx, ny) for im in list_im_slices])
        sigma = estimate_sigma(data)
        data_denoised = nlmeans(data, sigma)

        for i in range(len(list_im_slices)):
            list_im_slices[i].data = data_denoised[i]

    printv('\n\t\tMask data using the spinal cord mask ...', verbose, 'normal')
    list_sc_seg_slices = interpolate_im_to_ref(im_sc_seg_rpi, im_sc_seg_rpi, new_res=new_res, sq_size_size_mm=square_size_size_mm)
    for i in range(len(list_im_slices)):
        list_im_slices[i].data[list_sc_seg_slices[i] == 0] = 0

    printv('\n\tSplit along rostro-caudal direction...', verbose, 'normal')
    list_slices_target = [Slice(slice_id=i, im=im_slice.data, gm_seg=[], wm_seg=[]) for i, im_slice in enumerate(list_im_slices)]

    # load vertebral levels
    if fname_level is not None:
        printv('\n\tLoad vertebral levels ...', verbose, 'normal')
        # copy level file to tmp dir
        os.chdir('..')
        shutil.copy(fname_level, tmp_dir)
        os.chdir(tmp_dir)
        # change fname level to only file name (path = tmp dir now)
        path_level, file_level, ext_level = extract_fname(fname_level)
        fname_level = file_level+ext_level
        # load levels
        list_slices_target = load_level(list_slices_target, fname_level)

    # load manual gmseg if there is one (model data)
    if fname_manual_gmseg is not None:
        printv('\n\tLoad manual GM segmentation(s) ...', verbose, 'normal')
        list_slices_target = load_manual_gmseg(list_slices_target, fname_manual_gmseg, tmp_dir, im_sc_seg_rpi, new_res, square_size_size_mm)

    os.chdir('..')
    printv('\nPre-processing done!', verbose, 'normal')
    return list_slices_target, original_info


# ----------------------------------------------------------------------------------------------------------------------
def interpolate_im_to_ref(im_input, im_input_sc, new_res=0.3, sq_size_size_mm=22.5):
    nx, ny, nz, nt, px, py, pz, pt = im_input.dim

    sq_size = int(sq_size_size_mm/new_res)
    # create a reference image : square of ones
    im_ref = Image(np.ones((sq_size, sq_size, 1), dtype=np.int), dim=(sq_size, sq_size, 1, 0, new_res, new_res, pz, 0), orientation='RPI')

    # copy input header to reference image
    im_ref.hdr = im_input.hdr

    # set correct header to reference image
    im_ref.hdr.set_data_shape((sq_size, sq_size, 1))
    im_ref.hdr.set_zooms((new_res, new_res, pz))

    # save image to set orientation to RPI (not properly done at the creation of the image)
    fname_ref = 'im_ref.nii.gz'
    im_ref.setFileName(fname_ref)
    im_ref.save()
    im_ref = set_orientation(im_ref, 'RPI', fname_out=fname_ref)

    # set header origin to zero to get physical coordinates of the center of the square
    im_ref.hdr.as_analyze_map()['qoffset_x'] = 0
    im_ref.hdr.as_analyze_map()['qoffset_y'] = 0
    im_ref.hdr.as_analyze_map()['qoffset_z'] = 0
    im_ref.hdr.set_sform(im_ref.hdr.get_qform())
    im_ref.hdr.set_qform(im_ref.hdr.get_qform())
    [[x_square_center_phys, y_square_center_phys, z_square_center_phys]] = im_ref.transfo_pix2phys(coordi=[[int(sq_size / 2), int(sq_size / 2), 0]])

    list_interpolate_images = []
    # iterate on z dimension of input image
    for iz in range(nz):
        # copy reference image: one reference image per slice
        im_ref_slice_iz = im_ref.copy()

        # get center of mass of SC for slice iz
        x_seg, y_seg = (im_input_sc.data[:, :, iz] > 0).nonzero()
        x_center, y_center = np.mean(x_seg), np.mean(y_seg)
        [[x_center_phys, y_center_phys, z_center_phys]] = im_input_sc.transfo_pix2phys(coordi=[[x_center, y_center, iz]])

        # center reference image on SC for slice iz
        im_ref_slice_iz.hdr.as_analyze_map()['qoffset_x'] = x_center_phys - x_square_center_phys
        im_ref_slice_iz.hdr.as_analyze_map()['qoffset_y'] = y_center_phys - y_square_center_phys
        im_ref_slice_iz.hdr.as_analyze_map()['qoffset_z'] = z_center_phys
        im_ref_slice_iz.hdr.set_sform(im_ref_slice_iz.hdr.get_qform())
        im_ref_slice_iz.hdr.set_qform(im_ref_slice_iz.hdr.get_qform())

        # interpolate input image to reference image
        im_input_interpolate_iz = im_input.interpolate_from_image(im_ref_slice_iz, interpolation_mode=3, border='reflect')
        list_interpolate_images.append(im_input_interpolate_iz)

    return list_interpolate_images


# ----------------------------------------------------------------------------------------------------------------------
def load_level(list_slices_target, fname_level):
    verbose = 1
    path_level, file_level, ext_level = extract_fname(fname_level)

    #  ####### Check if the level file is an image or a text file
    # Level file is an image
    if ext_level in ['.nii', '.nii.gz']:
        im_level = Image(fname_level)
        im_level.change_orientation('IRP')

        list_level = []
        list_med_level = []
        for slice_level in im_level.data:
            try:
                # vertebral level of the slice
                l = np.mean(slice_level[slice_level > 0])
                # median of the vertebral level of the slice: if all voxels are int, med will be an int.
                med = np.median(slice_level[slice_level > 0])
                # change med in int if it is an int
                med = int(med) if int(med)==med else med
            except Exception, e:
                printv('WARNING: ' + str(e) + '\nNo level label found. Level will be set to 0 for this slice', verbose, 'warning')
                l = 0
                med = 0
            list_level.append(l)
            list_med_level.append(med)

        # if all median of level are int for all slices : consider level as int
        if all([isinstance(med, int) for med in list_med_level]):
            # level as int are placed in the middle of each vertebra (that's why there is a "+0.5")
            list_level = [int(round(l))+0.5 for l in list_level]

    # Level file is a text file
    elif ext_level == '.txt':
        file_level = open(fname_level, 'r')
        lines_level = file_level.readlines()
        file_level.close()

        list_level_by_slice = []
        list_type_level = []  # True or int, False for float
        for line in lines_level[1:]:
            i_slice, level = line.split(',')
            i_slice, level = int(i_slice), float(level)
            list_type_level.append(int(level) == level)
            list_level_by_slice.append((i_slice, level))

        # sort list by number of slice
        list_level_by_slice.sort()

        if all(list_type_level):  # levels are int
            # add 0.5 to the int level to place in the middle of the vertebra
            to_add = 0.5
        else:
            # levels are float: keep them untouched
            to_add = 0

        list_level = [l[1]+to_add for l in list_level_by_slice]

    # Level file is not recognized
    else:
        list_level = None
        printv('ERROR: the level file is nor an image nor a text file ...', verbose, 'error')

    #  ####### Set level number for each slice of list_slices_target:
    for target_slice, level in zip(list_slices_target, list_level):
        target_slice.set(level=level)

    return list_slices_target


# ----------------------------------------------------------------------------------------------------------------------
def load_manual_gmseg(list_slices_target, list_fname_manual_gmseg, tmp_dir, im_sc_seg_rpi, new_res, square_size_size_mm):
    if isinstance(list_fname_manual_gmseg, str):
        # consider fname_manual_gmseg as a list of file names to allow multiple manual GM segmentation
        list_fname_manual_gmseg = [list_fname_manual_gmseg]

    for fname_manual_gmseg in list_fname_manual_gmseg:
        os.chdir('..')
        shutil.copy(fname_manual_gmseg, tmp_dir)
        # change fname level to only file name (path = tmp dir now)
        path_gm, file_gm, ext_gm = extract_fname(fname_manual_gmseg)
        fname_manual_gmseg = file_gm + ext_gm
        os.chdir(tmp_dir)

        im_manual_gmseg = Image(fname_manual_gmseg)

        # reorient to RPI
        im_manual_gmseg = set_orientation(im_manual_gmseg, 'RPI')

        # assert gmseg has the right number of slices
        assert im_manual_gmseg.data.shape[2] == len(list_slices_target), 'ERROR: the manual GM segmentation has not the same number of slices than the image.'

        # interpolate gm to reference image
        nz_gmseg, nx_gmseg, ny_gmseg, nt_gmseg, pz_gmseg, px_gmseg, py_gmseg, pt_gmseg = im_manual_gmseg.dim

        list_im_gm = interpolate_im_to_ref(im_manual_gmseg, im_sc_seg_rpi, new_res=new_res, sq_size_size_mm=square_size_size_mm)

        # load gm seg in list of slices
        for im_gm, slice_im in zip(list_im_gm, list_slices_target):
            slice_im.gm_seg.append(im_gm.data)

            wm_slice = (slice_im.im > 0) - im_gm.data
            slice_im.wm_seg.append(wm_slice)

    return list_slices_target

########################################### End of pre-processing function #############################################


