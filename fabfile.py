from fabric.api import env
from deployment import tasks

# FIXME setup syslog
# FIXME backup before update
# FIXME setup hosts/dns
# FIXME add postix to monit
# FIXME add fail2ban to monit
# FIXME remove apache fail2ban for nginx
# FIXME create a setup_webserver task
# FIXME freetds conf fix?
# FIXME setup hosts/dns?

def setup_base():
    tasks.setup_sshd()
    tasks.setup_ssl()
    tasks.setup_hostname()
    tasks.setup_base()
    tasks.setup_postfix()
    tasks.setup_mounts()
    tasks.setup_ufw()
    tasks.setup_nginx()
    tasks.setup_uwsgi()
    tasks.setup_monit()
    tasks.setup_fail2ban()

setup_env = tasks.setup_env
setup_app = tasks.setup_app

def setup():
    setup_base()
    setup_env()
    setup_app()
