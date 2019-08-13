# license_mgmt
license management

HOWTO:
1. install mysql
2. python3 -m venv license_mgmt_venv
3. source license_mgmt_venv/bin/activate
4. pip install -r requirements.txt 
5. re-create migrations directory
   1) remove migrations
   2) python3 manage.py db init
   3) python3 manage.py db migrate
   4) python3 manage.py db upgrade
6. python3 license_mgmt.py

test:
python3 test/license_client.py -s 211803601049 -m cc:be:59:9d:44:dc -c GE-4
