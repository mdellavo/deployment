from fabric.api import *
from fabric.contrib.files import exists, append
from fabric.contrib.project import rsync_project
from tempfile import gettempdir

def virtualenv_create(env, **kwargs):
    cmd = sudo if kwargs.get('use_sudo') else run
    return cmd('virtualenv %s' % env)
    
def virtualenv_activate(env):
    return prefix('source %s/bin/activate' % env)

def pip(*packages, **kwargs):
    cmd = sudo if kwargs.get('use_sudo') else run
    env = '-E %s' % kwargs['env'] if 'env' in kwargs else ''
    return cmd('pip install -U %s %s' % (env, ' '.join(packages)))

def apt_get(*packages):
    return sudo('DEBIAN_FRONTEND=noninteractive apt-get install -q -y %s' % ' '.join(packages))

def apt_update():
    return sudo('DEBIAN_FRONTEND=noninteractive apt-get update -y -q')

def easy_install(*packages, **kwargs):
    cmd = sudo if kwargs.get('use_sudo') else run
    return cmd('easy_install %s' % ' '.join(packages))

def add_apt_repo(*repos):
    for repo in repos:
        sudo('add-apt-repository %s' % repo)

def svn_repo(host, module, branch=None):
    
    path = '%s/branches/%s' % (module, branch) \
        if branch and branch != 'trunk' else '%s/trunk' % module

    return 'svn://%s/%s' % (host, path)

def svn_checkout(host, module, branch, dirname):
    repo = svn_repo(host, module, branch)
    return run('svn co %s %s' % (repo, dirname))

def svn_export(host, module, branch, dirname):
    repo = svn_repo(host, module, branch)
    return run('svn export %s %s' % (repo, dirname))

def lsvn_checkout(host, module, branch, dirname):
    repo = svn_repo(host, module, branch)
    return local('svn co %s %s' % (repo, dirname))

def lsvn_export(host, module, branch, dirname):
    repo = svn_repo(host, module, branch)
    return local('svn export %s %s' % (repo, dirname))
    
def dpkg_install(path):
    return sudo('dpkg -i %s' % path)

def ufw_default(rule):
    return sudo('ufw default %s' % rule)

def ufw_enable():
    return sudo('yes|ufw enable')

def ufw_disable():
    return sudo('ufw disable')

def ufw_logging(status):
    return sudo('ufw logging %s' % 'on' if status else 'off')

def ufw_allow(*services):
    for service in services:
        sudo('ufw allow %s' % service)

def ufw_deny(*services):
    for service in services:
        sudo('ufw deny %s' % service)

def ufw_limit(*services):
    for service in services:
        sudo('ufw limit %s' % service)

def useradd(username):
    return sudo('useradd -m -G www-data %s' % username)

def start_service(service):
    return sudo('/etc/init.d/%s start' % service)

def stop_service(service):
    return sudo('/etc/init.d/%s stop' % service)

def restart_service(service):
    return sudo('/etc/init.d/%s restart' % service)

def backup_file(src, dest, **kwargs):
    cmd = sudo if kwargs.get('use_sudo') else run
    if exists(src):
        cmd('mv -f %s %s-`date +%%Y-%%m-%%d`' % (src, dest))

def python_svn_install(host, module, branch, env_path, use_sudo=True):
    cmd = sudo if use_sudo else run

    rv = None
    temp_dir = gettempdir() 

    with lcd(temp_dir):
        lsvn_checkout(host, module, branch, module)
        rsync_project('/tmp', module)
        local('rm -rf %s' % module)

    with virtualenv_activate(env_path):
        rv = cmd('cd /tmp/%s && python setup.py install' % module)

    cmd('rm -rf /tmp/%s' % module)

    return rv

def add_mount(file_system, mount_point, type, options):
    if isinstance(options, (list, tuple)):
        ','.join(str(o) for o in options)

    parts = (file_system, mount_point, type, options, 0, 0)
    line = "\t".join(str(p) for p in parts)

    return append('/etc/fstab', line, use_sudo=True)
    
def postconf(k, v):
    sudo('postconf -e "%s=%s"' % (k, v))
