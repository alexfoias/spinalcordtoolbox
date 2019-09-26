#!/usr/bin/env python
#########################################################################################
#
# sct_crop_image and crop image wrapper.
#
# ---------------------------------------------------------------------------------------
# Copyright (c) 2014 Polytechnique Montreal <www.neuro.polymtl.ca>
# Authors: Benjamin Leener, Julien Cohen-Adad, Olivier Comtois
# Modified: 2015-05-16
#
# About the license: see the file LICENSE.TXT
#########################################################################################

from __future__ import absolute_import, division

import sys
import os
import argparse

from spinalcordtoolbox.cropping import ImageCropper
from spinalcordtoolbox.image import Image, zeros_like
from spinalcordtoolbox.utils import Metavar, SmartFormatter
import sct_utils as sct


def get_parser():

    # Mandatory arguments
    parser = argparse.ArgumentParser(
        description='Tools to crop an image. Either through command line or GUI',
        add_help=None,
        formatter_class=SmartFormatter,
        prog=os.path.basename(__file__).strip(".py"))

    mandatoryArguments = parser.add_argument_group("\nMANDATORY ARGUMENTS")
    mandatoryArguments.add_argument(
        "-i",
        required=True,
        help='Input image. Example: t2.nii.gz',
        metavar=Metavar.file,
        )

    optional = parser.add_argument_group("\nOPTIONAL ARGUMENTS")
    optional.add_argument(
        "-h",
        "--help",
        action="help",
        help="Show this help message and exit")
    optional.add_argument(
        '-o',
        help="Output image. By default, the suffix '_crop' will be added to the input image.",
        metavar=Metavar.str,
    )
    optional.add_argument(
        "-g",
        type=int,
        help="0: Cropping via command line | 1: Cropping via GUI",
        choices=(0, 1),
        default=0,
    )
    optional.add_argument(
        "-v",
        type=int,
        help="1: display on, 0: display off (default)",
        required=False,
        choices=(0, 1),
        default = 1)

    optional.add_argument(
        "-m",
        help="Cropping around the mask",
        metavar=Metavar.file,
        required=False)
    optional.add_argument(
        "-start",
        help='Start slices, ]0,1[: percentage, 0 & >1: slice number. Example: 40,30,5',
        metavar=Metavar.list,
        required = False)
    optional.add_argument(
        "-end",
        help='End slices, ]0,1[: percentage, 0: last slice, >1: slice number, <0: last slice - value. '
             'Example: 60,100,10',
        metavar=Metavar.list,
        required = False)
    optional.add_argument(
        "-dim",
        help='Dimension to crop, from 0 to n-1, default is 1. Example: 0,1,2',
        metavar=Metavar.list,
        required = False)
    optional.add_argument(
        "-shift",
        help='adding shift when used with mask, default is 0. Example: 10,10,5',
        metavar=Metavar.list,
        required = False)
    optional.add_argument(
        "-b",
        type=float,
        help="Replace voxels outside cropping region with background value. If both the -m and the -b flags are used, "
             "the image is croped \"exactly\" around the mask with a background (and not around a rectangle area "
             "including the mask). The shape of the image does not change.",
        metavar=Metavar.float,
        required=False)
    optional.add_argument(
        "-bmax",
        help="Maximize the cropping of the image (provide -dim if you want to specify the dimensions).",
        metavar='',
        required=False)
    optional.add_argument(
        "-ref",
        help='Crop input image based on reference image (works only for 3D images). Example: ref.nii.gz',
        metavar=Metavar.file,
        required = False)
    optional.add_argument(
        "-mesh",
        help="Mesh to crop",
        metavar=Metavar.file,
        required=False)
    optional.add_argument(
        "-rof",
        type=int,
        help="Remove output file created when cropping",
        required=False,
        default=0,
        choices=(0, 1))

    return parser


def main(args=None):
    """
    Main function
    :param args:
    :return:
    """
    # get parser args
    if args is None:
        args = None if sys.argv[1:] else ['--help']
    parser = get_parser()
    arguments = parser.parse_args(args=args)

    # initialize ImageCropper
    cropper = ImageCropper(arguments.i)
    cropper.verbose = arguments.v
    sct.init_sct(log_level=cropper.verbose, update=True)  # Update log level

    # set output filename
    if arguments.o is None:
        cropper.output_filename = sct.add_suffix(arguments.i, '_crop')
    else:
        cropper.output_filename = arguments.o

    # Cropping with GUI vs. CLI
    # TODO: if not enough CLI arguments for cropping, open GUI
    if arguments.g:
        cropper.crop_with_gui()
    else:
        if arguments.m is not None:
            cropper.mask = arguments.m
        if arguments.start is not None:
            cropper.start = (arguments.start).split(",")
        if arguments.start is not None:
            cropper.end = (arguments.end).split(",")
        if arguments.dim is not None:
            cropper.dim = (arguments.dim).split(",")
        if arguments.shift is not None:
            cropper.shift = (arguments.shift).split(",")
        if arguments.b is not None:
            cropper.background = arguments.b
        if arguments.bmax is not None:
            cropper.bmax = True
        if arguments.ref is not None:
            cropper.ref = arguments.ref
        if arguments.mesh is not None:
            cropper.mesh = arguments.mesh

        cropper.crop()


if __name__ == "__main__":
    sct.init_sct()
    main()

