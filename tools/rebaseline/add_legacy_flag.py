#!/usr/bin/env python
# Copyright (c) 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

README = """
Automatically add a specific legacy flag to multiple Skia client repos.

This would only work on Google desktop.

Example usage:
  $ python add_legacy_flag.py SK_SUPPORT_LEGACY_SOMETHING \\
      -a /data/android -c ~/chromium/src -g legacyflag

If you only need to add the flag to one repo, for example, Android, please give
only -a (--android-dir) argument:
  $ python add_legacy_flag.py SK_SUPPORT_LEGACY_SOMETHING -a /data/android

"""

import os, sys
import argparse
import subprocess
import getpass
from random import randint


ANDROID_TOOLS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'android')


def insert_at(filename, pattern, offset, content):
  with open(filename) as f:
    lines = f.readlines()

  line_index = lines.index(pattern)
  lines.insert(line_index + offset, content)

  with open(filename, 'w') as f:
    for line in lines:
      f.write(line)


def add_to_android(args):
  REPO_BRANCH_NAME = "flag"
  sys.path.append(ANDROID_TOOLS_DIR)
  import upload_to_android

  repo_binary = upload_to_android.init_work_dir(args.android_dir);

  # Create repo branch.
  subprocess.check_call('%s start %s .' % (repo_binary, REPO_BRANCH_NAME),
                        shell=True)

  try:
    # Add flag to SkUserConfigManual.h.
    config_file = os.path.join('include', 'config', 'SkUserConfigManual.h')

    insert_at(config_file,
              "#endif // SkUserConfigManual_DEFINED\n",
              0,
              "  #define %s\n" % args.flag)

    subprocess.check_call('git add %s' % config_file, shell=True)

    message = ('Add %s\n\n'
               'Test: Presubmit checks will test this change.' % args.flag)

    subprocess.check_call('git commit -m "%s"' % message, shell=True)

    # Upload to Android Gerrit.
    subprocess.check_call('%s upload --verify' % repo_binary, shell=True)
  finally:
    # Remove repo branch
    subprocess.check_call('%s abandon flag' % repo_binary, shell=True)


def add_to_chromium(args):
  os.chdir(args.chromium_dir)

  branch = subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD'])
  branch = branch.strip()

  EXPECTED_STASH_OUT = "No local changes to save"
  stash_output = subprocess.check_output(['git', 'stash']).strip()

  if branch != "master" or stash_output != EXPECTED_STASH_OUT:
    print ("Please checkout a clean master branch at your chromium repo (%s) "
        "before running this script") % args.chromium_dir
    if stash_output != EXPECTED_STASH_OUT:
      subprocess.check_call(['git', 'stash', 'pop'])
    exit(1)

  # Use random number to avoid branch name collision.
  # We'll delete the branch in the end.
  random = randint(1, 10000)
  subprocess.check_call(['git', 'checkout', '-b', 'legacyflag_%d' % random])

  try:
    config_file = os.path.join('skia', 'config', 'SkUserConfig.h')
    separator = (
      "///////////////////////// Imported from BUILD.gn and skia_common.gypi\n")
    content = ("#ifndef {0}\n"
               "#define {0}\n"
               "#endif\n\n").format(args.flag)
    insert_at(config_file, separator, 0, content)

    subprocess.check_call('git commit -a -m "Add %s"' % args.flag, shell=True)
    subprocess.check_call('git cl upload -m "Add %s" -f' % args.flag,
                          shell=True)
  finally:
    subprocess.check_call(['git', 'checkout', 'master'])
    subprocess.check_call(['git', 'branch', '-D', 'legacyflag_%d' % random])


def add_to_google3(args):
  G3_SCRIPT_DIR = os.path.expanduser("~/skia-g3/scripts")
  if not os.path.isdir(G3_SCRIPT_DIR):
    print ("Google3 directory unavailable.\n"
           "Please see "
           "https://sites.google.com/a/google.com/skia/rebaseline#g3_flag "
           "for Google3 setup.")
    exit(1)
  sys.path.append(G3_SCRIPT_DIR)
  import citc_flag

  citc_flag.add_to_google3(args.google3, args.flag)


def main():
  if len(sys.argv) <= 1 or sys.argv[1] == '-h' or sys.argv[1] == '--help':
    print README

  parser = argparse.ArgumentParser()
  parser.add_argument(
      '--android-dir', '-a', required=False,
      help='Directory where an Android checkout will be created (if it does '
           'not already exist). Note: ~1GB space will be used.')
  parser.add_argument(
      '--chromium-dir', '-c', required=False,
      help='Directory of an EXISTING Chromium checkout (e.g., ~/chromium/src)')
  parser.add_argument(
      '--google3', '-g', required=False,
      help='Google3 workspace to be created (if it does not already exist).')
  parser.add_argument('flag', type=str, help='legacy flag name')

  args = parser.parse_args()

  if not args.android_dir and not args.chromium_dir and not args.google3:
    print """
Nothing to do. Please give me at least one of these three arguments:
  -a (--android-dir)
  -c (--chromium-dir)
  -g (--google3)
"""
    exit(1)

  end_message = "CLs generated. Now go review and land them:\n"
  if args.chromium_dir:
    args.chromium_dir = os.path.expanduser(args.chromium_dir)
    add_to_chromium(args)
    end_message += " * https://chromium-review.googlesource.com\n"
  if args.google3:
    add_to_google3(args)
    end_message += " * http://goto.google.com/cl\n"
  if args.android_dir:
    args.android_dir = os.path.expanduser(args.android_dir)
    add_to_android(args)
    end_message += " * http://goto.google.com/androidcl\n"

  print end_message


if __name__ == '__main__':
  main()