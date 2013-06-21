from subprocess import DEVNULL
import os
import tempfile
import shutil
import shlex
import configparser
import sys
from sarge import run as sarge_run, capture_stdout

DOCS = 'docs/source'
EXCLUDE = ['.buildinfo']
INI_FILE = 's2g.ini'

HEAD = 95
BLUE = 94
OK   = 92
WARN = 93
FAIL = 91
ENDC = '\033[0m'

def cprint(*text, color=HEAD):

    out = '{}'* len(text)
    out = out.format(*text)

    if color:
        code = '\033[{}m'.format(color)
        print (code, out, ENDC)
    else:
        print (out)


GITPATH = None

def get_git_path():
    wd = os.getcwd()

    while wd != '/':
        path = os.path.join(wd,'.git')
        if os.path.exists(path):
            return wd

        wd = os.path.split(wd)[0]

    cprint('!!!  Not a git repository', color=FAIL)
    sys.exit(0)




def get_conf():

    config_filename = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                   'config', INI_FILE)
    config = configparser.ConfigParser()
    config.read(config_filename)

    user_config_path = os.path.join(GITPATH, INI_FILE)

    if not os.path.exists(user_config_path):
        cprint('===  User configuration not found, using default values.')
        return config

    user_config = configparser.ConfigParser()
    user_config.read(user_config_path)

    cprint('===  User configuration found.')

    try:
        for section in user_config.sections():
            for key in user_config[section]:
                config[section][key]  # Only allow existing keys
                config[section][key] = user_config[section][key]
    except KeyError:
        cprint('###  Unknow option: ', key,' in section ', section, color=WARN )


    return config


'''def run(command, capture_out=True, show_err=False):

    output = subprocess.PIPE if capture_out else None
    err = subprocess.DEVNULL if capture_out else None

    with subprocess.Popen(shlex.split(command), stdout=output,
            stderr=err, universal_newlines=True) as proc:

        out = proc.stdout.read() if capture_out else ''
        ret = proc.poll()

    return out.strip(), ret'''

def check_exit_code(code):
    if code != 0:
        cprint('!!!  Last command fails, see previous output', color=FAIL)
        sys.exit(code)


def run(command, get_output=False, cwd=None):
    """By default, run all commands at GITPATH directory.
    If command fails, stop program execution.
    """
    if cwd is None:
        cwd = GITPATH

    cprint ('===')
    cprint ('===  Command: ', command)
    cprint ('===  CWD:     ', cwd)
    cprint ('===')

    if get_output:
        proc = capture_stdout(command, cwd=cwd)
        out = proc.stdout.read().decode()
        print(out, end='')
        check_exit_code(proc.returncode)
        return out
    else:
        proc = sarge_run(command, cwd=cwd)
        check_exit_code(proc.returncode)





def get_remote(service, remote_name=''):
    out = run('git remote -v', get_output=True)

    for line in out.splitlines():
        if 'push' in line and service in line:
            if remote_name == '':
                return line.split()[1]
            elif line.split()[0] == remote_name:
                return line.split()[1]

    cprint('!!!  No remote url remote found, set one with "git remote add <name> <url>"', color=FAIL)
    sys.exit(0)


def push_doc(remote, branch, message, output, exclude, extra, tmp):
    repo_dir = os.path.join(tmp, 'repo')
    docs_dir = os.path.join(tmp, 'copy', output)

    run('git clone {0} -b {1} repo'.format(remote, branch), cwd=tmp)

    command = sarge_run('git show-ref --verify --quiet refs/heads/{}'.format(branch),
                        cwd=repo_dir)

    if command.returncode != 0:  # branch doesn't exists
        cprint('===  Creating new branch "{}"'.format(branch))
        #run('git clone {} repo'.format(remote), cwd=tmp)
        run('git checkout --orphan {}'.format(branch), cwd=repo_dir)

    run('git rm -rf .', cwd=repo_dir)
    run('touch .nojekyll', cwd=repo_dir)

    for entry in os.listdir(docs_dir):
        if entry not in exclude:
            shutil.move(os.path.join(docs_dir, entry), repo_dir)

    run('git add -A', cwd=repo_dir)
    run('git commit -m "{}"'.format(message), cwd=repo_dir)
    run('git push origin {}'.format(branch), cwd=repo_dir)

    cprint ('===')
    cprint ('===  Documentation pushed.')
    cprint ('===')


def generate_output(command, tmp):

    #with tempfile.TemporaryDirectory(prefix='d2g_generated_doc') as tmp:

    temp_dir = os.path.join(tmp, 'copy')
    shutil.copytree(GITPATH, temp_dir, ignore=shutil.ignore_patterns('.*'))

    run(command, cwd=temp_dir)


def main():

    global GITPATH
    GITPATH = get_git_path()

    conf = get_conf()

    if conf['git']['remote'] == '':
        remote_name = None
    else:
        remote_name = conf['git']['remote']

    remote = get_remote(conf['git']['service'], conf['git']['remote'])

    with tempfile.TemporaryDirectory(prefix='d2g_') as tmp:
        generate_output(conf['doc']['command'], tmp)

        # Comma separated values to list
        exclude = tuple(map(str.strip, conf['doc']['exclude'].split(',')))

        push_doc(remote=remote, branch=conf['git']['branch'],
                 message=conf['git']['message'],
                 output=conf['doc']['output_folder'],
                 exclude=exclude, extra=conf['doc']['extra'],
                 tmp=tmp)
