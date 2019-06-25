#!/usr/bin/env python3

import os
import sys
import re
import shutil
import subprocess
from datetime import datetime
# import tarfile


def dispHelp():
    s = '''
boxup - selectively tar + gzip sub-folders to make cloud uploading easier.

USAGE

    boxup [command] [inputs] <options>

[command]:
    -p, --pack      Make compressed archives to replace the original folders in place.
    -u, --unpack    Recursively uncompress archives to restore the original folders.
    -s, --split     Recursively find over-sized box.tar.gz files, and offers to split
                    them into smaller segments.
    -c, --combine   Recursively finds file segments, and offers to re-combine them into
                    a single file.
    --install       Sets up an alias in .bashrc (GNU/Linux) or .bash_profile (macOS).
    --uninstall     Removes the above alias.
    --help          Display this infomation.

[inputs]:
    One of the following:
    (1) The directory for a search of eligible inputs, default the current directory.
        For '--pack', the search is limited in the directory, non-recursive.
        For '--unpack', the search is recursive.
        For '--split' and '--combine', this is the only choice.
    (2) A text file with the extension of '.box.list' in which every line
        is the full path to a directory/archive file to pack/unpack.

<options>:
    -i, --ignore-error  Do not stop if an error is encoutered in file operations.
                        Instead, write the failed operations in a 'failed.box.log'
                        file under the current working directory.

lm808, June 2019
'''
    print(s)


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


def getParts(rootDir):
    parts = []
    for root, directories, filenames in os.walk(rootDir):
        for file in filenames:
            parts.append(os.path.abspath(os.path.join(root, file)))
    parts = [x for x in parts if (ext_box + ext_part) in x]
    if not parts:
        print('\nNo "' + ext_box + ext_part + '**" file found.\n')
        sys.exit(-1)
    else:
        files = {}
        for x in parts:
            f = x.split(ext_box)[0] + ext_box
            if f not in files:
                files[f] = 1
            else:
                files[f] += 1
        return files


def getOverSize(rootDir):
    while True:
        lim = input('Specify size limit (in GiB [1024 MiB]): ')
        try:
            lim = int(lim)
            break
        except ValueError:
            print('Invalid input, integer only.')
            continue
    f = getTars(rootDir)
    f = [x for x in f if os.path.getsize(x) > (lim * 1024 ** 3)]
    return f, lim


def printList(f, msg='default'):
    # leading message
    if msg == 'default':
        print('\nThe following items are available:\n')
    else:
        print(msg)
    # loop through list / dictionary
    m = 0
    if type(f) == list:
        for x in f:
            m += 1
            print('\t[' + str(m) + ']', x, end='')
            if os.path.isfile(x):
                print(' (' + sizeHR(x) + ')')
            elif os.path.isdir(x):
                print('')
            else:
                print('Error in finding file / directory.')
        return f
    elif type(f) == dict:
        dict2list = [x for x in f.keys()]
        # print and check existence
        for x in dict2list:
            m += 1
            print('\t[' + str(m) + ']', x)
            for i in range(0, f[x]):
                fp = x + ext_part + '%02d' % i
                print('\t\t' + os.path.basename(fp), end='')
                if os.path.isfile(fp):
                    print(' (' + sizeHR(fp) + ')')
                else:
                    print('Error in finding part files.')
                    sys.exit(-1)
        return dict2list
    else:
        print('Invalid data type.')
        sys.exit(-1)


def refineList(f0):
    f = printList(f0)
    # get user input for indecies to keep
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
    # organise return value
    if keep[0] == 0:
        f2 = f
    elif len(keep) == 1:
        f2 = [f.pop(keep[0] - 1)]
    else:
        f2 = []
        for i in keep:
            f2.append(f[i-1])
    # decide return value
    if type(f0) == list:
        return f2
    elif type(f0) == dict:
        return {x: f0[x] for x in f2}
    else:
        print('Invalid data type.')
        sys.exit(-1)


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
        # strip off trailing path separator
        f2 = []
        for x in f:
            while x.endswith(os.sep):
                x = x[:-1]
            f2.append(x)
        return f2


def cleanPackList(flist):
    f = readList(flist)
    f = rmNotAbs(f)
    f = rmDups(f)
    f = rmInvalid(f)
    f.sort()
    f = rmAncestor(f)
    # check if there is any folders remaining
    if not f:
        print('\nNo valid item in this list.\n')
        sys.exit(-1)
    else:
        return f


def cleanUnpackList(flist):
    f = readList(flist)
    f = rmNotAbs(f)
    f = rmDups(f)
    f = [x for x in f if x.endswith('.box.tar.gz') and os.path.isfile(x)]
    if not f:
        print('No valid item in this list.\n')
        sys.exit(-1)
    else:
        return f


def rmNotAbs(f):
    # remove non-absolute paths
    exclude = [x for x in f if not os.path.isabs(x)]
    if len(exclude) > 0:
        print('\nWarning:', len(exclude), 'non-absolute paths removed:')
        printList(exclude, '')
    return [x for x in f if os.path.isabs(x)]


def rmDups(f):
    # remove duplicate items
    f2 = []
    dups = {}
    for x in f:
        if x not in f2:
            f2.append(x)
        elif x in dups:
            dups[x] += 1
        else:
            dups[x] = 1
    if len(f) != len(f2):
        print('\nWarning:', len(f) - len(f2), 'duplicate items removed:\n')
        n = 0
        for x, i in dups.items():
            n += 1
            print('\t[' + str(n) + '] (' + str(i) + ')', x)
    return f2


def rmInvalid(f):
    # remove invalid paths
    exclude = [x for x in f if not os.path.isdir(x)]
    if len(exclude) > 0:
        print('\nWarning:', len(exclude), 'invalid paths removed:')
        printList(exclude, '')
    return [x for x in f if os.path.isdir(x)]


def rmAncestor(f):
    # remove folders that are ancesters of other folders
    exclude = []
    for x in f:
        for y in f:
            if y.startswith(x + os.path.sep) and y != x:
                exclude.append(x)
                break
    if len(exclude) > 0:
        print('\nWarning:', len(exclude), 'ancestors removed:')
        printList(exclude, '')
    return [x for x in f if x not in exclude]


def sizeof_fmt(num, suffix='B'):
    for unit in ['', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)


def sizeHR(f):
    return sizeof_fmt(os.path.getsize(f))


def pack(f, ignoreErr=False):
    n = 0
    for x in f:
        n += 1
        tarName = x + ext_box
        print('Packing (' + str(n) + '/' + str(len(f)) + '): '
              + x + ' ... ', end='')
        sys.stdout.flush()
        try:
            dir = os.path.split(x)[0]
            arcName = os.path.split(x)[1]
            subprocess.run(['tar', '-czf', tarName, '-C', dir, arcName],
                           check=True)
            # tarfile alternative
            # tar = tarfile.open(name=tarName, mode='w:gz', dereference=False)
            # tar.add(x, arcname=os.path.split(x)[1])
            # tar.close()
        except subprocess.CalledProcessError:
            errHandSubProc(x, ignoreErr)
        except KeyboardInterrupt:
            printErr(x)
            raise
        except:
            printErr(x, 'Unexpected error')
            # tar.close() # tarfile alternative
            raise
        else:  # only executes when there is no error
            shutil.rmtree(x)
            print('OK! [' + sizeHR(tarName) + '/' +
                  datetime.now().strftime('%H:%M:%S') + ']')
    print('Packing completed.')


def unpack(f, ignoreErr=False):
    n = 0
    for x in f:
        n += 1
        print('Unpacking (' + str(n) + '/' + str(len(f)) + '): '
              + x + ' ... ', end='')
        sys.stdout.flush()
        try:
            dir = os.path.split(x)[0]
            subprocess.run(["tar", "-xzf", x, '-C', dir], check=True)
            # tarfile alternative
            # tar = tarfile.open(x, 'r:gz')
            # tar.extractall(path=os.path.dirname(x))
            # tar.close()
        except subprocess.CalledProcessError:
            errHandSubProc(x, ignoreErr)
        except KeyboardInterrupt:
            printErr(x)
            raise
        except:
            printErr(x, 'Unexpected error')
            # tar.close() # tarfile alternative
            raise
        else:  # only executes when there is no error
            print('OK! [' + sizeHR(x) + '/' +
                  datetime.now().strftime('%H:%M:%S') + ']')
            os.remove(x)
    print('Upacking completed.')


def combineTar(f, ignoreErr=False):
    n = 0
    for x, np in f.items():
        n += 1
        print('Combining (' + str(n) + '/' + str(len(f)) + '): '
              + x + ' ... ', end='')
        sys.stdout.flush()
        # build cat command
        cat = ['cat']
        for i in range(0, np):
            cat.append(x + ext_part + '%02d' % i)
        # perform the command
        try:
            with open(x, 'wb') as outFile:
                subprocess.run(cat, stdout=outFile, check=True)
                # python alternative
                # for i in range(0, np):
                #     with open((x + ext_part + '%02d' % i), 'rb') as inFile:
                #         outFile.write(inFile.read())
        except subprocess.CalledProcessError:
            errHandSubProc(x, ignoreErr)
        except KeyboardInterrupt:
            printErr(x)
        except:
            printErr(x, 'Unexpected error')
            raise
        else:  # only executes when there is no error
            print('OK! [' + sizeHR(x) + '/' +
                  datetime.now().strftime('%H:%M:%S') + ']')
            for i in range(0, np):
                fp = x + ext_part + '%02d' % i
                os.remove(fp)
    print('Recombine completed.')


def spliTar(f, lim, ignoreErr=False):
    n = 0
    for x in f:
        print('Splitting (' + str(n) + '/' + str(len(f)) + '): '
              + x + ' ... ')
        sys.stdout.flush()
        try:
            subprocess.run(['split', '-b', str(lim) + 'GB', '-d', '--verbose',
                            x, x + ext_part], check=True)
        except subprocess.CalledProcessError:
            errHandSubProc(x, ignoreErr)
        except KeyboardInterrupt:
            printErr(x)
        except:
            printErr(x, 'Unexpected error')
            raise
        else:  # only executes when there is no error
            print('OK! [' + sizeHR(x) + '/' +
                  datetime.now().strftime('%H:%M:%S') + ']')
            os.remove(x)
    print('Splitting completed.')


def errHandSubProc(x, ignoreErr=False):
    printErr(x, '\nExternal command error')
    if ignoreErr:
        with open(file_log, 'a') as logFHandle:
            logFHandle.write(x + '\n')
        pass
    else:
        raise


def printErr(x, errType='Error'):
    print('\n' + errType, end=' ')
    print('when procsessing', x, '.\n')


def printWarning():
    print('\n - Using this script may result in data loss.\n',
          '- Test on un-important files first.\n',
          '- Proceed at your own risk.')


def install():
    # check if the script is in the current directory
    if os.path.isfile(os.path.basename(__file__)):
        script = os.path.abspath(__file__)
    else:
        print('Please perform the install at the location of the script.')
        sys.exit(-1)
    # remove any previous installs (making a backup in the process)
    uninstall()
    # setup new alias and put it into .bashrc or .bash_profile
    alias = "alias boxup='/usr/bin/env python3 " + script + "'"
    with open(bashInitFile(), 'a') as fileHandle:
        fileHandle.write(alias + '\n')
    print('Added:', alias, 'to', bashInitFile(),
          '\nSource or restart shell for this to take effect.')
    return None


def uninstall():
    # make a backup
    backup = bashInitFile() + '.bak'
    shutil.copyfile(bashInitFile(), backup)
    print('Made a backup at:', backup)
    # remove lines from .bashrc or .bash_profile
    rm_keys = ['alias boxup=', 'boxup.py']
    with open(backup) as old_file, open(bashInitFile(), 'w') as new_file:
        for line in old_file:
            if not any(key in line for key in rm_keys):
                new_file.write(line)
            else:
                print('Removed:', line, end='')
    return None


def bashInitFile():
    if sys.platform == 'linux':
        bash_init = os.path.join(os.path.expanduser("~"), '.bashrc')
    elif sys.platform == 'darwin':
        bash_init = os.path.join(os.path.expanduser("~"), '.bash_profile')
    else:
        print('Unsupported system.')
        sys.exit(-1)
    return bash_init


def parseArgs(arg):
    # defaults
    ignoreErr = False
    # positional arguments
    nargin = len(arg)
    if nargin == 1:
        dispHelp()
        sys.exit(-1)
    elif nargin == 2:
        cmd = arg[1]
        inputs = '.'
    elif nargin == 3:
        cmd = arg[1]
        inputs = arg[2]
        if not (os.path.isdir(inputs) or os.path.isfile(inputs)):
            print('Specify file/path as second argument if nargin > 1.')
            sys.exit(-1)
    else:  # options
        cmd = arg[1]
        inputs = arg[2]
        n = 3
        while n < nargin:
            if arg[n] in ('--ignore-error', '-i'):
                ignoreErr = True
                print('Ignoring errors but will write to', file_log)
            else:
                print('Unknown argument "' + arg[n] + '".')
                sys.exit(-1)
            n += 1
    return cmd, inputs, ignoreErr


def main():
    # packdir <command> <root-dir> <options>
    cmd, inputs, ignoreErr = parseArgs(sys.argv)
    try:
        if cmd in ('--pack', '-p'):
            # printWarning()
            if os.path.isfile(inputs):
                f = cleanPackList(inputs)
            elif os.path.isdir(inputs):
                f = getSubDir(inputs)
                f = refineList(f)
            else:
                print('Invalid packing input.')
                sys.exit(-1)
            finalConfirm(f)
            pack(f, ignoreErr)
            sys.exit(0)

        elif cmd in ('--unpack', '-u'):
            # printWarning()
            if os.path.isfile(inputs):
                f = cleanUnpackList(inputs)
            elif os.path.isdir(inputs):
                f = getTars(inputs)
                f = refineList(f)
            else:
                print('Invalid unpacking input.')
                sys.exit(-1)
            finalConfirm(f)
            unpack(f, ignoreErr)
            sys.exit(0)

        elif cmd in ('--split', '-s'):
            if os.path.isdir(inputs):
                f, lim = getOverSize(inputs)
                f = refineList(f)
            else:
                print('Invalid search directory.')
                sys.exit(-1)
            finalConfirm(f)
            spliTar(f, lim, ignoreErr)
            sys.exit(0)

        elif cmd in ('--combine', '-c'):
            if os.path.isdir(inputs):
                f = getParts(inputs)
                f = refineList(f)
                finalConfirm(f)
                combineTar(f, ignoreErr)
                sys.exit(0)
            else:
                print('Invalid search directory.')
                sys.exit(-1)

        elif cmd == '--help':
            dispHelp()
            sys.exit(0)

        elif cmd == '--install':
            install()
            sys.exit(0)

        elif cmd == '--uninstall':
            uninstall()
            sys.exit(0)

        else:
            print('Unknown command "' + cmd + '".')
            sys.exit(-1)
    except (KeyboardInterrupt, EOFError):
        print('\nAbort mission.\n')
        sys.exit(0)


if __name__ == '__main__':
    if os.name != 'posix':
        print('Please use a unix-like system with these commands:')
        print('\ttar, split, cat')
        sys.exit(-1)
    else:
        # define some global constants
        ext_list = '.box.list'
        ext_box = '.box.tar.gz'
        ext_part = '.part'
        file_log = 'failed.box.log'
        main()


# TODO:
# * Test ignore-error


#     for root, directories, filenames in os.walk('/tmp/'):
# ...     for directory in directories:
# ...             print os.path.join(root, directory)
# ...     for filename in filenames:
# ...             print os.path.join(root,filename)
