Setting up a new api gatekeeper:

install nginx-extras
copy nginx-site.conf to /etc/nginx/sites-available and create a symlink in /etc/nginx/sites-enabled. Remove the 'default' symlink from /etc/nginx/sites-enabled

edit /etc/nginx/sites-available/nginx-site.conf to point to the proper location of apigk.lua

run coreapis with the gk component enabled on localhost port 6543 (or modify nginx-site.conf approprately)

start nginx. Point *.gk.feideconnect.no to this box.
