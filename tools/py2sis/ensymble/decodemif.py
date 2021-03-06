#!/usr/bin/env python
# -*- coding: utf-8 -*-

##############################################################################
# decodemif.py - Decodes a Symbian OS v9.x multi-image file (MIF)
# Copyright 2006, 2007 Jussi Yl?nen
#
# This program is part of Ensymble developer utilities for Symbian OS(TM).
#
# Ensymble is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Ensymble is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ensymble; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
#
# Version history
# ---------------
#
# v0.03 2006-09-22
# Replaced every possible range(...) with xrange(...) for efficiency
#
# v0.02 2006-08-22
# Added file type recognition (SVG, binary SVG or other)
#
# v0.01 2006-08-14
# Added support for strange index entries (length 0)
#
# v0.00 2006-08-13
# Work started
##############################################################################

VERSION = "v0.02 2006-09-22"

import sys
import os
import struct
import getopt
import random
import tempfile

# Parameters
MAXMIFFILESIZE      = 1024 * 1024       # Arbitrary maximum size of MIF file

tempdir = None
dumpcounter = 0

def mkdtemp(template):
    '''
    Create a unique temporary directory.

    tempfile.mkdtemp() was introduced in Python v2.3. This is for
    backward compatibility.
    '''

    # Cross-platform way to determine a suitable location for temporary files.
    systemp = tempfile.gettempdir()

    if not template.endswith("XXXXXX"):
        raise ValueError("invalid template for mkdtemp(): %s" % template)

    for n in xrange(10000):
        randchars = []
        for m in xrange(6):
            randchars.append(random.choice("abcdefghijklmnopqrstuvwxyz"))

        tempdir = os.path.join(systemp, template[: -6]) + "".join(randchars)

        try:
            os.mkdir(tempdir, 0700)
            return tempdir
        except OSError:
            pass

def dumpdata(data):
    '''Dumps data to a file in a temporary directory.'''

    global tempdir, dumpcounter

    if tempdir == None:
        # Create temporary directory for dumped files.
        tempdir = mkdtemp("decodemif-XXXXXX")
        dumpcounter = 0

    # Determine file type.
    if data[0:5] == "<?xml":
        ext = "svg"
    elif data[0:4] == '\xcc\x56\xfa\x03':
        ext = "svgb"
    else:
        ext = "dat"

    filename = os.path.join(tempdir, "dump%04d.%s" % (dumpcounter, ext))
    dumpcounter += 1
    f = file(filename, "wb")
    f.write(data)
    f.close()
    print "%s written" % filename

def main():
    global tempdir, dumpcounter

    pgmname     = os.path.basename(sys.argv[0])
    pgmversion  = VERSION

    try:
        try:
            gopt = getopt.gnu_getopt
        except:
            # Python <v2.3, GNU-style parameter ordering not supported.
            gopt = getopt.getopt

        # Parse command line using getopt.
        short_opts = "t:h"
        long_opts = [
            "dumpdir", "help"
        ]
        args = gopt(sys.argv[1:], short_opts, long_opts)

        opts = dict(args[0])
        pargs = args[1]

        if "--help" in opts.keys() or "-h" in opts.keys():
            # Help requested.
            print (
'''
DecodeMIF - Symbian OS v9.x MIF file decoder %(pgmversion)s

usage: %(pgmname)s [--dumpdir=DIR] [miffiles...]

        -t, --dumpdir       - Directory to use for dumped files (or automatic)
        miffiles            - MIF files to decode (stdin if not given or -)

''' % locals())
            return 0

        # A temporary directory is generated by default.
        tempdir = opts.get("--dumpdir", opts.get("-t", None))

        if len(pargs) == 0:
            miffilenames = ["-"]
        else:
            miffilenames = pargs

        for miffilename in miffilenames:
            if miffilename == '-':
                miffile = sys.stdin
            else:
                miffile = file(miffilename, "rb")

            try:
                # Load the whole MIF file as a string.
                mifdata = miffile.read(MAXMIFFILESIZE)
                if len(mifdata) == MAXMIFFILESIZE:
                    raise IOError("%s: file too large" % miffilename)
            finally:
                if miffile != sys.stdin:
                    miffile.close()

            # Verify MIF signature.
            if mifdata[:4] != "B##4":
                raise ValueError("%s: not a MIF file" % miffilename)

            if len(mifdata) < 16:
                raise ValueError("%s: file too short" % miffilename)

            entries = struct.unpack("<L", mifdata[12:16])[0] / 2

            # Verify header length:
            # 16-byte header, 16 bytes per index entry
            if len(mifdata) < (16 + 16 * entries):
                raise ValueError("%s: file too short" % miffilename)

            # Read index.
            index = []
            for n in xrange(entries):
                hdroff = 16 + n * 16
                a = struct.unpack("<L", mifdata[hdroff +  0:hdroff + 4])[0]
                b = struct.unpack("<L", mifdata[hdroff +  4:hdroff + 8])[0]
                c = struct.unpack("<L", mifdata[hdroff +  8:hdroff + 12])[0]
                d = struct.unpack("<L", mifdata[hdroff + 12:hdroff + 16])[0]

                if b == 0 and d == 0:
                    # Unknown index entry type, skip it.
                    continue

                if a != c or b != d:
                    raise ValueError("%s: invalid index entry %d" %
                                     (miffilename, n))

                # Check total length of file.
                if a + b > len(mifdata):
                    raise ValueError("%s: index %d out of range" %
                                     (miffilename, n))

                index.append((a, b))

            n = len(index)
            print "%s: %s %s inside" % (miffilename, n or "no",
                                        ((n == 1) and "file") or "files")

            # Extract contents.
            for i in index:
                offset = i[0]
                length = i[1]
                if mifdata[offset:offset + 4] != "C##4":
                    raise ValueError("%s: invalid file header %d" %
                                     (miffilename, n))

                print "0x%08x 0x%08x 0x%08x 0x%08x 0x%08x 0x%08x 0x%08x" % (
                    tuple(struct.unpack("<LLLLLLL", mifdata[(offset + 4):
                                                            (offset + 32)])))
                dumpdata(mifdata[offset + 32:offset + length + 32])
    except (TypeError, ValueError, IOError, OSError), e:
        return "%s: %s" % (pgmname, str(e))
    except KeyboardInterrupt:
        return ""

# Call main if run as stand-alone executable.
if __name__ == '__main__':
    sys.exit(main())
