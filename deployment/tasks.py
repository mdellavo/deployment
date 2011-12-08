from fabric.api import *
from fabric.contrib.files import contains, upload_template, sed, exists, uncomment, comment, append
import sys

from deployment.fabric_utils import *

import os

import yaml
import glob

DEPLOY_PATH = os.path.join('.', 'deploy')
CONFIGS_PATH = os.path.join(DEPLOY_PATH, 'configs')
CONFIG_PATH = os.path.join(DEPLOY_PATH, 'config.yml')

CONFIG = {}

def load_config(config_path): 
    if os.path.exists(config_path):
        CONFIG.update(yaml.load(open(config_path)))

        app_name = CONFIG.get('APP_NAME')
        if app_name:
            CONFIG['APP_PATH'] = os.path.join('/apps', app_name)
            CONFIG['CONFIG_PATH'] = os.path.join('/apps', app_name, 'configs')

load_config(CONFIG_PATH)

slurp = lambda path: list(i.strip() for i in open(path) if i.strip())

def setup_sshd():
    sed('/etc/ssh/sshd_config', 'PermitRootLogin yes', 'PermitRootLogin no', use_sudo=True)
    sudo('restart ssh')

def setup_hostname():
    assert CONFIG.get('HOSTNAME'), 'Config missing HOSTNAME'

    current_hostname = run('cat /etc/hostname')
    sed('/etc/hostname', current_hostname, CONFIG['HOSTNAME'], use_sudo=True)
    sed('/etc/hosts', current_hostname, CONFIG['HOSTNAME'], use_sudo=True)
    sudo('start hostname')

def setup_ufw():
    ufw_disable()
    ufw_default('deny')

    allowed_services_path = os.path.join(DEPLOY_PATH, 'services.allow')
    if os.path.exists(allowed_services_path):
        ufw_allow(*slurp(allowed_services_path))

    denied_services_path = os.path.join(DEPLOY_PATH, 'services.deny')
    if os.path.exists(denied_services_path):
        ufw_deny(*slurp(denied_services_path))

    limited_services_path = os.path.join(DEPLOY_PATH, 'services.limit')
    if os.path.exists(limited_services_path):
        ufw_limit(*slurp(limited_services_path))

    ufw_logging(True)
    ufw_enable()

def setup_monit():
    assert CONFIG.get('HOSTNAME'), 'Config missing HOSTNAME'
    assert CONFIG.get('APP_NAME'), 'Config missing APP_NAME'
    assert CONFIG.get('ADMIN_EMAIL'), 'Config missing ADMIN_EMAIL'

    sed('/etc/default/monit', 'startup=0', 'startup=1', use_sudo=True)

    upload_template(os.path.join(CONFIGS_PATH, 'monitrc'),
                    '/etc/monit/monitrc',
                    CONFIG,
                    use_sudo=True)

    sudo('chown root /etc/monit/monitrc')

    restart_service('monit')

def setup_fail2ban():
    upload_template(os.path.join(CONFIGS_PATH, 'jail.local'), '/etc/fail2ban', dict(), use_sudo=True)
    restart_service('fail2ban')

def setup_postfix():
    assert CONFIG.get('HOSTNAME'), 'Config missing HOSTNAME'
    assert CONFIG.get('ADMIN_EMAIL'), 'Config missing ADMIN_EMAIL'

    postconf('relayhost', CONFIG['RELAYHOST'])
    postconf('myhostname', CONFIG['HOSTNAME'])
    postconf('myorigin', CONFIG['HOSTNAME'])
    postconf('mynetworks', '127.0.0.0/8 [::ffff:127.0.0.0]/104 [::1]/128')
    postconf('mydestination', '%s, localhost.localdomain, localhost' % CONFIG['HOSTNAME'])

    append('/etc/aliases', 'root:\t%s' % CONFIG['ADMIN_EMAIL'], use_sudo=True)
    sudo('newaliases')

    restart_service('postfix')

def setup_ssl():
    put( os.path.join(CONFIGS_PATH, 'server.crt'),
         '/etc/ssl/certs/server.crt',
         use_sudo=True )

    put( os.path.join(CONFIGS_PATH, 'server.key'),
         '/etc/ssl/private/server.key',
         use_sudo=True )

def setup_nginx():
    assert CONFIG.get('APP_NAME'), 'Config missing APP_NAME'

    sudo('rm -f /etc/nginx/sites-*/default*')

    upload_template(os.path.join(CONFIGS_PATH, 'nginx-site.conf'),
                    '/etc/nginx/sites-available/%s' % CONFIG['APP_NAME'],
                    CONFIG,
                    use_sudo=True)

    sudo('ln -sf /etc/nginx/sites-available/%s /etc/nginx/sites-enabled/%s' % \
             (CONFIG['APP_NAME'], CONFIG['APP_NAME']))

    restart_service('nginx')

def setup_uwsgi():
    assert CONFIG.get('APP_NAME'), 'Config missing APP_NAME'

    upload_template( os.path.join(CONFIGS_PATH, 'uwsgi-app.ini'),
                     '/etc/uwsgi-python/apps-available/%s' % CONFIG['APP_NAME'],
                     CONFIG,
                     use_sudo=True)

    sudo('ln -sf /etc/uwsgi-python/apps-available/%s /etc/uwsgi-python/apps-enabled/%s.ini' % \
             (CONFIG['APP_NAME'], CONFIG['APP_NAME']))

    restart_service('uwsgi-python')

def setup_odbc():
    put(os.path.join(CONFIGS_PATH, 'odbc.ini'), '/etc', use_sudo=True)
    put(os.path.join(CONFIGS_PATH, 'odbcinst.ini'), '/etc', use_sudo=True)
    put(os.path.join(CONFIGS_PATH, 'freetds.conf'), '/etc', use_sudo=True)

def setup_mounts():
    fstab_path = os.path.join(DEPLOY_PATH, 'fstab')
    if os.path.exists(fstab_path):
        append('/etc/fstab', slurp(fstab_path), use_sudo=True)

def setup_base():
    uncomment('/etc/apt/sources.list', '# deb http', use_sudo=True)
    uncomment('/etc/apt/sources.list', '# deb-src http', use_sudo=True)
    apt_update()

    apt_get('python-software-properties')

    ppas_path = os.path.join(DEPLOY_PATH, 'ppas.txt')
    if os.path.exists(ppas_path):
        add_apt_repo(*slurp(ppas_path))
        apt_update()

    packages_path = os.path.join(DEPLOY_PATH, 'packages.txt')
    if os.path.exists(packages_path):
        apt_get(*slurp(packages_path))

    custom_packages_path = os.path.join(DEPLOY_PATH, 'packages')
    custom_packages_search = os.path.join(custom_packages_path, '*.deb')
    if os.path.exists(custom_packages_path):
        with cd('/tmp'):
            for i in glob.glob(custom_packages_search):
                put(i, os.path.basename(i))
                dpkg_install(os.path.basename(i))
                run('rm %s' % os.path.basename(i))

    easy_install('pip', use_sudo=True)
    pip('virtualenv', use_sudo=True)

    sudo('mkdir -p /apps')

def setup_env():
    assert CONFIG.get('APP_NAME'), 'Config missing APP_NAME'

    virtualenv_create(CONFIG['APP_PATH'], use_sudo=True)
    pip('distribute', use_sudo=True, env=CONFIG['APP_PATH'])

    requirements_path = os.path.join(DEPLOY_PATH, 'requirements.txt')
    if os.path.exists(requirements_path):
        pip(*slurp(requirements_path), use_sudo=True, env=CONFIG['APP_PATH'])
        sudo('rm -rf %s' % os.path.join(CONFIG['APP_PATH'], 'build'))

def setup_app():
    assert CONFIG.get('APP_NAME'), 'Config missing APP_NAME'
    assert CONFIG.get('SVN_HOST'), 'Config missing SVN_HOST'

    python_svn_install( CONFIG['SVN_HOST'],
                        CONFIG['APP_NAME'],
                       'production',
                        CONFIG['APP_PATH'],
                        use_sudo=True )

    sudo('mkdir -p %s' % CONFIG['CONFIG_PATH'])
    sudo('mkdir -p %s' % os.path.join(CONFIG['APP_PATH'], 'logs'))
    sudo('mkdir -p %s' % os.path.join(CONFIG['APP_PATH'], 'tmp'))

    put('production.ini', CONFIG['CONFIG_PATH'], use_sudo=True)
    put('app.wsgi', CONFIG['APP_PATH'], use_sudo=True)

    sudo('touch /var/run/uwsgi-python/%s/reload' % CONFIG['APP_NAME'])

    restart_service('uwsgi-python')

def setup_assets():
    rsync_project('/tmp', '*/public')
    sudo('rm -rf %s' % os.path.join(CONFIG['APP_PATH'], 'public'))
    sudo('mv /tmp/public %s' % CONFIG['APP_PATH'])

def setup_permissions():
    sudo('chown -R www-data:www-data /apps')
    sudo('chmod -R 0775 /apps')
