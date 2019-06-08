#! /usr/bin/python3

import os
import sys
import re
import tarfile
import shutil


ext_list = '.boxlist'
ext_box = '.box.tar.gz'


def getSubDir(rootDir, level=1, includeHidden=False, followSymLink=False):
    f = os.listdir(rootDir)
    if not includeHidden:
        f = [x for x in f if (not x.startswith('.'))]
    if not followSymLink:
        f = [x for x in f if (not os.path.islink(x))]
    f = [os.path.join(rootDir, f) for f in f]
    f = [x for x in f if os.path.isdir(x)]
    # ^ this can only be checked after prefixing rootDir if rootDir is not cwd
    if not f:
        print('\nNo folder found.\n')
        sys.exit(-1)
    else:
        f = [os.path.abspath(f) for f in f]
        f.sort()
        return f


def getTars(rootDir):
    f = []
    for root, directories, filenames in os.walk(rootDir):
        for file in filenames:
            f.append(os.path.abspath(os.path.join(root, file)))
    f = [x for x in f if x.endswith(ext_box)]
    if not f:
        print('\nNo "' + ext_box + '" file found.\n')
        sys.exit(-1)
    else:
        f.sort()
        return f


def readList(flist):
    if not flist.endswith(ext_list):
        print('Your list file needs an extension of "' + ext_list + '".')
        sys.exit(-1)
    else:
        f = []
        with open(flist, "r") as fhandle:
            line = fhandle.readline()
            while line:
                f.append(line.strip())
                line = fhandle.readline()
            n = len(f)
            f = [x for x in f if os.path.isabs(x)]
            if n != len(f):
                print('Warning:', n - len(f), 'non-absolute paths removed.')
            # remove duplicate items
            n = len(f)
            f = list(set(f))
            if len(f) != n:
                print('Warning:', n - len(f), 'duplicate items removed.')
            if not f:
                print('No valid item in this list.\n')
                sys.exit(-1)
            else:
                # strip off trailing path separator
                f2 = []
                for x in f:
                    while x.endswith(os.sep):
                        x = x[:-1]
                    f2.append(x)
                return f2


def processPackList(flist):
    f = readList(flist)
    n = len(f)
    f = [x for x in f if os.path.isdir(x)]
    if len(f) != n:
        print('Warning:', n - len(f), 'invalid paths removed.')
    # remove folders that are ancesters of other folders
    f.sort()
    exclude = []
    for x in f:
        for y in f:
            if y.startswith(x + os.path.sep) and y != x:
                exclude.append(x)
                break
    n = len(f)
    f = [x for x in f if x not in exclude]
    if n != len(f):
        print('Warning:', n - len(f), 'ancestors removed:')
        printList(exclude, '')
    if not f:
        print('No valid item in this list.\n')
        sys.exit(-1)
    else:
        return f


def processUnpackList(flist):
    f = readList(flist)
    f = [x for x in f if x.endswith('.box.tar.gz') and os.path.isfile(x)]
    if not f:
        print('No valid item in this list.\n')
        sys.exit(-1)
    else:
        return f


def printList(f, msg='default'):
    if msg == 'default':
        print('\nThe following items are available:\n')
    else:
        print(msg)
    n = 0
    for dir in f:
        n += 1
        print('\t[' + str(n) + ']', dir)


def refineList(f):
    printList(f)
    while True:
        keep = input('\nSelect ' +
                     '(e.g. "1 2 4", or 0 to select ALL): ')
        keep = re.sub('\s+|,|;|/', ' ', keep).strip().split()
        try:
            keep = [int(x) for x in keep]
        except ValueError:
            print('Invalid input!')
            continue
        keep = list(set(keep))
        keep.sort()
        if min(keep) < 0:
            print('Invalid index!')
            continue
        if (max(keep) - 1) > (len(f) - 1):
            print('Index exceeds bound!')
            continue
        else:
            break
    if keep[0] == 0:
        return f
    elif len(keep) == 1:
        return [f.pop(keep[0] - 1)]
    else:
        f2 = []
        for i in keep:
            f2.append(f[i-1])
        return f2


def finalConfirm(f):
    printList(f)
    while True:
        go = input('\nConfirm for operation & DELETEION (yes/no): ')
        if go == 'yes':
            return
        elif go == 'no':
            raise KeyboardInterrupt
        else:
            print('Please type "yes" or "no".')
            continue


def pack(f):
    n = 0
    for x in f:
        n = n + 1
        tarName = x + '.box.tar.gz'
        print('Processing (' + str(n) + '/' + str(len(f)) + '): '
              + x + ' ... ', end='')
        sys.stdout.flush()
        try:
            tar = tarfile.open(name=tarName, mode='w:gz', dereference=False)
            tar.add(x, arcname=os.path.split(x)[1])
            tar.close()
            shutil.rmtree(x)
        except:
            print('\nError when procsessing', x, '.\n')
            tar.close()
            raise
        else:
            print('[OK!]')
    print('Packing completed.')


def unpack(f):
    n = 0
    for x in f:
        n = n + 1
        print('Processing (' + str(n) + '/' + str(len(f)) + '): '
              + x + ' ... ', end='')
        sys.stdout.flush()
        try:
            tar = tarfile.open(x, 'r:gz')
            tar.extractall(path=os.path.dirname(x))
            tar.close()
            os.remove(x)
        except:
            print('\nError when procsessing', x, '.\n')
            tar.close()
            raise
        else:
            print('[OK!]')
    print('Upacking completed.')


def printWarning():
    print('\n - Using this script may result in data loss.\n',
          '- Test on un-important files first.\n',
          '- Proceed at your own risk.')


def dispHelp():
    s = '''
boxarch - selectively tar + gzip sub-folders to make cloud uploading easier.
\nUSAGE\n
  boxarch [operation] [directory]\n
  [operation]:
\t-p, --pack\tMake compressed archives to replace the original folders in place.
\t-u, --unpack\tRecursively uncompress archives to restore the original folders.
\t--help\t\tDisplay help infomation.\n
  [directory]:
\tDefaults to "./" (the current directory).\n
lm808, June 2019
'''
    print(s)


if __name__ == '__main__':
    # packdir <operation> <root-dir>
    nargin = len(sys.argv)
    if nargin == 1:
        print('Insufficient argument.')
        sys.exit(-1)
    elif nargin == 2:
        cmd = sys.argv[1]
        inputs = './'
    elif nargin == 3:
        cmd = sys.argv[1]
        inputs = sys.argv[2]
    else:
        print('Too many arguments.')
        sys.exit(-1)
    try:
        if cmd in ('--pack', '-p'):
            # printWarning()
            if os.path.isfile(inputs):
                f = processPackList(inputs)
            elif os.path.isdir(inputs):
                f = getSubDir(inputs)
                f = refineList(f)
            else:
                print('Invalid packing input.')
                sys.exit(-1)
            finalConfirm(f)
            pack(f)
        elif cmd in ('--unpack', '-u'):
            # printWarning()
            if os.path.isfile(inputs):
                f = processUnpackList(inputs)
            elif os.path.isdir(inputs):
                f = getTars(inputs)
                f = refineList(f)
            else:
                print('Invalid unpacking input.')
                sys.exit(-1)
            finalConfirm(f)
            unpack(f)
        elif cmd == '--help':
            dispHelp()
            sys.exit(0)
        else:
            print('Invalid operation.')
            sys.exit(-1)
    except KeyboardInterrupt:
        print('\nAbort mission.\n')
        sys.exit(0)


#     for root, directories, filenames in os.walk('/tmp/'):
# ...     for directory in directories:
# ...             print os.path.join(root, directory)
# ...     for filename in filenames:
# ...             print os.path.join(root,filename)
